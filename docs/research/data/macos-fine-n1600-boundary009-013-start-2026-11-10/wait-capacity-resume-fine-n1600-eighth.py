from pathlib import Path
import json,os,sys,shutil,time,subprocess
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n1600';hold=b/'fine-n1600-capacity-hold-eighth.json'
assert not (b/'fine-n1600-capacity-hold-ninth.json').exists()
while True:
 r=json.loads(hold.read_text());assert 'resumed_unix' not in r
 assert not (w/'completion.json').exists() and not (w/'failure.json').exists()
 line=subprocess.check_output(['ps','-p',str(r['pid']),'-o','pgid=,state=,command='],text=True).strip();g,s,c=line.split(None,2)
 assert int(g)==r['pgid'] and 'T' in s and c==r['command']
 free=shutil.disk_usage(b).free
 (b/'fine-n1600-eighth-resume-wait.json').write_text(json.dumps(dict(status='waiting-for-capacity',pid=r['pid'],free_bytes=free,required_free_bytes=23*2**30,unix=time.time()),indent=2))
 if free>23*2**30:os.execv(sys.executable,[sys.executable,str(b/'resume-fine-n1600-eighth.py')])
 time.sleep(5)
