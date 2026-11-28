"""Collect bounded Slurm receipts, verify raw hashes, and summarize inclusive level events."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('runs',type=Path)
    cli.add_argument('output',type=Path)
    args=cli.parse_args()
    root=args.runs.resolve()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    records={}
    index={}
    summary=[]
    def identify(path, expected=None):
        key=str(path).replace(str(Path.home()),'$HOME',1)
        sha=digest(path)
        if expected and sha!=expected:
            raise ValueError(f'Hash mismatch: {key}')
        index[key]=dict(bytes=path.stat().st_size,sha256=sha)
        return key
    def load(path):
        key=identify(path)
        obj=json.loads(path.read_text())
        records[key]=obj
        return obj
    for name in ('A1','A2','A4','A4-422','A2-independent','A2-independent-LU','B20','B-LU','B-system',
                 'A-reg-32','A-reg-100','A-audit-32','A-audit-100','coarse-64','coarse-512',
                 'coarse-1024','coarse-formal','large-owner','B-native-RCS','C-first-64'):
        base=root/name
        file={'B-native-RCS':'screen.json','C-first-64':'diagnosis.json'}.get(name,'summary.json')
        data=load(base/file)
        for row in data.get('runs',[data]):
            log=row.get('log')
            if not log:
                if 'solver' in row:
                    log=base/f"{row['iteration']}-{row['solver']}"/'solve.log'
                elif 'mode' in row and 'repeat' in row:
                    log=base/str(row['repeat'])/row['mode']/'solve.log'
                elif 'profile' in row:
                    log=base/f"r{row['ranks']}-profile{int(row['profile'])}"/'solver.log'
                else:
                    log=base/'solve.log'
            path=Path(log)
            key=identify(path,row.get('log_sha256'))
            seconds=row.get('T_job',row.get('wall_seconds'))
            cores=128 if name.startswith('coarse-') or name=='large-owner' else data.get('ranks',len(data.get('affinity',[])) or 1)
            solver=row.get('solver',row.get('mode',row.get('budget',row.get('local_fields'))))
            summary.append(dict(campaign=name,solver=solver,kind=row.get('kind','diagnostic'),
                status=row.get('status'),error=row.get('error'),cores=cores,T_job_s=seconds,
                core_hours=seconds*cores/3600 if seconds is not None else None,
                process_tree_peak_bytes=row.get('rss_peak',row.get('local_job_peak_sampled_rss_bytes')),
                log=key,log_sha256=index[key]['sha256']))
        for r in [data.get('prepare'),data.get('reference')]:
            if r and r.get('log'):
                identify(Path(r['log']),r.get('log_sha256'))
        for p in base.glob('diag-*/run.json'):
            r=load(p)
            identify(p.parent/'solve.log',r['log_sha256'])
    for name in ('B-layout.json','C-layout.json','B-precision.json','C-system.json'):
        load(root/name)
    for name in ('C-first-64','B-system/lu-refined'):
        for p in (root/name).glob('*.petsc*'):
            identify(p)
    for grid in 'BC':
        for p in sorted((root/(grid+'-layout')).glob('*.csv')):
            identify(p)
    for name in ('piece-controls.log','algebra-414.log','export_layout','layout-build.log',
                 'replay-407.log','replay-408.log','C-first/solve.log','C-first/run.json'):
        identify(root/name)
    old=root.parent/'fsi-scalable-02-runs'
    for name in ('C20-fixed','B20'):
        original=load(old/name/'summary.json')
        for r in original['runs']:
            p=old/name/f"{r['iteration']}-{r['solver']}"
            identify(p/'solve.log',r['log_sha256'])
            if (p/'32-procs/histor.dat').exists():
                identify(p/'32-procs/histor.dat')
    for p in (root/'B-native-RCS').glob('*-procs/histor.dat'):
        identify(p)
    for n in ('B20','B-LU'):
        for p in (root/n).glob('*/solve.log'):
            if p.parent.name!='prepare':
                log=p.read_text(errors='replace')
                detail=[l for l in log.splitlines() if l.startswith(('linear_iteration_limit_residual ',
                        'linear_iteration_limit_field_residual ','pc_monolithic_mg prefix='))]
                if detail:
                    records[n+'/'+p.parent.name+'/diagnostic_lines']=detail[:8]
    seed_files=[root.parent/'fsi-scalable-01-runs/scale-n22/1795753257759852998/results.json',
                old/'large-t2/1795788192001678783/results.json']
    for seed in seed_files:
        key=identify(seed)
        metadata=json.loads(seed.read_text())
        cases=[]
        for c in metadata['cases']:
            if c['ranks'] not in (64,128):
                continue
            for item in c['input_sha256']+c['preparation']['artifacts']:
                identify(seed.parent/item['path'],item['sha256'])
            cases.append({k:c[k] for k in ('ranks','subdivisions','input_sha256','preparation')})
        records[key]=dict(cases=cases,source=metadata['build_source'],binary=metadata['executable_sha256'])
    profiles=[]
    for budget in (64,512,1024):
        folder=root/f'coarse-{budget}/r128-profile1'
        events=folder/'events.csv'
        row=next(r for r in json.loads((folder.parent/'summary.json').read_text())['runs'] if r['profile'])
        identify(events,row['event_sha256'])
        groups={}
        with events.open() as stream:
            for r in csv.DictReader(stream):
                if r['Stage Name']=='Main Stage' and (r['Event Name'].startswith('FSI_L') or r['Event Name']=='PCSetUp'):
                    groups.setdefault(r['Event Name'],[]).append(r)
        for event,rows in groups.items():
            if {int(r['Rank']) for r in rows}!=set(range(128)):
                raise ValueError('Incomplete rank event coverage')
            rank0=next(r for r in rows if r['Rank']=='0')
            seconds=[float(r['Time']) for r in rows]
            reductions=Counter(float(r['Num Reductions']) for r in rows)
            profiles.append(dict(row_budget=budget,event=event,rank0_seconds=rank0['Time'],
                min_seconds=min(seconds),mean_seconds=statistics.mean(seconds),max_seconds=max(seconds),
                rank0_calls=rank0['Count'],rank0_reductions=rank0['Num Reductions'],
                reductions_and_rank_counts=json.dumps(sorted(reductions.items()))))
    def save(path,obj):
        text=json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)
        path.write_text(text.replace(str(Path.home()),'$HOME')+'\n')
    save(out/'validation.json',records)
    save(out/'log-index.json',index)
    write_csv(out/'runs.csv',summary)
    write_csv(out/'levels.csv',profiles)


if __name__=='__main__':
    main()
