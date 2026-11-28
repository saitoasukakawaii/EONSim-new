"""Replay the qualified 64x2 synthetic seed with both Braess owner-field settings."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import benchmark_fsi_block_scaling as scaling


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('seed','root','binary'):
        cli.add_argument(name,type=Path)
    args=cli.parse_args()
    if not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0))!=128:
        cli.error('requires the same 128 physical cores')
    seed=json.loads(args.seed.read_text())
    root=args.root.resolve()
    root.mkdir(parents=True,exist_ok=False)
    threads=dict(OMP_NUM_THREADS='2',OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close',
                 MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    if any(seed['environment'].get(k)!=v for k,v in threads.items()):
        raise ValueError('Seed thread placement differs')
    os.environ.update(threads)
    result=dict(seed=str(args.seed.resolve()),seed_sha256=scaling.assembly.digest(args.seed),
                job=os.environ['SLURM_JOB_ID'],affinity=sorted(os.sched_getaffinity(0)),
                binary=scaling.assembly.digest(args.binary),environment=threads,runs=[],passed=False)
    for n in (37,47):
        case=next(c for c in seed['cases'] if c['subdivisions']==n and c['ranks']==64 and c['status']=='passed')
        original=next(r for r in case['runs'] if r['label']=='warmup-mono_braess_tentative' and r['status']=='passed')
        ref=Path(next(r['log'] for r in case['runs'] if r['label']=='reference' and r['status']=='passed')).parent
        for f in case['input_sha256']+case['preparation']['artifacts']:
            if scaling.assembly.digest(args.seed.parent/f['path'])!=f['sha256']:
                raise ValueError('Archived input or partition changed')
        dt=case['configuration']['fsi']['dt']
        history=scaling.assembly.history(ref/'solution.csv',5,dt)
        for enabled in (False,True):
            folder=root/f'n{n}-owner{int(enabled)}'
            folder.mkdir()
            cmd=original['command'].copy()
            cmd[cmd.index('-case')-1]=str(args.binary.resolve())
            cmd[cmd.index('-output')+1]=str(folder/'solution.vtu')
            if cmd[cmd.index('-fsi_threads')+1]!='2' or cmd[cmd.index('-n')+1]!='64':
                raise ValueError('Unexpected seed layout')
            cmd+=['-monolithic_mg_braess_local_fields',str(enabled).lower()]
            row=dict(subdivisions=n,local_fields=enabled,log=str(folder/'solve.log'),command=cmd)
            result['runs'].append(row)
            try:
                text=scaling.block.timed_command(cmd,folder/'solve.log',600,row,rss_interval=.5,rss_limit=140*2**30)
                trace=scaling.assembly.history(folder/'solution.csv',5,dt)
                audit=scaling.multigrid.audit(text,trace,64,'mono_braess_tentative')
                row.update({k:audit[k] for k in ('outer_iterations','dofs','corrections','max_true_residual_ratio')})
                row['history_difference']=scaling.assembly.compare_history(history,trace)
                for stem,reference in [('solution','fields.sqlite'),('solution_step5','last-step.sqlite')]:
                    db=folder/(stem+'.sqlite')
                    scaling.spool_fields(folder/(stem+'.vtu'),64,db)
                    row[stem+'_difference']=scaling.compare_spools(ref/reference,db)
                row['status']='passed'
            except Exception as error:
                row.update(status='failed',error=str(error))
                raise
            finally:
                if (folder/'solve.log').is_file():
                    row['log_sha256']=scaling.assembly.digest(folder/'solve.log')
                scaling.save(result,root/'summary.json')
    result['passed']=True
    scaling.save(result,root/'summary.json')


if __name__=='__main__':
    main()
