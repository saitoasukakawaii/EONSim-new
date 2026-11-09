"""One production job in a private cgroup-v2 scope, including nested MPI sessions."""
import json, os, re, signal, subprocess, time
from pathlib import Path
LIMIT=2*1024**3
def available():
    return int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def members(group):
    try:return [int(x) for x in (group/'cgroup.procs').read_text().split()]
    except FileNotFoundError:return []
def run(command,cwd,log,env,unit,timeout):
    """Caller owns CPU/memory-admission locks. Failures propagate after scope cleanup."""
    assert re.fullmatch(r'eonsim-[a-z0-9-]+-'+str(os.getpid())+r'\.scope',unit)
    assert available()>10*1024**3,'Need10GiB available before admitting this2GiB job'
    group=Path('/sys/fs/cgroup')/f'user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice'/unit
    assert not group.exists(),'Never attach to an existing scope'
    cmd=['/usr/bin/systemd-run','--user','--scope','--quiet','--unit='+unit,'--property=MemoryMax=2G','--property=MemorySwapMax=0',*map(str,command)]
    receipt=log.with_suffix('.resource.json')
    record=dict(command=cmd,cwd=str(cwd),unit=unit,memory_max_bytes=LIMIT,memory_swap_max_bytes=0,timeout_seconds=timeout,
        peak_observed_bytes=0,minimum_available_bytes=available(),scope_seen=False,cleanup=[])
    dump(receipt,record);start=time.monotonic();p=None;failure=None
    try:
        with log.open('x') as stream:
            p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            record['launcher_pid']=p.pid;dump(receipt,record)
            while p.poll() is None:
                if time.monotonic()-start>timeout:raise TimeoutError('Predeclared job time limit exceeded')
                free=available();record['minimum_available_bytes']=min(record['minimum_available_bytes'],free)
                if free<8*1024**3:raise MemoryError('Global available memory below8GiB')
                if group.exists():
                    try:
                        ready = (group/'memory.max').read_text().strip()==str(LIMIT) and (group/'memory.swap.max').read_text().strip()=='0'
                        if not ready:
                            if record['scope_seen'] or time.monotonic()-start>5:
                                raise RuntimeError('Hard memory controls not established or changed')
                            time.sleep(.05)
                            continue
                        record['scope_seen']=True;record['peak_observed_bytes']=max(record['peak_observed_bytes'],int((group/'memory.peak').read_text()))
                        record['memory_events']=(group/'memory.events').read_text()
                    except FileNotFoundError:pass
                time.sleep(.2)
            if p.returncode:raise subprocess.CalledProcessError(p.returncode,cmd)
            if members(group):raise RuntimeError('Launcher completed but scope still contains live processes')
            assert record['scope_seen'],'Job exited before hard memory control was observed'
    except BaseException as error:
        failure=error;record['error']=str(error)
        # The cgroup contains the study driver and all nested MPI sessions.
        # Signal only this newly created unit, never a shared slice or user service.
        for sig,grace in [('SIGINT',5),('SIGTERM',2),('SIGKILL',5)]:
            before=members(group)
            if not before:break
            q=subprocess.run(['/usr/bin/systemctl','--user','kill','--kill-whom=all','--signal='+sig,unit],capture_output=True,text=True,timeout=10)
            record['cleanup'].append(dict(signal=sig,members_before=before,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
            deadline=time.monotonic()+grace
            while members(group) and time.monotonic()<deadline:time.sleep(.05)
        if p is not None and p.poll() is None:
            # systemd-run can fail before it creates the private scope; only
            # its own still-live PID is owned in that case.
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    finally:
        record.update(returncode=p.returncode if p is not None else None,wall_seconds=time.monotonic()-start,remaining_scope_members=members(group))
        dump(receipt,record)
    if record['remaining_scope_members']:raise RuntimeError('Private scope cleanup incomplete: '+str(record['remaining_scope_members'])) from failure
    if failure is not None:raise failure
    return record
