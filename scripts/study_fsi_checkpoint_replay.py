"""Replay a stored complete cycle to verify field compatibility across builds."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner
from study_fsi_periodic import preserve_attempt
from fsi_field_cycles import series
from analyze_fsi_space import cycle_paths,phase_paths,cycle_distance


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);a=p.parse_args()
    source=a.source.resolve();saved=json.loads((source/'periodic-result.json').read_text())
    if not saved['converged']:raise ValueError('Expected converged source')
    definition=json.loads((source/'study-definition.json').read_text());cycle=saved['metrics'][-1]['cycle']
    cfg=copy.deepcopy(saved['config']);steps=round(.1/cfg['fsi']['dt']);cfg['fsi'].update(steps=cycle*steps,checkpoint_interval=steps)
    checkpoint=None
    for generation in sorted((source/'checkpoint').glob('generation_*'),reverse=True):
        manifest=generation/'manifest'
        if manifest.exists() and int(manifest.read_text().split()[2])==(cycle-1)*steps:
            checkpoint=generation;break
    if checkpoint is None:raise ValueError('Preceding complete-cycle generation missing')
    run=Runner(a.executable,a.mpiexec,a.work,timeout=7200)
    preserve_attempt(run.work,'replay')
    for name in ('fluid.msh','solid.msh'):shutil.copyfile(source/name,run.work/name)
    run.solve('replay',cfg,definition['ranks'],['-restart',checkpoint])
    old={solid:cycle_paths(source,cycle,solid) for solid in (False,True)}
    new={solid:phase_paths(series(run.work/(f'replay_restart{(cycle-1)*steps}'+('_solid' if solid else '')+'.pvd')),cycle) for solid in (False,True)}
    errors=cycle_distance(old,new)
    result=dict(source=str(source),source_definition=definition,source_checkpoint=checkpoint.name,
                executable_sha256=hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),cycle=cycle,errors=errors,
                passed=max(errors.values())<2e-9)
    (run.work/'replay-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if not result['passed']:raise RuntimeError('Complete-cycle build compatibility failed')


if __name__=='__main__':main()
