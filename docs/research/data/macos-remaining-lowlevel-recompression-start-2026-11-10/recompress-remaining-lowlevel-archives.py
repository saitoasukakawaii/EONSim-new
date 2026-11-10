"""Sequential lossless re-encoding of the four zstd9 fineN1600 boundary collections and zstd3 native reference collection."""
from pathlib import Path
import json,subprocess,time
b=Path(__file__).resolve().parent;out=b/'remaining-lowlevel-recompression-progress.json';assert not out.exists();results=[]
selection=json.loads((b/'remaining-lowlevel-recompression-selection.json').read_text())
for item in selection:
 for rp in sorted((b/'archives'/item['name']).glob('*.json')):
  start=time.time();p=subprocess.run(['python3',str(b/'recompress-remaining-lowlevel-chunk.py'),str(rp)],capture_output=True,text=True)
  results.append(dict(receipt=str(rp),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,seconds=time.time()-start))
  out.write_text(json.dumps(dict(status='running' if p.returncode==0 else 'failed-review-journal',observed_unix=time.time(),results=results),indent=2)+'\n');assert p.returncode==0,p.stderr
out.write_text(json.dumps(dict(status='complete',observed_unix=time.time(),results=results),indent=2)+'\n');print('All selected lowlevel collections processed',flush=True)
