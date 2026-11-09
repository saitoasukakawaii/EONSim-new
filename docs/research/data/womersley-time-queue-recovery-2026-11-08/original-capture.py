"""Archive the completed mesh-loop diagnostic and immutable queue replacement."""
import importlib.util,json,os,shutil,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
os.sched_setaffinity(0,{9})
spec=importlib.util.spec_from_file_location('capture',root/'build/prod48-20261107/capture-production-followups.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
diagnostic=work/'reference-mesh-loop-a7a177e'
assert json.loads((work/'reference-mesh-loop-current.json').read_text())['state']=='completed'
capture.capture('reference-mesh-loop-2026-11-08',list(diagnostic.rglob('*'))+[work/'reference-mesh-loop-current.json'],
                [diagnostic/'summary.json',diagnostic/'harmonic-definition.json',diagnostic/'baseline-reproduction.json',diagnostic/'definition.json'])
snapshot=work/'time400-queue-repair-a7a177e';assert not snapshot.exists();snapshot.mkdir()
shutil.copy2(__file__,snapshot/'original-capture.py')
states={};files=[]
for alpha in (1,2):
    for suffix in ('retry2','retry3'):
        name=f'womersley-time400-a{alpha}-{suffix}-current.json'
        original=work/name;shutil.copy2(original,snapshot/name)
        states[name]=json.loads((snapshot/name).read_text())
    assert states[f'womersley-time400-a{alpha}-retry2-current.json']['state']=='cancelled_before_numerical_work'
    current=states[f'womersley-time400-a{alpha}-retry3-current.json']
    assert current['state']=='waiting_for_fine_n200_producer' and not current['holds_queue_lock']
    for name in (f'womersley-time400-a{alpha}-fa9646d-attempt2',f'womersley-time400-a{alpha}-a7a177e-attempt3'):
        files.extend((work/name).rglob('*'))
for name in ('reference-mesh-nu0-current.json','elastic-mpi-restart-current.json','womersley-vector-boundary-retry2-current.json'):
    shutil.copy2(work/name,snapshot/name);states[name]=json.loads((snapshot/name).read_text())
(snapshot/'summary.json').write_text(json.dumps(dict(snapshot_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),states=states,
    scope='N400 successors remain waiting, no trajectory started. Corrected real CLI checks are complete. Reference-nu0 and MPI are running snapshots only.'),indent=2)+'\n')
cli=work/'time400-cli-review-a7a177e';assert json.loads((cli/'summary.json').read_text())['passed']
shutil.copy2(cli/'summary.json',snapshot/'cli-checks.json')
files.extend(cli.rglob('*'));files.extend(snapshot.rglob('*'))
capture.capture('womersley-time-queue-recovery-2026-11-08',files,[snapshot/'summary.json',snapshot/'cli-checks.json',snapshot/'original-capture.py'])
