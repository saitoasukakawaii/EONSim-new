"""Reconcile only terminal fine N1600 length24 tail volume receipts; no running length-reader paths examined."""
from pathlib import Path
import json,hashlib
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';manifest=b/'length24-volumes-tail-through25349-before-archive.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
expected={r['path']:r for r in json.loads(manifest.read_text())['files']};covered=set();receipts=[];archives={}
full={r['path']:r for r in json.loads((b.parents[1]/'docs/research/data/macos-elastic-length24-n800-2026-11-09/raw-manifest.json').read_text())['files']}
assert all(rel in full and (row['bytes'],row['sha256'])==(full[rel]['bytes'],full[rel]['sha256']) for rel,row in expected.items())
for p in sorted((b/'archives/elastic-s24-l1-n800-length24-volume-tail-through25349-chunks').glob('*.json')):
 r=json.loads(p.read_text());a=Path(r['archive']);assert r['status']=='evicted' and Path(r['work'])==w and Path(r['source_manifest'])==manifest and r['source_manifest_sha256']==sha(manifest)
 assert a.is_file() and a.stat().st_size==r['archive_bytes']
 for rel,row in r['selected'].items():
  assert rel not in covered and not (w/rel).exists();assert (row['bytes'],row['sha256'])==(expected[rel]['bytes'],expected[rel]['sha256']);covered.add(rel)
 receipts.append(dict(path=str(p),sha256=sha(p)));archives[str(a)]=dict(bytes=r['archive_bytes'],sha256=r['archive_sha256'])
assert len(receipts)==53 and len(covered)==1530
(b/'length24-tail-recompression-catalog.json').write_text(json.dumps(dict(passed=True,source_manifest_sha256=sha(manifest),receipts=receipts,archives=archives,members=1530,scope='Only completed length24 tail volume collection. New encoding checked by transaction full decoded tar SHA; prior members fully decoded. Full global catalog refresh pending until active length audit restores no temporary files.'),indent=2)+'\n');print('53 receipts and1530 immutable members reconciled')
