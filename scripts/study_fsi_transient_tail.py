"""Extend a converged periodic state to estimate its remaining transient.

Three equal blocks measure decay, rather than treating an adjacent-cycle
threshold as an asymptotic error bound. The geometric-tail estimate is empirical
and conditional on the measured contraction continuing; it is not a proof.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner
from study_fsi_periodic import preserve_attempt
from fsi_field_cycles import series
from analyze_fsi_space import cycle_paths,phase_paths,cycle_distance


def tail_estimate(changes):
    if len(changes)!=3 or any(r.keys()!=changes[0].keys() for r in changes):raise ValueError('Three complete decay blocks required')
    result={}
    for field in changes[0]:
        values=[r[field] for r in changes]
        if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Invalid transient difference')
        if max(values)==0:result[field]=dict(contraction=0.,remaining_at_source=0.);continue
        if min(values[:-1])<=0:raise ValueError('Cannot estimate contraction from a zero preceding difference')
        q=max(values[1]/values[0],values[2]/values[1])
        if q>=.8:raise ValueError('Transient decay not resolved; increase block length')
        # Sum measured block changes plus the conditional unobserved geometric tail.
        result[field]=dict(contraction=q,remaining_at_source=sum(values)+values[-1]*q/(1-q))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--block-cycles',type=int,default=10)
    a=p.parse_args()
    if a.block_cycles<3:raise ValueError('At least three cycles per decay block required')
    source=a.source.resolve();receipt=json.loads((source/'periodic-result.json').read_text())
    if not receipt['converged']:raise ValueError('Source must have passed periodic convergence')
    source_definition=json.loads((source/'study-definition.json').read_text())
    cycle=receipt['metrics'][-1]['cycle'];cfg=copy.deepcopy(receipt['config']);steps=round(.1/cfg['fsi']['dt'])
    checkpoint=source/'checkpoint'/receipt['checkpoint_generation']
    definition=dict(source=str(source),source_checkpoint=receipt['checkpoint_generation'],source_definition=source_definition,
                    source_files_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in checkpoint.iterdir() if x.is_file()},
                    mesh_sha256={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')},
                    executable_sha256=hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),block_cycles=a.block_cycles)
    run=Runner(a.executable,a.mpiexec,a.work,timeout=14400);definition_file=run.work/'study-definition.json'
    if definition_file.exists():
        if json.loads(definition_file.read_text())!=definition:raise ValueError('Transient study definition changed')
    elif any(run.work.iterdir()):raise ValueError('Fresh transient study requires an empty work directory')
    else:definition_file.write_text(json.dumps(definition,indent=2)+'\n')
    for name in ('fluid.msh','solid.msh'):shutil.copyfile(source/name,run.work/name)
    previous={solid:cycle_paths(source,cycle,solid) for solid in (False,True)}
    changes=[];blocks=[]
    cfg['fsi']['checkpoint_interval']=steps
    for block in range(1,4):
        end=cycle+block*a.block_cycles;start=end-a.block_cycles
        cfg['fsi']['steps']=end*steps;label=f'block{block}'
        block_checkpoint=run.work/(label+'-checkpoint');block_receipt=run.work/(label+'-receipt.json')
        if block_receipt.exists():
            saved=json.loads(block_receipt.read_text());generation=saved['generation']
        else:
            preserve_attempt(run.work,label)
            run.solve(label,cfg,source_definition['ranks'],['-restart',checkpoint,'-checkpoint',block_checkpoint])
            generation=(block_checkpoint/'current').read_text().split()[1]
            saved=dict(generation=generation,end_cycle=end)
            temporary=block_receipt.with_suffix('.tmp');temporary.write_text(json.dumps(saved,indent=2)+'\n');temporary.replace(block_receipt)
        checkpoint=block_checkpoint/generation
        current={solid:phase_paths(series(run.work/(f'{label}_restart{start*steps}'+('_solid' if solid else '')+'.pvd')),end) for solid in (False,True)}
        delta=cycle_distance(previous,current);changes.append(delta);previous=current;blocks.append(saved)
        print(json.dumps(dict(block=block,end_cycle=end,change=delta)),flush=True)
    result=dict(definition=definition,blocks=blocks,block_changes=changes,estimate=tail_estimate(changes),
                limitation='Empirical geometric decay extrapolation, not a rigorous asymptotic bound')
    (run.work/'transient-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
