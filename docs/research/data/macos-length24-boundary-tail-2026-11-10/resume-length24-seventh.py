from pathlib import Path
import subprocess,json,shutil,os,signal,time,runpy
b=Path(__file__).resolve().parent;p=b/'length24-capacity-hold-sixth.json';h=json.loads(p.read_text());pid=h['pid'];out=b/'length24-capacity-hold-sixth-resume.json';assert not out.exists()
raw=subprocess.check_output(['ps','-p',str(pid),'-o','pgid=,state=,command='],text=True).strip();group,state,cmd=raw.split(None,2)
assert int(group)==h['pgid']==pid and cmd==h['command'] and 'T' in state
free=shutil.disk_usage(b).free;assert free>23*2**30
now=time.time();os.killpg(pid,signal.SIGCONT)
out.write_text(json.dumps(dict(pid=pid,command=cmd,resumed_unix=now,hold_seconds=now-h['start_unix'],free_bytes=free,hold_receipt=str(p),monitor=str(b/'monitor-length-capacity-seventh.py'),scope='Same process resumed; original20GiB controller floor,22GiB monitor hold,23GiB resume threshold unchanged. Tail compressor excludes prior archived prefix.'),indent=2)+'\n')
print('resumed',pid,'hold_seconds',now-h['start_unix'],flush=True)
try:runpy.run_path(str(b/'monitor-length-capacity-seventh.py'),run_name='__main__')
except BaseException as error:
 raw=subprocess.run(['ps','-p',str(pid),'-o','pgid=,state=,command='],capture_output=True,text=True).stdout.strip()
 if raw:
  group,state,cmd=raw.split(None,2)
  assert int(group)==pid and cmd==h['command']
  if 'T' not in state:os.killpg(pid,signal.SIGSTOP)
 (b/'length24-seventh-monitor-failure.json').write_text(json.dumps(dict(error=repr(error),observed_unix=time.time(),process=raw),indent=2)+'\n')
 raise
