"""Reconcile current raw paths against complete captured manifests and explicit eviction receipts."""
from pathlib import Path
import json,hashlib,time
b=Path(__file__).resolve().parent;out=b/'materialization-catalog.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
receipts=[]
for p in sorted((b/'archives').glob('*-materialization.json')):
 d=json.loads(p.read_text());assert d['status']=='evicted';receipts.append((p,d))
archives=[]
for p in sorted((b/'archives').glob('*.json')):
 d=json.loads(p.read_text())
 if not isinstance(d,dict):continue # Probe outputs can be JSON lists, not archive receipts.
 if not {'verified_members','archive','source_manifest','source_manifest_sha256','work'}<=set(d):continue
 w=Path(d['work']);archive=Path(d['archive']);manifest=Path(d['source_manifest']);assert archive.is_file() and archive.stat().st_size==d['archive_bytes'];assert sha(manifest)==d['source_manifest_sha256']
 expected={row['path']:row for row in json.loads(manifest.read_text())['files']};assert len(expected)==d['verified_members'];evicted={};used=[]
 for rp,rd in receipts:
  if Path(rd['work'])!=w:continue
  assert rd['archive_sha256']==d['archive_sha256'] and rd['source_manifest_sha256']==d['source_manifest_sha256'];assert Path(rd['archive'])==archive
  for rel,row in rd['selected'].items():
   assert rel not in evicted and rel in expected;assert row['sha256']==expected[rel]['sha256'] and row['bytes']==expected[rel]['bytes'];evicted[rel]=row
  used.append(dict(receipt=str(rp),sha256=sha(rp),restore_command=rd['restore_command'],selected_members=len(rd['selected'])))
 actual={str(p.relative_to(w)):p for p in w.rglob('*') if p.is_file()};assert set(actual)<=set(expected),'Unexpected new files in completed dataset'
 missing=set(expected)-set(actual);assert missing==set(evicted),'Missing paths do not exactly match explicit receipts'
 for rel,present in actual.items():assert not present.is_symlink() and present.stat().st_size==expected[rel]['bytes']
 archives.append(dict(work=str(w),archive_receipt=str(p),archive_receipt_sha256=sha(p),archive=str(archive),archive_sha256_from_previously_decoded_verification=d['archive_sha256'],manifest=str(manifest),manifest_sha256=d['source_manifest_sha256'],original_members=len(expected),currently_expanded_members=len(actual),currently_missing_members=len(missing),missing_logical_bytes=sum(expected[n]['bytes'] for n in missing),restoration_receipts=used,missing_paths_exactly_accounted=True))
assert len(archives)==7
report=dict(passed=True,observed_unix=time.time(),studies=archives,scope='Current filesystem inventory reconciled against complete original manifests and nonoverlapping explicit materialization receipts. All missing paths exactly accounted; every retained file size checked. Archive bytes were independently decoded/SHA-verified at creation; this inventory review checks current archive existence/size and receipt binding, does NOT rehash/redecode every archive or retained field.',source_sha256=sha(Path(__file__)))
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([dict(work=Path(d['work']).name,original=d['original_members'],expanded=d['currently_expanded_members'],missing=d['currently_missing_members']) for d in archives],indent=2))
