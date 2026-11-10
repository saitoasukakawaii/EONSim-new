"""Monitor this existing length process; compress immutable frames, hold before global floor."""
from pathlib import Path
import subprocess,json,time,re,shutil,os,signal
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';pid=73679
out=b/'length-capacity-monitor-sixth.json';events=[];last_cutoff=24829
while True:
 raw=(w/'dense/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1]
 hits=re.findall(rb'^fsi_step=(\d+) time=',raw,re.M);last=int(hits[-1]) if hits else 23200
 free=shutil.disk_usage(b).free
 if last-1-last_cutoff>=64 or (last==25600 and last_cutoff<25599):
  cutoff=last-1;target=b/(w.name+f'-tail2-logged-frames-through{cutoff}-compression.json')
  assert not target.exists()
  p=subprocess.run(['python3',str(b/'compress-length24-tail-after24584.py'),'--work',str(w),'--through',str(cutoff)],capture_output=True,text=True)
  events.append(dict(unix=time.time(),through=cutoff,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
  last_cutoff=cutoff;free=shutil.disk_usage(b).free
 state=dict(observed_unix=time.time(),last_complete_step=last,free_bytes=free,through=last_cutoff,events=events,status='monitoring')
 if (w/'completion.json').exists():
  state['status']='solver-complete';out.write_text(json.dumps(state,indent=2)+'\n');print('length solver complete',flush=True);break
 ps=subprocess.run(['ps','-p',str(pid),'-o','pgid=,state=,command='],capture_output=True,text=True)
 if not ps.stdout.strip():
  state['status']='solver-ended-check-controller';out.write_text(json.dumps(state,indent=2)+'\n');print(state['status'],flush=True);break
 group,mode,cmd=ps.stdout.strip().split(None,2)
 original=json.loads((b/'length24-capacity-hold.json').read_text());assert int(group)==pid and cmd==original['command'] and 'T' not in mode
 if free<22*2**30:
  receipt=b/'length24-capacity-hold-sixth.json';assert not receipt.exists();os.killpg(pid,signal.SIGSTOP)
  hold=dict(pid=pid,pgid=pid,command=cmd,status='held',start_unix=time.time(),accepted_last_before_hold=last,free_bytes=free,reason='Length-only monitor protects 20GiB shared controller floor; current immutable frames compressed. Resume same process after further verified cleanup.',resume='Verify same PID/command/stopped state, SIGCONT; record hold duration.')
  receipt.write_text(json.dumps(hold,indent=2)+'\n');state['status']='held-for-capacity';out.write_text(json.dumps(state,indent=2)+'\n');print(state['status'],last,free,flush=True);break
 out.write_text(json.dumps(state,indent=2)+'\n');time.sleep(20)
