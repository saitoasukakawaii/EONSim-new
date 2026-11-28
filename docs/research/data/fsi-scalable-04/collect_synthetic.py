"""Collect complete and interrupted synthetic jobs from their raw server directories."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            sha.update(block)
    return sha.hexdigest()


def portable(path):
    path = Path(path)
    return '$HOME/' + str(path.relative_to(Path.home())) if path.is_relative_to(Path.home()) else str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('jobs', type=Path, nargs='+')
    args = parser.parse_args()
    samples, jobs, index = [], [], {}

    def verify(path, expected=None):
        p = Path(path)
        key = portable(p)
        if key not in index:
            index[key] = dict(sha256=digest(p), bytes=p.stat().st_size)
        if expected and index[key]['sha256'] != expected:
            raise ValueError(f'Raw artifact differs from receipt: {p}')
        return key

    for directory in args.jobs:
        path = directory / 'summary.json'
        data = json.loads(path.read_text())
        receipt = verify(path)
        verify(data['seed'], data['seed_sha256'])
        seed = json.loads(Path(data['seed']).read_text())
        # The executable can be rebuilt in place between campaigns. Keep the
        # digest measured by the driver when the job actually used the executable.
        experiments = {}
        prep = {}
        for n, case in data['cases'].items():
            for p, sha in case['inputs'].items():
                verify(p, sha)
            for f, sha in case['reference_sha256'].items():
                verify(Path(case['reference']) / f, sha)
            experiments[n] = {k: case[k] for k in ('stats', 'median_reduction', 'coarsest_rows') if k in case}
            archived = next(c['preparation'] for c in seed['cases'] if c['subdivisions'] == int(n)
                            and c['ranks'] == 64 and c['status'] == 'passed')
            verify(archived['log'], archived['log_sha256'])
            prep[n] = float(archived['wall_seconds'])
            if not math.isfinite(prep[n]) or prep[n] <= 0:
                raise ValueError('Invalid archived partition preparation time')
            experiments[n]['preparation'] = dict(archived_seconds=prep[n], log=portable(archived['log']),
                                                 log_sha256=archived['log_sha256'], reused=True)
        counts = {}
        for row in data['runs']:
            if row.get('log_sha256'):
                verify(row['log'], row['log_sha256'])
            raw = Path(row['log']).parent
            if row.get('history_sha256'):
                verify(raw / 'solution.csv', row['history_sha256'])
            for stem, field in row.get('fields', {}).items():
                if len(field['pieces']) != 128:
                    raise ValueError(f'Incomplete piece evidence: {raw}/{stem}')
                for suffix, sha in field['pieces'].items():
                    verify(raw / (stem + suffix), sha)
            certified = row['status'] == 'passed'
            if certified and set(row['fields']) != {'solution', 'solution_step5'}:
                raise ValueError(f'Missing accepted final field or last saved phase: {raw}')
            label = str(row['mode'])
            if data['experiment'] == 'telescope':
                label = row['command'][row['command'].index('-monolithic_mg_coarse_rows_per_rank') + 1]
            if certified:
                key = (row['subdivisions'], label, row['kind'])
                counts[key] = counts.get(key, 0) + 1
            diag = row.get('corrections', {})
            fields = row.get('fields', {})
            wall = row.get('wall_seconds')
            prepare = prep[str(row['subdivisions'])]
            if certified and (not math.isfinite(wall) or wall <= 0 or row['core_hours'] != 128 * wall / 3600):
                raise ValueError('Inconsistent T_job or core-hours')
            samples.append(dict(job=data['job'], experiment=data['experiment'], subdivisions=row['subdivisions'],
                                setting=label, kind=row['kind'], repeat=row['repeat'], status=row['status'],
                                error=row.get('error'), T_prepare_archived_s=prepare, T_prepare_in_this_job_s=0,
                                T_job_s=wall, T_total_with_archived_prepare_s=prepare+wall if certified else None,
                                core_hours=row.get('core_hours'),
                                peak_sampled_rss_bytes=row.get('local_job_peak_sampled_rss_bytes'),
                                corrections=diag.get('corrections'), outer_iterations=diag.get('outer_iterations'),
                                true_residual_max_ratio=diag.get('max_true_residual_ratio'),
                                history_max_difference=row.get('history_difference'),
                                final_max_difference=fields.get('solution', {}).get('difference'),
                                last_phase_max_difference=fields.get('solution_step5', {}).get('difference'),
                                log=portable(row['log']), log_sha256=row.get('log_sha256')))
            if 'coarse' in row:
                detail = dict(row['coarse'])
                if 'profile' in detail:
                    event = dict(detail['profile'])
                    event['csv'] = verify(event['csv'], event['sha256'])
                    detail['profile'] = event
                experiments[str(row['subdivisions'])].setdefault('diagnostic_children', {})[label] = detail
        if data['passed']:
            expected = {37, 47} if data['experiment'] == 'owner' else {37}
            for n in expected:
                modes = {m for grid, m, kind in counts if grid == n}
                if len(modes) != 2 or any(counts.get((n, m, 'formal')) != 3 or
                                          counts.get((n, m, 'diagnostic_warmup')) != 1 for m in modes):
                    raise ValueError(f'Incomplete formal pair coverage on n={n}')
                formal = [r for r in data['runs'] if r['subdivisions'] == n and r['kind'] == 'formal']
                computed = {}
                for mode in sorted({r['mode'] for r in formal}):
                    selected = [r for r in formal if r['mode'] == mode]
                    if {r['repeat'] for r in selected} != {1, 2, 3}:
                        raise ValueError('Repeated or missing pair index')
                    computed[mode] = {}
                    for key in ('wall_seconds', 'core_hours', 'local_job_peak_sampled_rss_bytes'):
                        values = [r[key] for r in selected]
                        stats = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
                        if stats != data['cases'][str(n)]['stats'][str(mode)][key]:
                            raise ValueError(f'Receipt summary differs from formal samples for n={n}, mode={mode}, {key}')
                        computed[mode][key] = stats
                baseline, candidate = (0, 1) if data['experiment'] == 'owner' else (64, 0)
                reduction = 1 - computed[candidate]['wall_seconds']['median'] / computed[baseline]['wall_seconds']['median']
                if reduction != data['cases'][str(n)]['median_reduction']:
                    raise ValueError('Median reduction differs from the paired sample receipts')
        jobs.append(dict(experiment=data['experiment'], job=data['job'], completed=data['passed'], driver_commit=data['source'],
                         binary=portable(data['binary']), binary_commit=data['binary_commit'], binary_sha256=data['binary_sha256'],
                         seed=portable(data['seed']), seed_sha256=data['seed_sha256'], cases=experiments,
                         root=portable(directory), summary=receipt, summary_sha256=index[receipt]['sha256'],
                         affinity=data['affinity'], environment=data['environment']))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'synthetic-runs.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    for name, obj in [('synthetic-validation', jobs), ('synthetic-log-index', index)]:
        (args.output / (name + '.json')).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
