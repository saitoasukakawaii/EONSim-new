"""Create an explicit continuation branch after a passed same-state option probe.

This copies only a complete selected generation, its exact mesh/partition and
frozen executable. It never changes the source study or starts a numerical job.
The original incomplete attempt remains in its own directory. Resume the new
study explicitly with the recorded execution flags and physical definition.
"""
import argparse,hashlib,json,math,shutil
from pathlib import Path

OPTIONS={'standard':[],'coo':['-fluid_coo'],'chord':['-snes_lag_jacobian','-2'],
         'coo_chord':['-fluid_coo','-snes_lag_jacobian','-2']}
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--study',type=Path,required=True);p.add_argument('--probe',type=Path,required=True)
p.add_argument('--mode',choices=OPTIONS,required=True);p.add_argument('--work',type=Path,required=True)
p.add_argument('--phases',type=int,help='Explicit new phase-save count; only warmup checkpoints are supported')
a=p.parse_args();source=a.study.resolve();probe=a.probe.resolve();out=a.work.resolve()
if out.parent!=source.parent or out==source:raise ValueError('Destination must be a distinct sibling study')
if out.exists():raise ValueError('Continuation destination already exists')
record=json.loads(probe.read_text());definition=json.loads((source/'definition.json').read_text())
if (record['source_study']!=str(source) or record['definition']!=definition or
        not record.get('complete') or record['requested_steps']<3 or record['field_tolerance']!=2e-9):
    raise ValueError('Need a complete matching three-step option probe')
if sha(probe.parent/'original-probe.py')!=record['helper_sha256']:raise ValueError('Probe helper provenance changed')
selected={r['mode']:r for r in record['runs']}
for mode in {'standard',a.mode}:
    run=selected[mode];error=run['maximum_field_difference']
    if run['state']!='passed' or not math.isfinite(error) or not 0<=error<2e-9:
        raise ValueError('Requested execution mode has not passed the field check')
options=OPTIONS[a.mode]
command=selected[a.mode]['command']
expected_tail=options+(['-partition',str(source/'parts')] if definition['ranks']>1 else [])
if command[command.index('-solver_report')+1:]!=expected_tail:raise ValueError('Probe command does not match the requested mode')
if '-snes_lag_jacobian' in options and not definition['schur']:raise ValueError('Chord requires preassembled Schur Jacobian')
if sha(source/'eonsim')!=definition['executable_sha256']:raise ValueError('Source executable changed')
mesh_hash=(source/'mesh-sha256.txt').read_text().strip()
if sha(source/'fluid.msh')!=mesh_hash:raise ValueError('Source mesh changed')
generation=record['source_generation']
if Path(generation).name!=generation:raise ValueError('Invalid checkpoint generation')
checkpoint=source/'checkpoint'/generation
hashes={path.name:sha(path) for path in checkpoint.iterdir() if path.is_file()}
if hashes!=record['source_checkpoint_hashes']:raise ValueError('Source checkpoint differs from the tested state')
manifest=(checkpoint/'manifest').read_text().split()
step=record['source_step'];dt=definition['period']/definition['steps_per_cycle']
if (len(manifest)!=5 or manifest[0]!='EONSim_checkpoint_v3' or int(manifest[1])!=definition['ranks'] or
        int(manifest[2])!=step or abs(float(manifest[3])-step*dt)>1e-10):
    raise ValueError('Checkpoint clock/rank differs from the probe')
if step>definition['warmup']*definition['steps_per_cycle']:
    raise ValueError('This bounded fork copies a warmup state only; later forks need complete phase-history handling')
if a.phases is not None:
    if a.phases<4 or definition['steps_per_cycle']%a.phases:
        raise ValueError('New phase count must divide the unchanged steps per cycle')
    definition['phases']=a.phases
if options:definition['solver_options']=options
else:definition.pop('solver_options',None)

out.mkdir();copied={}
for name in ('eonsim','fluid.msh','mesh-sha256.txt'):
    shutil.copy2(source/name,out/name);copied[name]=sha(source/name)
    if sha(out/name)!=copied[name]:raise ValueError('Copied study input differs')
if definition['ranks']>1:
    shutil.copytree(source/'parts',out/'parts')
    for path in (source/'parts').rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(source);digest=sha(path);copied[relative.as_posix()]=digest
        if sha(out/relative)!=digest:raise ValueError('Copied partition differs')
shutil.copytree(checkpoint,out/'checkpoint'/generation)
for name,digest in hashes.items():
    if sha(out/'checkpoint'/generation/name)!=digest:raise ValueError('Copied accepted history differs')
shutil.copy2(probe,out/'execution-probe.json')
if sha(out/'execution-probe.json')!=sha(probe):raise ValueError('Copied probe differs')
shutil.copy2(__file__,out/'original-fork.py')
(out/'definition.json').write_text(json.dumps(definition,indent=2)+'\n')
origin=dict(source_study=str(source),source_definition=json.loads((source/'definition.json').read_text()),
    source_definition_sha256=sha(source/'definition.json'),checkpoint_generation=generation,
    accepted_step=step,checkpoint_sha256=hashes,copied_inputs_sha256=copied,
    selected_mode=a.mode,solver_options=options,probe_sha256=sha(probe),
    fork_helper_sha256=sha(Path(__file__)),
    scope='New execution-policy study from a preserved complete accepted state; original study unchanged; no solve yet')
(out/'checkpoint-source.json').write_text(json.dumps(origin,indent=2)+'\n')
(out/'checkpoint/current').write_text('EONSim_checkpoint_v3 '+generation+'\n')
print(json.dumps(dict(work=str(out),accepted_step=step,mode=a.mode,definition=definition,solve_started=False)))
