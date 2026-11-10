"""Reconcile immutable length boundary prefix with fully decoded archives."""
from pathlib import Path
import json,hashlib,subprocess,tarfile
b=Path(__file__).resolve().parent
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify():
 manifest=b/'reference-native-n800-dual-path-before-archive.json';m=json.loads(manifest.read_text());w=Path(m['work']);expected={r['path']:r for r in m['files']};assert len(expected)==4697
 receipts=[];covered={}
 for p in sorted((b/'archives/reference-native-n800-dual-path-chunks').glob('*.json')):
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
 return dict(passed=True,files=list(covered.values()),receipts=receipts,manifest_sha256=sha(manifest),scope='2398 completed native field values plus2299 hardlink aliases archived as4697 independent regular-file restoration paths; unique allocated bytes counted once')
if __name__=='__main__':
 result=verify();(b/'reference-native-n800-dual-path-verification.json').write_text(json.dumps(result,indent=2)+'\n');print('Verified',len(result['files']),'members in',len(result['receipts']),'archives')
