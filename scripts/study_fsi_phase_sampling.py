"""Check a 20-phase waveform against actual 100-phase solver output."""
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
from fsi_field_cycles import series,phase_sampling_error


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);a=p.parse_args()
    source=a.source.resolve();saved=json.loads((source/'periodic-result.json').read_text())
    if not saved['converged']:raise ValueError('Source must be periodic')
    source_definition=json.loads((source/'study-definition.json').read_text());cycle=saved['metrics'][-1]['cycle']
    cfg=copy.deepcopy(saved['config']);steps=round(.1/cfg['fsi']['dt'])
    if steps%100:raise ValueError('Require exactly aligned 100-phase output')
    cfg['fsi'].update(steps=(cycle+2)*steps,output_interval=steps//100,checkpoint_interval=steps)
    checkpoint=source/'checkpoint'/saved['checkpoint_generation']
    definition=dict(source=str(source),source_checkpoint=saved['checkpoint_generation'],source_definition=source_definition,
                    source_files_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in checkpoint.iterdir() if x.is_file()},
                    mesh_sha256={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')},
                    executable_sha256=hashlib.sha256(Path(a.executable).read_bytes()).hexdigest())
    run=Runner(a.executable,a.mpiexec,a.work,timeout=7200);provenance=run.work/'study-definition.json'
    if provenance.exists():
        if json.loads(provenance.read_text())!=definition:raise ValueError('Sampling study definition changed')
    elif any(run.work.iterdir()):raise ValueError('Fresh sampling study requires empty directory')
    else:provenance.write_text(json.dumps(definition,indent=2)+'\n')
    for name in ('fluid.msh','solid.msh'):shutil.copyfile(source/name,run.work/name)
    # A failed attempt has no success receipt; replay the same physical source.
    if not (run.work/'solver-complete.json').exists():
        preserve_attempt(run.work,'dense')
        run.solve('dense',cfg,source_definition['ranks'],['-restart',checkpoint])
        temporary=run.work/'solver-complete.tmp';temporary.write_text(json.dumps(dict(end_cycle=cycle+2))+'\n');temporary.replace(run.work/'solver-complete.json')
    if json.loads((run.work/'solver-complete.json').read_text())!={'end_cycle':cycle+2}:raise ValueError('Invalid solver completion receipt')
    result={}
    for solid in (False,True):
        entries=series(run.work/(f'dense_restart{cycle*steps}'+('_solid' if solid else '')+'.pvd'))
        scales={name:1. for name in (('velocity','displacement') if solid else ('velocity','pressure','mesh_displacement'))}
        errors=phase_sampling_error(entries,.1,(cycle+2)*.1,scales,solid)
        result.update({('solid_' if solid else 'fluid_')+k:v for k,v in errors.items()})
    receipt=dict(definition=definition,coarse_phases=20,dense_phases=100,errors=result)
    (run.work/'sampling-result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
