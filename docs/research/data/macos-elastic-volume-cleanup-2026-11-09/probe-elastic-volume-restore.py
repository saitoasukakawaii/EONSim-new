from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).resolve().parent;results=[]
for n in [400,800]:
 r=json.loads((b/'archives'/f'elastic-s24-l1-n{n}-volume-materialization.json').read_text());keys=sorted(r['selected']);chosen=[keys[0],keys[-1]];dest=b/f'elastic-n{n}-volume-restore-probe';assert not dest.exists();dest.mkdir()
 for key in chosen:(dest/key).parent.mkdir(parents=True,exist_ok=True)
 probe=dict(r,work=str(dest),selected={key:r['selected'][key] for key in chosen});rp=b/f'elastic-n{n}-volume-restore-probe.json';assert not rp.exists();rp.write_text(json.dumps(probe,indent=2)+'\n')
 p=subprocess.run(['python3',str(b/'restore-womersley-materialization.py'),str(rp)],capture_output=True,text=True);assert p.returncode==0,p.stderr
 for key in chosen:
  q=dest/key
  with q.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['selected'][key]['sha256']
 results.append(dict(n=n,receipt=str(rp),restored_members=chosen,exit_code=p.returncode,stdout=p.stdout));print(n,'restored and verified',flush=True)
(b/'elastic-volume-restoration-results.json').write_text(json.dumps(results,indent=2)+'\n')
