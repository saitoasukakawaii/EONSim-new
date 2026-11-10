from pathlib import Path
import json,os,signal,subprocess,shutil,time,sys
b=Path(__file__).resolve().parent;p=b/'fine-n1600-capacity-hold-eighth.json';r=json.loads(p.read_text());assert 'resumed_unix' not in r
assert shutil.disk_usage(b).free>23*2**30
line=subprocess.check_output(['ps','-p',str(r['pid']),'-o','pgid=,state=,command='],text=True).strip();g,s,c=line.split(None,2)
assert int(g)==r['pgid'] and 'T' in s and c==r['command']
os.killpg(r['pgid'],signal.SIGCONT)
r.update(resumed_unix=time.time(),free_bytes_at_resume=shutil.disk_usage(b).free);r['held_seconds']=r['resumed_unix']-r['start_unix'];p.write_text(json.dumps(r,indent=2)+'\n');print('Resumed original process',r['pid'],'after',r['held_seconds'],'seconds',flush=True)
os.execv(sys.executable,[sys.executable,str(b/'monitor-fine-n1600-capacity-ninth.py')])
