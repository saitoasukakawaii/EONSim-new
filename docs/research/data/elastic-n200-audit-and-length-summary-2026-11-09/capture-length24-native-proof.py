"""Capture terminal L24 proof/review evidence, including a failure if one occurs."""
import fcntl,hashlib,importlib.util,json,os,shutil,time,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[2]
w=Path('/home/tfblab633/EONSim-prod48-20261107');d=Path('/mnt/d/EONSim-prod48-20261107')
p=w/'length24-native-extension-proof-4f5f26d';r=w/'length24-native-proof-review-b002c06'
c=w/'length24-native-proof-capture-98ee0f9';status=w/'length24-native-proof-capture-current.json'
name='length24-native-extension-proof-2026-11-09'
read=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def update(state,**kw):
    v=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),archive=name,**kw)
    t=status.with_suffix('.tmp');dump(t,v);t.replace(status);print(json.dumps(v),flush=True)
def alive(pid):
    try:return (Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[0] not in ('Z','X')
    except FileNotFoundError:return False
def files(folder):return [q for q in folder.rglob('*') if q.is_file() and '__pycache__' not in q.parts]
def clean_owned_scope(receipt):
    assert not receipt['remaining_scope_members']
    unit=receipt['unit']
    for q in Path('/proc').iterdir():
        if not q.name.isdigit():continue
        try:assert unit not in (q/'cgroup').read_text()
        except (FileNotFoundError,ProcessLookupError):pass
assert not c.exists() and not status.exists()
c.mkdir();shutil.copy2(__file__,c/'controller.py')
helper=root/'build/prod48-20261107/capture-ranked-external-evidence.py'
assert sha(helper)=='81dba5d266e9cde0c74f0ae8a073e54dc6075427bd583b65ddd10ea9a2e58533'
dump(c/'definition.json',dict(controller_sha256=sha(c/'controller.py'),helper_sha256=sha(helper),
    proof_definition_sha256=sha(p/'definition.json'),review_definition_sha256=sha(r/'definition.json'),
    cpu=18,nice=19,shared_guest_cpu=True,cpu_lock='elastic-ramp-queue.lock',
    capture_only_after_both_terminal_and_all_owned_scopes_empty=True,adopted=False))
try:
    update('waiting_for_terminal_proof_and_review',holds_locks=False)
    states={}
    for label,filename,expected in [('proof','length24-native-extension-proof-current.json',44437),
                                    ('review','length24-native-proof-review-current.json',44493)]:
        while True:
            value=read(w/filename);assert value['pid']==expected
            if value['state'] in ('completed','failed') and not alive(expected):states[label]=value;break
            time.sleep(10)
    while True:
        current=read(w/'elastic-n200-native1600-current.json')
        if current['state']=='completed' and not alive(current['pid']):break
        assert current['state']!='failed','Prior CPU18 owner did not complete; no resource takeover'
        time.sleep(10)
    with (w/'elastic-ramp-queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{18});os.nice(19)
        for folder in (p,r):
            for receipt in folder.glob('*.resource.json'):clean_owned_scope(read(receipt))
        definition=read(c/'definition.json')
        assert sha(p/'definition.json')==definition['proof_definition_sha256']
        assert sha(r/'definition.json')==definition['review_definition_sha256']
        raw=read(p/'immutable-inputs.json')
        for path,h in raw.items():assert sha(Path(path))==h
        copies=[]
        for label,folder in [('proof',p),('review',r)]:
            for filename in ('definition.json','plan-review.json','report.json','raw-review.json','completion.json','failure.json'):
                src=folder/filename
                if src.exists():
                    dst=c/(label+'-'+filename);shutil.copy2(src,dst);assert sha(src)==sha(dst);copies.append(dst)
        passed=all(value['state']=='completed' for value in states.values())
        if passed:
            assert read(p/'report.json')['passed'] and read(r/'raw-review.json')['passed']
            assert read(p/'completion.json')['report_sha256']==sha(p/'report.json')
            assert read(r/'completion.json')['raw_review_sha256']==sha(r/'raw-review.json')
        dump(c/'summary.json',dict(states=states,proof_and_review_passed=passed,adopted=False,full_qualification=False,
            scope='All terminal proof/review control, source, numerical fields and native current/history states plus all416 original oracle inputs. Failed attempts, if any, remain explicit. Original c32 periodic failure is not replaced. Long extension and project qualification are separate.'))
        copies.append(c/'summary.json')
        selected=sorted(set(files(p)+files(r)+files(d/p.name)+[Path(x) for x in raw]+files(c)))
        before={str(q):sha(q) for q in selected}
        spec=importlib.util.spec_from_file_location('capture',helper);cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
        update('capturing',proof_and_review_passed=passed)
        cap.capture(name,selected,copies)
        assert before=={str(q):sha(q) for q in selected}
        update('completed',proof_and_review_passed=passed,git_staging_complete=False,full_qualification=False)
except BaseException as error:
    dump(c/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise
