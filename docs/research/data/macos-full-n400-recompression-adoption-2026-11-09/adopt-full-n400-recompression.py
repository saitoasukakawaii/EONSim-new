"""Adopt staged archive and all three recovery receipts after geometry parent is held."""
from pathlib import Path
import json,hashlib,os,subprocess,time
b=Path(__file__).resolve().parent;s=b/'full-n400-level19-staged';r=json.loads((s/'status.json').read_text());assert r['status']=='verified-staged';original=Path(r['original']);candidate=Path(r['candidate']);t=b/'full-n400-recompression-adoption';assert not t.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):
 q=p.with_name(p.name+'.pending');assert not q.exists();q.write_text(json.dumps(v,indent=2)+'\n');os.replace(q,p)
held=json.loads((b/'geometry-recompression-publication-hold.json').read_text());state=subprocess.check_output(['ps','-p',str(held['pid']),'-o','state=,command='],text=True).strip().split(None,1);assert 'T' in state[0] and state[1]==held['command']
for p in (b/'archive-recompression').rglob('journal.json'):assert json.loads(p.read_text())['status'] in ['committed','kept-original-no-gain']
assert sha(original)==r['original_sha256'] and sha(candidate)==r['candidate_sha256'];assert candidate.stat().st_size==r['candidate_bytes']<original.stat().st_size==r['original_bytes']
receipts={}
for p in (b/'archives').glob('*.json'):
 d=json.loads(p.read_text())
 if isinstance(d,dict) and d.get('archive')==str(original):
  assert d['archive_sha256']==r['original_sha256'];receipts[p]=d
assert {p.name for p in receipts}=={'elastic-s24-l1-n400.json','elastic-s24-l1-n400-boundary-materialization.json','elastic-s24-l1-n400-volume-materialization.json'}
t.mkdir();(t/'old-receipts').mkdir()
for p in receipts:(t/'old-receipts'/p.name).write_bytes(p.read_bytes())
j=dict(r,status='verified-before-adoption',receipts=[str(p) for p in receipts],recovery='Retain old-archive.backup and old-receipts until validated new pair; reconcile journal if interrupted.');dump(t/'journal.json',j)
os.replace(original,t/'old-archive.backup');os.replace(candidate,original)
for p,d in receipts.items():
 d=dict(d,archive_sha256=r['candidate_sha256'],recompression=dict(previous_archive_sha256=r['original_sha256'],previous_archive_bytes=r['original_bytes'],decoded_tar_sha256=r['decoded_tar_sha256'],journal=str(t/'journal.json')))
 if 'archive_bytes' in d:d['archive_bytes']=r['candidate_bytes']
 dump(p,d)
j['status']='published-awaiting-verification';dump(t/'journal.json',j)
check=subprocess.run(['python3',str(b/'review-current-archive-catalog.py')],capture_output=True,text=True);(t/'catalog.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
v=json.loads((b/'archives/elastic-s24-l1-n400-volume-materialization.json').read_text());keys=sorted(v['selected']);selected={k:v['selected'][k] for k in [keys[0],keys[-1]]};work=t/'restore-probe';work.mkdir()
for key in selected:(work/key).parent.mkdir(parents=True,exist_ok=True)
probe=dict(v,work=str(work),selected=selected);dump(t/'restore-receipt.json',probe)
check=subprocess.run(['python3',str(b/'restore-womersley-materialization.py'),str(t/'restore-receipt.json')],capture_output=True,text=True);assert check.returncode==0,check.stderr
for key,row in selected.items():assert sha(work/key)==row['sha256']
assert sha(original)==r['candidate_sha256'];(t/'old-archive.backup').unlink();j.update(status='committed',saved_bytes=r['original_bytes']-r['candidate_bytes'],finished_unix=time.time(),restored_members=list(selected));dump(t/'journal.json',j);print(json.dumps(j,indent=2),flush=True)
