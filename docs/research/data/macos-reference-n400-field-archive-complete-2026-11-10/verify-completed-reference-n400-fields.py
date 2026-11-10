"""Independently decode every archived completed reference N400 field."""
from pathlib import Path
import json,hashlib,subprocess,tarfile,re
b=Path(__file__).resolve().parent
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify():
 manifest=b.parents[1]/'docs/research/data/macos-kinematic-fine-n400-physics-2026-11-10/raw-manifest.json';m=json.loads(manifest.read_text());w=Path(m['local_root']);expected={r['path']:r for r in m['files'] if re.fullmatch(r'results/result_\d+\.vtu',r['path']) and int(Path(r['path']).stem.split('_')[-1])<12800};assert len(expected)==1200
 assert {int(Path(x).stem.split('_')[-1]) for x in expected}==set(range(11600,12800))
 final=next(r for r in m['files'] if r['path']=='results/result_12800.vtu');assert sha(w/final['path'])==final['sha256']
 receipts=[];covered={}
 for p in sorted((b/'archives/reference-kinematic-elastic-s24-l1-n400-nu0-completed-fields-through12799-chunks').glob('*.json')):
  r=json.loads(p.read_text());assert r['status']=='evicted' and Path(r['work'])==w and Path(r['source_manifest'])==manifest and r['source_manifest_sha256']==sha(manifest)
  a=Path(r['archive']);assert a.stat().st_size==r['archive_bytes'] and sha(a)==r['archive_sha256']
  proc=subprocess.Popen(['zstd','-q','-d','-c',str(a)],stdout=subprocess.PIPE);seen=set()
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
   for member in tar:
    rel=member.name;assert member.isfile() and rel in r['selected'] and rel not in covered and rel not in seen
    row=expected[rel];assert row['bytes']==member.size==r['selected'][rel]['bytes'];assert row['sha256']==r['selected'][rel]['sha256']==hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest();assert not (w/rel).exists();seen.add(rel)
    covered[rel]=dict(row,materialization='archived',archive=str(a),archive_sha256=r['archive_sha256'],restoration_receipt=str(p))
  proc.stdout.read();assert proc.wait()==0 and seen==set(r['selected']);receipts.append(str(p))
 assert set(covered)==set(expected)
 return dict(passed=True,files=list(covered.values()),receipts=receipts,manifest_sha256=sha(manifest),scope='Complete reference N400 fields11600..12799 restored by archive receipts; final12800 retained and SHA checked')
if __name__=='__main__':
 result=verify();(b/'reference-n400-fields-archive-verification.json').write_text(json.dumps(result,indent=2)+'\n');print('Verified',len(result['files']),'members in',len(result['receipts']),'archives')
