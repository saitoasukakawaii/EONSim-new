"""Compress only immutable accepted dense outputs; original capacity monitor retains signal authority."""
from pathlib import Path
import json,re,subprocess,time
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-tautime-n400';out=b/'fsi-tau-compression-monitor.json';assert not out.exists();last_cutoff=23200;events=[]
while True:
 p=w/'dense/solve.log';last=23200
 if p.exists():
  raw=p.read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fsi_step=(\d+) ',raw,re.M)))
  if steps:
   assert steps==list(range(23201,steps[-1]+1));last=steps[-1]
 held=(b/'fsi-tau-control-capacity-hold-second.json').exists();terminal=(w/'completion.json').exists() or (w/'failure.json').exists()
 if last-1-last_cutoff>=64 or ((held or terminal or last==25600) and last-1>last_cutoff):
  cutoff=last-1
  r=subprocess.run(['python3',str(b/'compress-fsi-tau-accepted-dense.py'),'--work',str(w),'--through',str(cutoff)],capture_output=True,text=True)
  events.append(dict(observed_unix=time.time(),through=cutoff,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
  out.write_text(json.dumps(dict(status='batch-finished' if r.returncode==0 else 'compression-failed',events=events,last_complete_step=last),indent=2)+'\n')
  if r.returncode:raise RuntimeError('Immutable compression failed; original capacity protection remains active')
  last_cutoff=cutoff
 state=dict(observed_unix=time.time(),status='held-or-terminal' if held or terminal else 'monitoring',last_complete_step=last,through=last_cutoff,events=events)
 out.write_text(json.dumps(state,indent=2)+'\n')
 if held or terminal:print(state['status'],last,flush=True);break
 time.sleep(5)
