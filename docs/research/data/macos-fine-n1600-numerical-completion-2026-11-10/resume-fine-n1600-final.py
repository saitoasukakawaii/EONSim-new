from pathlib import Path
import json,os,signal,subprocess,shutil,time,sys
b=Path(__file__).resolve().parent;p=b/'fine-n1600-capacity-hold-thirteenth.json';r=json.loads(p.read_text());assert 'resumed_unix' not in r
assert r['stage']['label']=='dense-019' and r['stage']['target']==51200 and r['accepted_last_before_hold']==51064
required=20*2**30+1053020256*1.1+64*2**20+.25*2**30
assert shutil.disk_usage(b).free>required
line=subprocess.check_output(['ps','-p',str(r['pid']),'-o','pgid=,state=,command='],text=True).strip();g,s,c=line.split(None,2)
assert int(g)==r['pgid'] and 'T' in s and c==r['command']
os.killpg(r['pgid'],signal.SIGCONT)
r.update(resumed_unix=time.time(),free_bytes_at_resume=shutil.disk_usage(b).free,resume_threshold_bytes=required,remaining_steps=136,measured_max_frame_bytes=7742796,output_allowance_factor=1.1,finalization_allowance_bytes=64*2**20,early_hold_bytes=20.25*2**30,capacity_policy='Final stage only: measured output budget plus 10 percent, 64MiB finalization and 256MiB buffer; 20.25GiB early hold every second. Original 20GiB controller floor and numerical thresholds unchanged.');r['held_seconds']=r['resumed_unix']-r['start_unix'];p.write_text(json.dumps(r,indent=2)+'\n');print('Resumed original process',r['pid'],'after',r['held_seconds'],'seconds',flush=True)
os.execv(sys.executable,[sys.executable,str(b/'monitor-fine-n1600-capacity-final.py')])
