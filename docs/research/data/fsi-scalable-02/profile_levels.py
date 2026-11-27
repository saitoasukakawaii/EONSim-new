"""Replay a prepared five-step case with PETSc level events, separately from formal samples."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import benchmark_fsi_block_scaling as scaling


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('seed','root','binary','mpiexec'): cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--ranks',type=int,nargs='+',required=True)
    args=cli.parse_args(); seed=json.loads(args.seed.read_text()); root=args.root.resolve()
    if not os.environ.get('SLURM_JOB_ID'): cli.error('requires a Slurm allocation')
    root.mkdir(parents=True,exist_ok=False); rows=[]
    for rank in args.ranks:
        case=next(c for c in seed['cases'] if c['ranks']==rank and c['subdivisions']==22 and c['status']=='passed')
        reference=next(r for r in case['runs'] if r['label']=='reference'); parent=Path(reference['log']).parent
        casepath=Path(case['input']); partition=parent.parent/'partition'
        for enabled in (False,True):
            folder=root/f'r{rank}-profile{int(enabled)}'; folder.mkdir(); output=folder/'solution.vtu'
            events=folder/'events.csv'; mode='mono_pressure_auto'
            command=[args.mpiexec.resolve(),'--bind-to','core','--map-by','socket','-n',str(rank),args.binary.resolve(),'-case',casepath,
                     '-partition',partition,'-output',output,'-vtu_format','ascii','-vtu_boundary','false','-fsi_threads','1',*scaling.multigrid.flags(mode)]
            if enabled: command+=['-monolithic_mg_profile_levels','true','-log_view',f':{events}:ascii_csv']
            row=dict(ranks=rank,profile=enabled,command=list(map(str,command)),status='running'); rows.append(row)
            try:
                text=scaling.block.timed_command(command,folder/'solver.log',300,row,rss_interval=.5,rss_limit=140*2**30)
                trace=scaling.assembly.history(output.with_suffix('.csv'),5,float(case['configuration']['fsi']['dt']))
                audit=scaling.multigrid.audit(text,trace,rank,mode)
                row.update(outer_iterations=audit['outer_iterations'],dofs=audit['dofs'])
                reference_trace=scaling.assembly.history(parent/'solution.csv',5,float(case['configuration']['fsi']['dt']))
                row['history_difference']=scaling.multigrid.previous.compare_history(reference_trace,trace)
                db=folder/'fields.sqlite'; scaling.spool_fields(output,rank,db)
                row['field_difference']=scaling.compare_spools(parent/'fields.sqlite',db)
                if enabled: row['event_sha256']=scaling.assembly.digest(events)
                row['status']='passed'
            except Exception as error:
                row.update(status='failed',error=str(error))
            scaling.save(dict(binary=scaling.assembly.digest(args.binary),runs=rows),root/'summary.json')


if __name__=='__main__': main()
