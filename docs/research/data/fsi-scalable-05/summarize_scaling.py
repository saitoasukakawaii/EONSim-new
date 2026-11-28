"""Report the three independently qualified C20 pure-MPI layouts relative to 32 ranks."""
import argparse
import json
from pathlib import Path

from collect_windows import digest
from resource_accounting import resource_hours
from scale_c import read_bindings


def summarize(direct, paths):
    direct_sha = digest(direct / 'window.json')
    baseline_sha = digest(paths[1] / 'window.json')
    threads = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    baseline = json.loads((paths[1] / 'window.json').read_text())
    reference = json.loads((direct / 'window.json').read_text())
    if (reference['profile'] != 'lu' or reference['qualification'] != 'awaiting_independent_crosscheck' or
            reference['ranks'] != 64 or reference['accepted_steps'] != list(range(1, 21)) or
            reference['log_sha256'] != digest(direct / 'solve.log') or
            any(reference[k] != baseline[k] for k in ('case', 'inputs', 'binary', 'compiled_source', 'partition'))):
        raise ValueError('C64 direct reference differs from the qualified original trajectory')
    entries = []
    for ranks, path in zip((32, 64, 128), paths):
        receipt = path / 'window.json'
        row = json.loads(receipt.read_text())
        log = path / 'solve.log'
        if (row['qualification'] != 'independent_pair_passed' or row['case'] != 'C' or
                row['ranks'] != ranks or row['formal'] or row['start_step'] != 0 or row['steps'] != 20 or
                row['accepted_steps'] != list(range(1, 21)) or row['reference_receipt'] != direct_sha or
                row['profile'] != 'fixed-1e-6' or row['preconditioner'] != {'pc': 'physics'} or
                row['allocated_cpus'] != 128 or row['thread_environment'] != threads or
                '-fsi_threads' in row['command'] or row['log_sha256'] != digest(log) or
                row['rank_bindings'] != read_bindings(log.read_text(), ranks) or
                any(row[k] != baseline[k] for k in ('inputs', 'binary', 'compiled_source', 'policy', 'archive_receipt'))):
            raise ValueError(f'Unmatched or unqualified cold C20 pure-MPI layout: {path}')
        if ranks != 64 and row['scaling']['baseline_window'] != baseline_sha:
            raise ValueError(f'New partition was qualified against another C64 baseline: {path}')
        hours = resource_hours(ranks, row['allocation'], row['T_job'])
        if any(row[key] != value for key, value in hours.items()):
            raise ValueError(f'Inconsistent recorded allocation or rank-hours: {path}')
        entries.append(dict(ranks=ranks, job=row['job'], window_sha256=digest(receipt),
                            log_sha256=row['log_sha256'], T_job=row['T_job'],
                            new_partition_seconds=row.get('partition_preparation', {}).get('T_job'),
                            rss_bytes=row['rss_peak'], newton=row['linear']['corrections'],
                            ksp=row['linear']['ksp_iterations'], max_ratio=row['linear']['max_ratio'],
                            **hours))
    for item in entries:
        item['speedup_from_32'] = entries[0]['T_job'] / item['T_job']
        item['efficiency_from_32'] = item['speedup_from_32'] / (item['ranks'] / 32)
    return dict(diagnostic_samples_per_layout=1, baseline_ranks=32, protocol_hash=baseline['policy']['hash'],
                lu_window_sha256=direct_sha, compiled_source=baseline['compiled_source'],
                binary=baseline['binary'], layouts=entries)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('direct', type=Path)
    cli.add_argument('layouts', type=Path, nargs=3, metavar='C20', help='32, 64 and 128-rank run directories, in order')
    args = cli.parse_args()
    print(json.dumps(summarize(args.direct, args.layouts), indent=2, allow_nan=False))
