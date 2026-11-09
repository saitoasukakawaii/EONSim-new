"""Record completed scheduler replacement, not future numerical success."""
import fcntl,importlib.util,json,os,shutil,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107');storage=Path('/mnt/d/EONSim-prod48-20261107')
spec=importlib.util.spec_from_file_location('capture',root/'build/prod48-20261107/capture-production-followups.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
with (work/'reference-diagnostic.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{23})
    snapshot=work/'segment-controller-capture-08718b9';assert not snapshot.exists();snapshot.mkdir()
    shutil.copy2(__file__,snapshot/'original-capture.py')
    states={}
    names=['womersley-segment-boundary-current.json','alpha1-fine-vector-segmented-current.json',
        'womersley-time400-a1-retry4-current.json','womersley-time400-a2-retry4-current.json','reference-nu0-s24-series-current.json']
    for name in names:
        shutil.copy2(work/name,snapshot/name);states[name]=json.loads((snapshot/name).read_text())
        assert states[name]['state'].startswith('waiting_'),(name,states[name])
    old=[work/'womersley-time400-a1-retry3-current.json',work/'womersley-time400-a2-retry3-current.json',work/'alpha1-fine-vector-current.json']
    assert all(json.loads(p.read_text())['state'].startswith('cancelled_before_') for p in old)
    directories=['segment-controller-replacement-08718b9','womersley-segment-boundary-08718b9','alpha1-fine-vector-f0422d0',
        'alpha1-fine-vector-segmented-08718b9','reference-nu0-s24-series-6f202a1']
    directories += [f'womersley-time400-a{a}-{suffix}' for a in [1,2] for suffix in ['a7a177e-attempt3','08718b9-attempt4']]
    files=old+sum((list((work/name).rglob('*')) for name in directories),[])
    for case_id in ['s24-l1-n400','s24-l0-n400','s24-l1-n200']:
        path=storage/f'reference-{case_id}-meshnu0-6f202a1'
        assert not (path/'reference').exists()
        files += [path/n for n in ['case.json','fluid.msh','solid.msh','geometry.json']]
    (snapshot/'summary.json').write_text(json.dumps(dict(snapshot_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),states=states,
        cancelled_waiters=[15446,15457,7639],running_numerical_child_preserved=5422,
        scope='Replacement of waiting controllers is complete. Main alpha2 accepted600 handoff, alpha1 fine screen, both N400 controls and reference-nu0 S24 family remain pending. No numerical qualification inferred.'),indent=2)+'\n')
    files+=list(snapshot.rglob('*'))
    capture.capture('segmented-queue-handoff-2026-11-08',files,[snapshot/'summary.json',snapshot/'original-capture.py'])
