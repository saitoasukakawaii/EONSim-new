"""Resume the original held tau diagnostic and watch its original early/dense controller transitions."""
from pathlib import Path
import json,subprocess,shutil,time,os,signal
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-tautime-n400';hp=b/'fsi-tau-control-capacity-hold-third.json';h=json.loads(hp.read_text());out=b/'fsi-tau-control-capacity-resume-third.json';monitor=b/'fsi-tau-capacity-monitor-third.json';assert not out.exists() and not monitor.exists()
def snapshot(pid):
 p=subprocess.run(['ps','-p',str(pid),'-o','pgid=,state=,command='],capture_output=True,text=True)
 if not p.stdout.strip():return None
 g,s,c=p.stdout.strip().split(None,2);return int(g),s,c
p=snapshot(h['pid']);assert p and p[0]==h['pgid']==h['pid'] and 'T' in p[1] and p[2]==h['command']
free=shutil.disk_usage(b).free;assert free>23*2**30
now=time.time();os.killpg(h['pgid'],signal.SIGCONT)
out.write_text(json.dumps(dict(pid=h['pid'],command=h['command'],resumed_unix=now,hold_seconds=now-h['start_unix'],free_bytes=free,hold_receipt=str(hp),scope='Same original process resumed. Original24h per-stage timeout and20GiB controller floor preserved; monitor holds current original stage below22GiB.'),indent=2)+'\n');print('resumed',h['pid'],flush=True)
last_verified=None
try:
 while True:
  free=shutil.disk_usage(b).free
  if (w/'completion.json').exists() or (w/'failure.json').exists():
   monitor.write_text(json.dumps(dict(observed_unix=time.time(),status='controller-terminal',free_bytes=free),indent=2)+'\n');break
  live=json.loads((w/'live.json').read_text());pid=live['pid'];label=live['label'];assert label in ('early','dense')
  expected=' '.join(json.loads((w/label/'command.json').read_text()));p=snapshot(pid)
  if not p:
   monitor.write_text(json.dumps(dict(observed_unix=time.time(),status='awaiting-original-controller-transition',live=live,free_bytes=free),indent=2)+'\n');time.sleep(5);continue
  assert p[0]==pid and p[2]==expected and expected.startswith(str(w/'eonsim')+' ')
  assert 'T' not in p[1];last_verified=(pid,expected)
  state=dict(observed_unix=time.time(),status='monitoring',live=live,free_bytes=free)
  if free<22*2**30:
   hold=b/'fsi-tau-control-capacity-hold-fourth.json';assert not hold.exists();os.killpg(pid,signal.SIGSTOP)
   hold.write_text(json.dumps(dict(pid=pid,pgid=pid,command=expected,status='held',start_unix=time.time(),live=live,free_bytes=free,reason='Protect original20GiB controller floor; resume same process after verified capacity recovery'),indent=2)+'\n');state['status']='held-for-capacity';monitor.write_text(json.dumps(state,indent=2)+'\n');print('held',pid,label,free,flush=True);break
  monitor.write_text(json.dumps(state,indent=2)+'\n');time.sleep(5)
except BaseException as error:
 if last_verified:
  pid,expected=last_verified;p=snapshot(pid)
  if p and p[0]==pid and p[2]==expected and 'T' not in p[1]:os.killpg(pid,signal.SIGSTOP)
 (b/'fsi-tau-capacity-monitor-third-failure.json').write_text(json.dumps(dict(error=repr(error),observed_unix=time.time(),last_verified=last_verified),indent=2)+'\n');raise
