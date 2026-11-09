"""Honor the user's explicit stop: identity-checked project PIDs only, keep files."""
import hashlib,json,os,signal,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
W=Path('/home/tfblab633/EONSim-prod48-20261107')
D=Path('/mnt/d/EONSim-prod48-20261107')
OUT=ROOT/'build/prod48-20261107/user-stop-20261109'
EXPECTED={38880:9390530,39157:9491956,39392:9622670,40042:9960295,
40998:10452294,41187:10548551,42447:11134483,43221:11413359,
43241:11423463,43314:11444848,43315:11444932,43422:11551911,
43808:11682379,44619:12250920,46800:12588137,47776:12760033,
47914:12837864,47944:12840257,47952:12842040,47990:12868220}
WAITERS={40042,42447,43221,43241,43315,43422,43808,44619,47776,47952,47990}
ROOTS=(str(W)+'/',str(D)+'/',str(ROOT/'build/prod48-20261107')+'/')
ME=os.getpid()
events=[]

def stamp():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def proc(pid):
    try:
        p=Path('/proc')/str(pid);f=(p/'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,ppid=int(f[1]),state=f[0],start_ticks=int(f[19]),
                    argv=[os.fsdecode(a) for a in (p/'cmdline').read_bytes().split(b'\0') if a],
                    cwd=os.readlink(p/'cwd'),cgroup=(p/'cgroup').read_text().strip())
    except (FileNotFoundError,ProcessLookupError,PermissionError):return None
def bound(p):
    return any(p['cwd'].startswith(r) or any(a.startswith(r) for a in p['argv']) for r in ROOTS)
def scan():
    return [v for p in Path('/proc').iterdir() if p.name.isdigit() and int(p.name)!=ME
            and (v:=proc(int(p.name))) and v['state'] not in ('Z','X') and bound(v)]
def statuses():
    result={}
    for p in W.glob('*-current.json'):
        try:
            value=json.loads(p.read_text())
            if value.get('pid') in EXPECTED:result[str(p)]=value
        except (ValueError,OSError):pass
    return result
def send(record,sig):
    current=proc(record['pid'])
    if not current or current['start_ticks']!=record['start_ticks'] or current['state'] in ('Z','X'):return
    assert bound(current),current
    # A pidfd prevents a recycled numerical PID from receiving this signal.
    fd=os.pidfd_open(current['pid'])
    try:
        check=proc(current['pid'])
        if check and check['start_ticks']==record['start_ticks']:
            signal.pidfd_send_signal(fd,sig)
            events.append(dict(utc=stamp(),pid=current['pid'],start_ticks=current['start_ticks'],signal=signal.Signals(sig).name))
            dump(OUT/'signals.json',events)
    except ProcessLookupError:pass
    finally:os.close(fd)
def wait_empty(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if not scan():return []
        time.sleep(.2)
    return scan()

assert not OUT.exists();OUT.mkdir()
before=scan();byid={p['pid']:p for p in before}
for pid,start in EXPECTED.items():
    current=proc(pid)
    if current and current['state'] not in ('Z','X'):
        assert current['start_ticks']==start and bound(current),(pid,current)
dump(OUT/'request.json',dict(utc=stamp(),reason='User explicitly requested stopping all background calculations, after disabling the automation.',
    scope='All current EONSim-prod48 controllers, queued successors, numerical/analysis children and captures only.',
    files_deleted=False,shared_cgroups_signalled=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
dump(OUT/'before-processes.json',before);dump(OUT/'before-statuses.json',statuses())
snapshot=subprocess.run(['/usr/bin/python3',str(ROOT/'build/prod48-20261107/compact-active-studies-v7-20261109.py')],capture_output=True,text=True,timeout=20)
assert snapshot.returncode==0,snapshot.stderr
(OUT/'before-progress.json').write_text(snapshot.stdout)
for pid in sorted(WAITERS):
    if pid in byid:send(byid[pid],signal.SIGINT)
for pid in sorted(set(EXPECTED)-WAITERS):
    if pid in byid:send(byid[pid],signal.SIGINT)
left=wait_empty(20)
for sig,grace in ((signal.SIGTERM,5),(signal.SIGKILL,5)):
    if not left:break
    for record in left:send(record,sig)
    left=wait_empty(grace)
# Check every task-owned private scope seen before; never signal init.scope.
scopes=sorted({p['cgroup'].split('::',1)[1] for p in before if '/eonsim-' in p['cgroup']})
scope_members={}
for name in scopes:
    p=Path('/sys/fs/cgroup')/name.lstrip('/')/'cgroup.procs'
    scope_members[name]=[int(v) for v in p.read_text().split()] if p.exists() else []
dump(OUT/'after-statuses.json',statuses());dump(OUT/'after-processes.json',left)
report=dict(utc=stamp(),stopped=not left and not any(scope_members.values()),controllers_requested=len(EXPECTED),
    initial_processes=len(before),signals=events,remaining_processes=left,owned_scope_members=scope_members,
    prior_results_logs_checkpoints_retained=True,incomplete_archives_not_complete=True,
    numerical_qualification=False,automatic_resume_authorized=False)
dump(OUT/'report.json',report)
print(json.dumps({k:v for k,v in report.items() if k!='signals'}),flush=True)
assert report['stopped'],report
