"""Capture completed S24 boundary proof and immutable active-controller sources."""
import importlib.util,json,os,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107');storage=Path('/mnt/d/EONSim-prod48-20261107')
os.sched_setaffinity(0,{9})
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-production-followups.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
snapshot=work/'continuation-snapshot-054b64a';snapshot.mkdir();states={}
for name in ['elastic-execution-s24-current.json','womersley-vector-boundary-current.json','elastic-geometry-eonsim-current.json',
    'elastic-geometry-svfsi-current.json','womersley-alpha1-current.json','elastic-budget-eonsim-queue-current.json','elastic-budget-svfsi-queue-current.json']:
    value=(work/name).read_text();states[name]=json.loads(value);(snapshot/name).write_text(value)
assert states['elastic-execution-s24-current.json']['state']=='running'
assert states['elastic-execution-s24-current.json']['job']=='continued-warmup'
assert states['womersley-vector-boundary-current.json']['state']=='waiting_for_natural_warmup_exit'
summary=dict(snapshot_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),states=states,
    scope='S24 three-step boundary comparison is completed. Long S24 continuation and fluid boundary handoff are in progress; their states here are dated snapshots, never completion claims.')
(snapshot/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
probe=work/'elastic-direct-boundary-s24-400-054b64a';assert json.loads((probe/'report.json').read_text())['complete']
files=list(probe.rglob('*'))+list(snapshot.iterdir())+[work/'elastic-direct-boundary-s24-current.json',work/'alpha1-fine-storage-054b64a.json']
for name in ['elastic-execution-s24-400-054b64a','womersley-vector-boundary-054b64a']:
    folder=work/name
    files+=list((folder/'source').rglob('*'))+[folder/n for n in ['original-controller.py','source-hashes.json','process-identities.json']]
folder=work/'elastic-execution-s24-400-054b64a'
files+=[folder/n for n in ['planned-interruption.json','original-worker-status.json','boundary-probe-command.json','boundary-probe.log']]
original=storage/'elastic-s24-l1-n400-ramp16-c32'
files+=[original/n for n in ['case.json','fluid.msh','solid.msh','geometry.json','eonsim','provenance.json','original-controller.py','eonsim-warmup-command.json','eonsim-warmup.log']]
files+=list((original/'warmup').rglob('*'))
transfer=json.loads((folder/'planned-interruption.json').read_text());files+=list((original/'checkpoint'/transfer['generation']).iterdir())
target=storage/'elastic-s24-l1-n400-ramp16-c32-mumps_chord-m400'
files+=[target/n for n in ['case.json','fluid.msh','solid.msh','geometry.json','eonsim','execution-source.json']]
files+=list((target/'checkpoint'/transfer['generation']).iterdir())
c.capture('execution-continuations-2026-11-08',files,[snapshot/'summary.json',probe/'report.json',Path(__file__)])
