"""Adopt verified completed alpha1 N400 archive and all five existing recovery receipts."""
from pathlib import Path
import json,hashlib,os,subprocess,time
b=Path(__file__).resolve().parent;s=b/'wom-alpha1-n400-level19-staged';r=json.loads((s/'status.json').read_text());assert r['status']=='verified-staged';original=Path(r['original']);candidate=Path(r['candidate']);t=b/'wom-alpha1-n400-recompression-adoption';assert not t.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):
 q=p.with_name(p.name+'.pending');assert not q.exists();q.write_text(json.dumps(v,indent=2)+'\n');os.replace(q,p)
assert sha(original)==r['original_sha256'] and sha(candidate)==r['candidate_sha256'];assert candidate.stat().st_size==r['candidate_bytes']<original.stat().st_size==r['original_bytes']
receipts={}
for p in (b/'archives').glob('*.json'):
 d=json.loads(p.read_text())
 if isinstance(d,dict) and d.get('archive')==str(original):
  assert d['archive_sha256']==r['original_sha256'];receipts[p]=d
assert {p.name for p in receipts}=={'alpha1-s96-l1-n400.json','alpha1-s96-l1-n400-completed-consumers-materialization.json','alpha1-s96-l1-n400-cycle3-materialization.json','alpha1-s96-l1-n400-post-budget-materialization.json','cycle3-one-member-restore-probe.json'}
# Independently decode every candidate member against the original full inventory.
import tarfile
primary=json.loads((b/'archives/alpha1-s96-l1-n400.json').read_text());manifest=Path(primary['source_manifest']);assert sha(manifest)==primary['source_manifest_sha256']
expected={x['path']:x for x in json.loads(manifest.read_text())['files']};assert len(expected)==primary['verified_members'];seen=set()
proc=subprocess.Popen(['zstd','-q','-d','-c',str(candidate)],stdout=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
 for member in tar:
  assert member.isfile() and member.name in expected and member.name not in seen
  row=expected[member.name];assert member.size==row['bytes'] and hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==row['sha256'];seen.add(member.name)
proc.stdout.read();assert proc.wait()==0 and seen==set(expected)
t.mkdir();(t/'old-receipts').mkdir()
for p in receipts:(t/'old-receipts'/p.name).write_bytes(p.read_bytes())
j=dict(r,status='verified-before-adoption',receipts=[str(p) for p in receipts],independently_verified_members=len(seen),recovery='Retain old-archive.backup and old-receipts until validated new pair; reconcile journal if interrupted.');dump(t/'journal.json',j)
os.replace(original,t/'old-archive.backup');os.replace(candidate,original)
for p,d in receipts.items():
 d=dict(d,archive_sha256=r['candidate_sha256'],recompression=dict(previous_archive_sha256=r['original_sha256'],previous_archive_bytes=r['original_bytes'],decoded_tar_sha256=r['decoded_tar_sha256'],journal=str(t/'journal.json')))
 if 'archive_bytes' in d:d['archive_bytes']=r['candidate_bytes']
 dump(p,d)
j['status']='published-awaiting-verification';dump(t/'journal.json',j)
check=subprocess.run(['python3',str(b/'review-current-archive-catalog.py')],capture_output=True,text=True);(t/'catalog.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
v=json.loads((b/'archives/alpha1-s96-l1-n400-completed-consumers-materialization.json').read_text());keys=sorted(v['selected']);selected={k:v['selected'][k] for k in [keys[0],keys[-1]]};work=t/'restore-probe';work.mkdir()
for key in selected:(work/key).parent.mkdir(parents=True,exist_ok=True)
probe=dict(v,work=str(work),selected=selected);dump(t/'restore-receipt.json',probe)
check=subprocess.run(['python3',str(b/'restore-womersley-materialization.py'),str(t/'restore-receipt.json')],capture_output=True,text=True);assert check.returncode==0,check.stderr
for key,row in selected.items():assert sha(work/key)==row['sha256']
assert sha(original)==r['candidate_sha256'];(t/'old-archive.backup').unlink();j.update(status='committed',saved_bytes=r['original_bytes']-r['candidate_bytes'],finished_unix=time.time(),restored_members=list(selected));dump(t/'journal.json',j);print(json.dumps(j,indent=2),flush=True)
