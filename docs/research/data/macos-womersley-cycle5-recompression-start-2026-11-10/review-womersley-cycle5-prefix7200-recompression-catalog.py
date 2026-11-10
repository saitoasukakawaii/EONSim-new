"""Reconcile only immutable Womersley cycle5 prefix receipts; no current solver states examined."""
from pathlib import Path
import json,hashlib
b=Path(__file__).resolve().parent;w=b/'alpha2-s96-l1-n1600';manifest=b/'alpha2-s96-l1-n1600-cycle5-prefix7200-before-archive.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
expected={r['path']:r for r in json.loads(manifest.read_text())['files']};covered=set();receipts=[];archives={}
assert len(expected)==800 and {r['step'] for r in expected.values()}==set(range(6401,7201))
for row in expected.values():assert sha(w/row['checkpoint_manifest'])==row['checkpoint_manifest_sha256']
for p in sorted((b/'archives/alpha2-s96-l1-n1600-cycle5-prefix7200-chunks').glob('*.json')):
 r=json.loads(p.read_text());a=Path(r['archive']);assert r['status']=='evicted' and Path(r['work'])==w and Path(r['source_manifest'])==manifest and r['source_manifest_sha256']==sha(manifest)
 assert a.is_file() and a.stat().st_size==r['archive_bytes']
 for rel,row in r['selected'].items():
  assert rel not in covered and not (w/rel).exists();assert (row['bytes'],row['sha256'])==(expected[rel]['bytes'],expected[rel]['sha256']);covered.add(rel)
 receipts.append(dict(path=str(p),sha256=sha(p)));archives[str(a)]=dict(bytes=r['archive_bytes'],sha256=r['archive_sha256'])
assert len(receipts)==20 and len(covered)==800
(b/'womersley-cycle5-prefix7200-recompression-catalog.json').write_text(json.dumps(dict(passed=True,source_manifest_sha256=sha(manifest),receipts=receipts,archives=archives,members=800,scope='Only immutable Womersley cycle5-prefix7200 HDF collection. New encoding checked by transaction full decoded tar SHA; prior members fully decoded. Full global catalog refresh pending until all re-encoding batches finish.'),indent=2)+'\n');print('20 receipts and800 immutable members reconciled')
