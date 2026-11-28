"""Collect compact trajectory receipts and content hashes, leaving complete fields on the host."""
import argparse
import csv
import gzip
import hashlib
import json
import re
from pathlib import Path
import subprocess
from physics_telescope import coarse_receipt
from tube_protocol import records
from resource_accounting import formal_resources, resource_hours


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1<<20), b''):
            value.update(block)
    return value.hexdigest()


def owner_smoother_stats(log, row):
    """Require active RCR bulk Braess smoothers on every reported step and rank."""
    options = row['linear']['effective_options']
    owner = row['preconditioner']['owner']
    prefix = '-rcr_bulk_monolithic_mg_'
    if (owner not in ('on', 'off') or options.get('-pc_recipe') != 'monolithic_mg' or
            options.get(prefix + 'smoother') != 'braess_sarazin' or
            options.get(prefix + 'braess_local_fields') != ('true' if owner == 'on' else 'false')):
        raise ValueError('RCR bulk Braess owner options differ from the declared configuration')
    result = []
    start = row.get('start_step', 0)
    reports = ('\n' + log).split('\nsolver_report ')[1:]
    if len(reports) != row['steps'] - start:
        raise ValueError('Missing solver report in Braess owner window')
    for step, report in enumerate(reports, start + 1):
        header, _, body = report.partition('\n')
        if int(records(['solver_report ' + header], 'solver_report ')[0]['step']) != step:
            raise ValueError('Unexpected step in Braess owner report')
        rows = [x for x in records(body.splitlines(), 'monolithic_mg_stats ') if x['path'] == 'root/rcr_bulk']
        rows.sort(key=lambda x: int(x['rank']))
        if [int(x['rank']) for x in rows] != list(range(row['ranks'])):
            raise ValueError('Incomplete rank coverage in RCR bulk MG statistics')
        names = ('levels', 'coarse_processes', 'coarse_solves', 'smoother_applications', 'schur_applications')
        counters = [{name: int(x[name]) for name in names} for x in rows]
        if any(x['levels'] < 2 or min(x.values()) <= 0 for x in counters):
            raise ValueError('RCR bulk MG did not execute its Schur smoother or coarse solve')
        result.append(dict(step=step, ranks=counters))
    return dict(owner=owner, per_step=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--runs', nargs='+', type=Path,
                        help='collect only the specified top-level run directories under root')
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    groups = [root] if not args.runs else [(root/path).resolve(strict=True) for path in args.runs]
    if args.runs and (len(set(groups)) != len(groups) or
                      any(p.parent != root or not p.is_dir() or p == out for p in groups)):
        parser.error('--runs requires distinct top-level run directories under root')
    out.mkdir(exist_ok=True,parents=True)
    summary, index, runs = [], {}, []
    legacy_allocations = {}
    for name in ('window.json','first.json','native-mesh.json','timings.json','review.json',
                 'supplement.json','restart-regression.json','continuation.json'):
        for p in sorted(p for group in groups for p in group.rglob(name)):
            if 'source' in p.relative_to(root).parts or out in p.parents:
                continue
            work = p.parent
            row = json.loads(p.read_text())
            if (work/'solve.log').is_file() and 'log_sha256' in row and row['log_sha256']!=digest(work/'solve.log'):
                raise ValueError(f'Log differs from receipt: {work}')
            entry = str(p.relative_to(root))
            saved = dict(receipt=entry, data=row)
            runs.append(saved)
            if name=='timings.json':
                layouts = set()
                for sample in row['runs']:
                    sample_path = work/Path(sample['receipt']).parent.name/'window.json'
                    if digest(sample_path) != sample['receipt_sha256']:
                        raise ValueError(f'Timing source differs: {sample_path}')
                    matched = json.loads(sample_path.read_text())
                    layouts.add(formal_resources(matched))
                    if row.get('experiment') == 'gamg_telescope':
                        wrapped = bool(sample['side'])
                        fields = coarse_receipt((sample_path.parent/'solve.log').read_text(),
                                                matched['ranks'], matched['steps'], wrapped,
                                                matched['linear']['effective_options'])
                        if wrapped and fields != matched['gamg_coarse_fields']:
                            raise ValueError(f'Coarse subtree differs from receipt: {sample_path}')
                    if matched['T_job'] != sample['T_job'] or matched['job'] != row['job']:
                        raise ValueError(f'Timing sample differs from original: {sample_path}')
                if len(layouts)>1 or (row['status']=='passed' and len(row['runs'])!=8):
                    raise ValueError(f'Unmatched timing resources or missing samples: {p}')
                if layouts:
                    job,cpus,ranks,affinity,launcher=next(iter(layouts))
                    saved['derived_timing_audit']=dict(job=job,allocated_cpus=cpus,active_ranks=ranks,
                        affinity=affinity,mpi_launcher=launcher,samples_checked=len(row['runs']),
                        detailed_monitors=False,componentwise_diagnostic=False)
            if name=='window.json':
                if (row.get('preconditioner', {}).get('pc') == 'pressure-mg' and
                        row['qualification'] in ('linear_window_only', 'independent_pair_passed')):
                    saved['derived_owner_smoother'] = owner_smoother_stats((work/'solve.log').read_text(), row)
                linear = row.get('linear',{})
                allocation = row.get('allocation')
                if not allocation:
                    # Early receipts lacked SLURM_JOB_CPUS_PER_NODE. Read the
                    # actual allocation from the job, never infer it from -n.
                    job = str(row['job'])
                    if job not in legacy_allocations:
                        records = subprocess.check_output(['sacct','-X','-P','-n','-j',job,
                            '-o','JobIDRaw,AllocCPUS'],text=True).splitlines()
                        matches = [r.split('|')[1] for r in records if r.split('|')[0]==job]
                        if len(matches)!=1:
                            raise ValueError(f'Missing Slurm allocation for job {job}')
                        legacy_allocations[job]=matches[0]
                    allocation=legacy_allocations[job]
                hours=resource_hours(row['ranks'],allocation,row.get('T_job'))
                saved['derived_resources']=dict(**hours,allocation_source='run_environment' if row.get('allocation') else 'sacct')
                summary.append(dict(run=str(work.relative_to(root)), job=row['job'],case=row['case'],steps=row['steps'],
                    profile=row['profile'],protocol=row['policy']['protocol_id'],hash=row['policy']['hash'],
                    start_step=row.get('start_step',0),accepted_in_segment=len(row.get('accepted_steps',[])),
                    accepted=row.get('start_step',0)+len(row.get('accepted_steps',[])),newton=linear.get('corrections'),
                    ksp=linear.get('ksp_iterations'),max_ratio=linear.get('max_ratio'),
                    seconds=row.get('T_job'),cumulative_seconds=row.get('cumulative_T_job',row.get('T_job')),
                    rss_bytes=row.get('rss_peak'),**hours,
                    qualification=row['qualification'],error=row.get('error','')))
            for f in sorted(work.rglob('*')):
                key = str(f.relative_to(root))
                if f.is_file() and key not in index:
                    index[key] = dict(bytes=f.stat().st_size,sha256=digest(f))
    job_ids = {str(run['data'].get('job', '')) for run in runs}
    for f in sorted(root.glob('*.log')):
        if args.runs and not any(part in job_ids for part in re.findall(r'\d+', f.stem)):
            continue
        index[f.name] = dict(bytes=f.stat().st_size,sha256=digest(f))
    with (out/'calibration.csv').open('w',newline='') as stream:
        if summary:
            writer = csv.DictWriter(stream,fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
    for filename, obj in [('run-receipts.json.gz',runs),('log-index.json.gz',index)]:
        with (out/filename).open('wb') as f, gzip.GzipFile(fileobj=f, mode='wb',mtime=0) as z:
            z.write(json.dumps(obj, separators=(',',':'),allow_nan=False).encode())
    print(f'{len(runs)} receipts, {len(index)} artifacts')


if __name__=='__main__':
    main()
