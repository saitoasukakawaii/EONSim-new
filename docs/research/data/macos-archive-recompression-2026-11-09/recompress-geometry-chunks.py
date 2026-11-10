"""Sequentially apply the validated chunk transaction to existing geometry archives."""
from pathlib import Path
import json,subprocess,time
b=Path(__file__).resolve().parent;out=b/'geometry-recompression-progress.json';assert not out.exists();results=[]
for suffix in ['-volume-chunks','-boundary-chunks']:
 for rp in sorted((b/'archives'/('elastic-s24-l1-n800-geometry48'+suffix)).glob('*.json')):
  r=json.loads(rp.read_text())
  if 'recompression' in r:
   j=json.loads(Path(r['recompression']['journal']).read_text());assert j['status']=='committed';results.append(dict(receipt=str(rp),journal=r['recompression']['journal'],saved_bytes=j['saved_bytes'],preexisting=True));continue
  start=time.time();p=subprocess.run(['python3',str(b/'recompress-archive-chunk.py'),str(rp)],capture_output=True,text=True)
  row=dict(receipt=str(rp),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,seconds=time.time()-start);results.append(row)
  out.write_text(json.dumps(dict(status='running' if p.returncode==0 else 'failed-review-journal',observed_unix=time.time(),results=results),indent=2)+'\n')
  assert p.returncode==0,p.stderr
  print(rp.parent.name,rp.name,'done',flush=True)
out.write_text(json.dumps(dict(status='complete',observed_unix=time.time(),results=results),indent=2)+'\n');print('all geometry chunks processed',flush=True)
