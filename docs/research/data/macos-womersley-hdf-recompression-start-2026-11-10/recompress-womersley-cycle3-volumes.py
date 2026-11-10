"""Sequential verified lossless re-encoding of immutable Womersley cycle3 HDF."""
from pathlib import Path
import json,subprocess,time
b=Path(__file__).resolve().parent;out=b/'womersley-cycle3-recompression-progress.json';assert not out.exists();results=[]
for rp in sorted((b/'archives/alpha2-s96-l1-n1600-cycle3-chunks').glob('*.json')):
 r=json.loads(rp.read_text())
 if 'recompression' in r:
  j=json.loads(Path(r['recompression']['journal']).read_text());assert j['status']=='committed';results.append(dict(receipt=str(rp),journal=r['recompression']['journal'],saved_bytes=j['saved_bytes'],preexisting=True));continue
 start=time.time();p=subprocess.run(['python3',str(b/'recompress-womersley-cycle3-chunk.py'),str(rp)],capture_output=True,text=True)
 results.append(dict(receipt=str(rp),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,seconds=time.time()-start))
 out.write_text(json.dumps(dict(status='running' if p.returncode==0 else 'failed-review-journal',global_catalog_refresh_pending=True,observed_unix=time.time(),results=results),indent=2)+'\n');assert p.returncode==0,p.stderr
 print(rp.name,'done',flush=True)
out.write_text(json.dumps(dict(status='complete',global_catalog_refresh_pending=True,observed_unix=time.time(),results=results),indent=2)+'\n');print('All Womersley cycle3 chunks processed',flush=True)
