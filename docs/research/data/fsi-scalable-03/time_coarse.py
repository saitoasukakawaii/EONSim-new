"""Interleave already qualified coarse row budgets on the same 128-core synthetic case."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import benchmark_fsi_block_scaling as scaling


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('root',type=Path)
    cli.add_argument('profiles',type=Path,nargs=2)
    args=cli.parse_args()
    if len(os.sched_getaffinity(0))!=128 or not os.getenv('SLURM_JOB_ID'):
        cli.error('requires 128 allocated cores')
    root=args.root.resolve()
    root.mkdir(parents=True,exist_ok=False)
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    modes={}
    diagnostics=[]
    for p in args.profiles:
        seed=json.loads((p/'summary.json').read_text())
        if len(seed['runs'])!=2 or not all(r['status']=='passed' for r in seed['runs']):
            raise ValueError('Both level-event and unprofiled screens must pass')
        row=next(r for r in seed['runs'] if not r['profile'])
        command=row['command']
        if scaling.assembly.digest(Path(command[command.index('-case')-1]))!=seed['binary']:
            raise ValueError('Qualified binary has changed')
        budget=command[command.index('-monolithic_mg_coarse_rows_per_rank')+1]
        folder=Path(command[command.index('-output')+1]).parent
        modes[budget]=[v for v in command if v not in ('-pc_plan_report','-solver_report','-linear_report')]
        diagnostics.append(dict(path=str(p/'summary.json'),sha256=scaling.assembly.digest(p/'summary.json'),
                                binary=seed['binary'],reference=str(folder)))
    if len(modes)!=2:
        raise ValueError('Choose two distinct row budgets')
    def shared(cmd):
        filtered=cmd.copy()
        for opt in ('-output','-monolithic_mg_coarse_rows_per_rank'):
            i=filtered.index(opt)
            del filtered[i:i+2]
        return filtered
    first,second=list(modes.values())
    if shared(first)!=shared(second):
        raise ValueError('Layout, inputs or other solver options differ')
    reference=Path(diagnostics[0]['reference'])
    case=Path(first[first.index('-case')+1])
    part=Path(first[first.index('-partition')+1])
    inputs={str(p):scaling.assembly.digest(p) for p in [case,part/'manifest.yaml',*(part/f'rank_{i}.h5' for i in range(128))]}
    dt=json.loads(case.read_text())['fsi']['dt']
    history=scaling.assembly.history(reference/'solution.csv',5,dt)
    stepdb=root/'reference-step.sqlite'
    scaling.spool_fields(reference/'solution_step5.vtu',128,stepdb)
    result=dict(job=os.environ['SLURM_JOB_ID'],affinity=sorted(os.sched_getaffinity(0)),inputs=inputs,
                diagnostics=diagnostics,runs=[],passed=False)
    for repeat in range(4):
        order=list(modes) if repeat%2==0 else list(reversed(modes))
        for budget in order:
            folder=root/f'r{repeat}-q{budget}'
            folder.mkdir()
            command=modes[budget].copy()
            command[command.index('-output')+1]=str(folder/'solution.vtu')
            row=dict(repeat=repeat,kind='timed' if repeat else 'warmup',budget=budget,command=command,log=str(folder/'solve.log'))
            result['runs'].append(row)
            try:
                text=scaling.block.timed_command(command,folder/'solve.log',300,row,rss_interval=.2,rss_limit=140*2**30)
                if 'status=success' not in text or 'status=failed' in text:
                    raise ValueError('Solver did not accept the window')
                row['core_hours']=128*row['wall_seconds']/3600
                row['history_difference']=scaling.assembly.compare_history(history,scaling.assembly.history(folder/'solution.csv',5,dt))
                for stem,db in [('solution',reference/'fields.sqlite'),('solution_step5',stepdb)]:
                    actual=folder/(stem+'.sqlite')
                    scaling.spool_fields(folder/(stem+'.vtu'),128,actual)
                    row[stem+'_difference']=scaling.compare_spools(db,actual)
                row['log_sha256']=scaling.assembly.digest(folder/'solve.log')
                row['status']='passed'
            except Exception as error:
                row.update(status='failed',error=str(error))
                raise
            finally:
                scaling.save(result,root/'summary.json')
    result['medians']={b:statistics.median(r['wall_seconds'] for r in result['runs'] if r['budget']==b and r['repeat']) for b in modes}
    result['passed']=True
    scaling.save(result,root/'summary.json')


if __name__=='__main__':
    main()
