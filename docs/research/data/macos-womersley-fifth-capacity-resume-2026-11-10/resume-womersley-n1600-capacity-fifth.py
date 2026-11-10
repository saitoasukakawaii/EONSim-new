"""Resume the same held Womersley group; retain original timeout and disk limits."""
from pathlib import Path
import argparse,json,subprocess,time,shutil,os,signal
b=Path(__file__).resolve().parent;w=b/'alpha2-s96-l1-n1600';hp=b/'womersley-n1600-capacity-hold-fifth.json';h=json.loads(hp.read_text());execution=w.with_suffix('.execution.json')
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
def dump(path,obj):
 tmp=path.with_suffix(path.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,path)
def group():
 result=subprocess.run(['ps','-axo','pid=,ppid=,pgid=,state=,command='],text=True,capture_output=True,check=True);rows=[]
 for line in result.stdout.splitlines():
  parts=line.strip().split(None,4)
  if len(parts)==5 and int(parts[2])==h['pgid']:rows.append(dict(pid=int(parts[0]),ppid=int(parts[1]),pgid=int(parts[2]),state=parts[3],command=parts[4]))
 return rows
info=json.loads(execution.read_text());assert info['pid']==h['pid']==h['pgid']==32871 and 'exit_code' not in info
before=group();expected={x['pid']:x for x in h['members']};assert {x['pid'] for x in before}==set(expected)
for row in before:assert row['command']==expected[row['pid']]['command'] and row['ppid']==expected[row['pid']]['ppid'] and 'T' in row['state']
now=time.time();remaining=info['start_unix']+info['timeout_seconds']-now;assert remaining>0
free=shutil.disk_usage(b).free;preflight=dict(passed=True,observed_unix=now,free_bytes=free,capacity_ready=free>23*2**30,remaining_original_seconds=remaining,members=before,hold_seconds=now-h['start_unix'])
if a.check:print(json.dumps(preflight,indent=2));raise SystemExit(0)
out=b/'womersley-n1600-capacity-resume-fifth.json';monitor=b/'womersley-n1600-capacity-monitor-fifth.json';assert not out.exists() and not monitor.exists();assert preflight['capacity_ready']
leader=expected[h['pid']]['command'];os.killpg(h['pgid'],signal.SIGCONT);dump(out,dict(preflight,resumed_unix=time.time(),hold_receipt=str(hp),scope='Same original group resumed. Original whole-study86400s clock, memory and20GiB floor unchanged; preemptive hold below22GiB.'))
print('Resumed original Womersley process group',h['pgid'],flush=True)
try:
 while True:
  rows=group();free=shutil.disk_usage(b).free;info=json.loads(execution.read_text())
  if 'exit_code' in info or not rows:
   dump(monitor,dict(status='original-group-terminal-or-exiting',observed_unix=time.time(),free_bytes=free,execution=info));break
  main=next(x for x in rows if x['pid']==h['pid']);assert main['command']==leader and 'T' not in main['state']
  state=dict(status='monitoring',observed_unix=time.time(),free_bytes=free,members=rows)
  if free<22*2**30:
   hold=b/'womersley-n1600-capacity-hold-sixth.json';assert not hold.exists();os.killpg(h['pgid'],signal.SIGSTOP)
   state.update(status='held-for-capacity',start_unix=time.time(),pid=h['pid'],pgid=h['pgid'],reason='Preserve original20GiB floor; no original timeout reset');dump(hold,state);dump(monitor,state);print('Held Womersley group for capacity',flush=True);break
  dump(monitor,state);time.sleep(3)
except BaseException as error:
 rows=group();main=next((x for x in rows if x['pid']==h['pid']),None)
 if main and main['command']==leader:os.killpg(h['pgid'],signal.SIGSTOP)
 dump(b/'womersley-n1600-capacity-monitor-fifth-failure.json',dict(error=repr(error),observed_unix=time.time(),members=rows));raise
