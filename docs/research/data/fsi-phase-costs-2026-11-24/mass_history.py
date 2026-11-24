"""Compare identical accepted fields and mass histories with independent event timing on each rank."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'cases/fsi'),str(ROOT/'scripts')]
from verify_fsi_inlet import Runner,error
from verify_fsi_moving_port import circular_case,verify_volume_rates


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(path,ranks):
    values={}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            if row['Stage Name']=='Main Stage' and row['Event Name']=='FSIMassObserve':
                rank=int(row['Rank'])
                if rank in values:raise ValueError('Duplicate event')
                values[rank]=(int(row['Count']),float(row['Time']))
    return [values.get(i,(0,0.)) for i in range(ranks)]


def one(exe,mpi,work,cfg,geo,label,ranks):
    runner=Runner(exe,mpi,work,timeout=1800,interface_area=geo['interface_area'],singleton=True)
    path=work/(label+'-events.csv')
    start=time.monotonic()
    fields,rows,log=runner.solve(label,cfg,ranks,['-log_view',':'+str(path.resolve())+':ascii_csv'])
    elapsed=time.monotonic()-start
    observations=event(path,ranks)
    hist={k:[r[k] for r in rows] for k in rows[0]} if rows else {}
    if rows:
        verify_volume_rates(rows[0]['endpoint_volume'],rows[1:])
    if log.count('fsi_step=')!=cfg['fsi']['steps']:raise ValueError('Missing accepted steps')
    return fields,hist,dict(counts=[v[0] for v in observations],rank_seconds=[v[1] for v in observations],
                            max_rank_seconds=max(v[1] for v in observations),whole_with_python_s=elapsed,
                            event_sha256=digest(path),vtu_sha256=digest(work/(label+('_rank0' if ranks>1 else '')+'.vtu')))


def measure(exes,mpi,work,repeats,ranks,steps):
    cfg,geo=circular_case(work,(1.,0.,0.),(0.,0.,0.))
    cfg.pop('time_control',None)
    cfg['fsi'].update(steps=steps,dt=.005,pressure_face_history=False,output_interval=steps)
    result=[]
    for rank in ranks:
        for scheme in ('generalized_alpha','be'):
            cfg['time']=dict(scheme=scheme)
            if scheme=='generalized_alpha':cfg['time']['rho_infinity']=.5
            for enabled in (True,False):
                cfg['fsi']['output_interval']=steps if enabled else 0
                samples=[]
                for rep in range(repeats):
                    record={}
                    previous=None
                    for name in (('baseline','optimized') if rep%2==0 else ('optimized','baseline')):
                        label=f'{scheme}-r{rank}-history{int(enabled)}-rep{rep}-{name}'
                        fields,hist,data=one(exes[name],mpi,work,cfg,geo,label,rank)
                        if name=='baseline' or enabled:
                            if data['counts']!=[steps]*rank:raise ValueError('Missing mass observation event')
                        elif data['counts']!=[0]*rank:raise ValueError('Unexpected mass observation with history off')
                        record[name]=data
                        if previous is not None:
                            old_fields,old_hist=previous
                            record['field_error']=error(old_fields,fields)
                            if old_hist.keys()!=hist.keys():raise ValueError('History columns changed')
                            record['history_error']=max((abs(a-b) for k,col in hist.items() for a,b in zip(col,old_hist[k])),default=0.)
                            if max(record['field_error'],record['history_error'])>2e-10:raise ValueError('Numerical observations changed')
                        previous=fields,hist
                    samples.append(record)
                    print(rank,scheme,enabled,rep,record['baseline']['max_rank_seconds'],record['optimized']['max_rank_seconds'],flush=True)
                    (work/'measurements.json').write_text(json.dumps(dict(completed=result,active=dict(rank=rank,scheme=scheme,history=enabled,samples=samples)))+'\n')
                result.append(dict(rank=rank,scheme=scheme,history=enabled,samples=samples))
    return dict(binary_sha256={k:digest(v) for k,v in exes.items()},mesh_sha256={f:digest(work/f) for f in ('fluid.msh','solid.msh')},
                geometry=geo,steps=steps,dt=.005,repeats=repeats,runs=result)


def table(data):
    rows=[]
    for r in data['runs']:
        samples=r['samples']
        if len(samples)!=data['repeats']:raise ValueError('Incomplete repeated pair')
        a=[x['baseline']['max_rank_seconds'] for x in samples]
        b=[x['optimized']['max_rank_seconds'] for x in samples]
        rows.append(dict(ranks=r['rank'],scheme=r['scheme'],history=r['history'],pairs=len(samples),accepted_steps=data['steps'],
                         baseline_event_ms=1000*statistics.median(a),optimized_event_ms=1000*statistics.median(b),
                         median_paired_ratio=statistics.median(y/x for x,y in zip(a,b)),min_paired_ratio=min(y/x for x,y in zip(a,b)),
                         max_paired_ratio=max(y/x for x,y in zip(a,b)),max_field_error=max(x['field_error'] for x in samples),
                         max_history_error=max(x['history_error'] for x in samples)))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path)
    p.add_argument('--optimized',type=Path)
    p.add_argument('--mpiexec')
    p.add_argument('--ranks',nargs='+',type=int,default=[1,2])
    p.add_argument('--pairs',type=int,default=5)
    p.add_argument('--steps',type=int,default=9)
    p.add_argument('--work',type=Path)
    p.add_argument('--archive',type=Path)
    p.add_argument('--write-archive',type=Path)
    p.add_argument('--csv',type=Path,required=True)
    a=p.parse_args()
    if a.archive:data=json.loads(a.archive.read_text())
    else:
        if not (a.work and a.baseline and a.optimized and a.mpiexec and a.pairs>=1):
            p.error('Raw measurements require both compiled versions, MPI and a work directory')
        a.work.mkdir(exist_ok=True,parents=True)
        data=measure(dict(baseline=a.baseline.resolve(),optimized=a.optimized.resolve()),a.mpiexec,a.work.resolve(),a.pairs,a.ranks,a.steps)
    rows=table(data)
    with a.csv.open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    if a.write_archive:a.write_archive.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
