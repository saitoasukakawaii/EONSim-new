"""Observe changing segment PIDs; preserve active solver before shared disk floor."""
from pathlib import Path
import json,subprocess,shutil,time,os,signal,re
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n1600';out=b/'fine-n1600-capacity-monitor.json';hold=b/'fine-n1600-capacity-hold.json'
assert not hold.exists()
while True:
 if (w/'completion.json').exists() or (w/'failure.json').exists():
  out.write_text(json.dumps(dict(status='controller-terminal-inspect-result',unix=time.time()))+'\n');break
 live=json.loads((w/'live.json').read_text());pid=live['pid'];ps=subprocess.run(['ps','-p',str(pid),'-o','pgid=,state=,command='],capture_output=True,text=True)
 if not ps.stdout.strip():time.sleep(2);continue
 pgid,state,cmd=ps.stdout.strip().split(None,2)
 assert int(pgid)==pid and cmd.startswith(str(w/'eonsim')+' -case case.json ') and f'-stop_after {live["target"]} ' in cmd and 'T' not in state
 free=shutil.disk_usage(b).free
 if free<21.25*2**30:
  assert json.loads((w/'live.json').read_text())==live
  os.killpg(pid,signal.SIGSTOP)
  check=subprocess.check_output(['ps','-p',str(pid),'-o','pgid=,state=,command='],text=True).strip();g,s,c=check.split(None,2);assert int(g)==pid and c==cmd and 'T' in s
  raw=(w/live['label']/'solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];hits=re.findall(rb'^fsi_step=(\d+) ',raw,re.M)
  result=dict(status='held',pid=pid,pgid=pid,command=cmd,stage=live,start_unix=time.time(),accepted_last_before_hold=int(hits[-1]) if hits else None,free_bytes=shutil.disk_usage(b).free,reason='Preserve 20GiB controller floor during dense output; original process retained, no solver/controller change.',resume='Verify same PID/command/T state then SIGCONT; record elapsed hold time.')
  hold.write_text(json.dumps(result,indent=2)+'\n');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);break
 out.write_text(json.dumps(dict(status='monitoring',unix=time.time(),stage=live,free_bytes=free),indent=2)+'\n');time.sleep(5)
