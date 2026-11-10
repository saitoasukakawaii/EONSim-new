"""Current full/subset restoration catalog; no new numerical qualification or raw mutation."""
from pathlib import Path
import json,hashlib,subprocess,time
b=Path(__file__).resolve().parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
run=subprocess.run(['python3',str(b/'review-materialization-catalog-reference-diagnostics.py')],capture_output=True,text=True);assert run.returncode==0,run.stderr
base=json.loads((b/'materialization-catalog-reference-diagnostics.json').read_text());assert base['passed'] and len(base['studies'])==11
artifacts={}
for study in base['studies']:
 p=Path(study['archive']);artifacts[str(p.relative_to(b))]=dict(bytes=p.stat().st_size,sha256=study['archive_sha256_from_previously_decoded_verification'],scope='Previously decoded full archive; current existence/size and receipt/manifest bindings checked.')
new=[]
for name,manifest_name,suffixes,count,complete in [
 ('elastic-s24-l1-n800-geometry48','elastic-s24-l1-n800-geometry48-raw-before-archive.json',['-boundary-chunks','-volume-chunks'],9815,True),
 ('alpha2-s96-l1-n1600','alpha2-s96-l1-n1600-cycle3-before-archive.json',['-cycle3-chunks'],1599,False),
 ('elastic-s24-l0-n1600',str(b.parents[1]/'docs/research/data/macos-elastic-coarse-n1600-2026-11-09/raw-manifest.json'),['-boundary-chunks'],19418,True)]:
 w=b/name;manifest=b/manifest_name;m=json.loads(manifest.read_text());expected={r['path']:r for r in m['files']};assert len(expected)==count;mh=sha(manifest)
 missing={rel for rel in expected if not (w/rel).is_file()};covered=set();receipts=[]
 for suffix in suffixes:
  for rp in sorted((b/'archives'/(name+suffix)).glob('*.json')):
   r=json.loads(rp.read_text());assert r['status']=='evicted' and Path(r['work'])==w and Path(r['source_manifest'])==manifest and r['source_manifest_sha256']==mh
   archive=Path(r['archive']);assert archive.is_file() and archive.stat().st_size==r['archive_bytes']
   relarchive=str(archive.relative_to(b));assert relarchive not in artifacts
   artifacts[relarchive]=dict(bytes=archive.stat().st_size,sha256=r['archive_sha256'],scope='Previously decoded chunk; current existence/size and receipt/manifest bindings checked.')
   for rel,row in r['selected'].items():
    assert rel in missing and rel not in covered
    assert row['bytes']==expected[rel]['bytes'] and row['sha256']==expected[rel]['sha256'];covered.add(rel)
   receipts.append(dict(receipt=str(rp),sha256=sha(rp),members=len(r['selected']),restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(rp)]))
 assert missing==covered
 if name=='elastic-s24-l0-n1600':assert len(missing)==9658
 if complete:
  actual={str(p.relative_to(w)):p for p in w.rglob('*') if p.is_file() and not p.name.endswith('.compressed-pending')};assert set(actual)==set(expected)-missing
  for rel,p in actual.items():assert not p.is_symlink() and p.stat().st_size==expected[rel]['bytes']
 else:
  assert missing==set(expected)
  for row in expected.values():assert sha(w/row['checkpoint_manifest'])==row['checkpoint_manifest_sha256']
  assert {r['step'] for r in expected.values()}==set(range(3201,4800))
 new.append(dict(work=str(w),scope='Complete terminal raw inventory' if complete else 'Only immutable cycle3 internal HDF subset of unfinished study; no whole-study inventory claim',manifest=str(manifest),manifest_sha256=mh,original_members_in_scope=count,missing_members_in_scope=len(missing),missing_paths_exactly_accounted=True,restoration_receipts=receipts))
zstd_count=193+len(new[2]['restoration_receipts'])
assert len(artifacts)==zstd_count and set(artifacts)=={str(p.relative_to(b)) for p in (b/'archives').rglob('*.tar.zst')}
for p in sorted((b/'archives').glob('*.tar.gz')):
 artifacts[str(p.relative_to(b))]=dict(bytes=p.stat().st_size,sha256=sha(p),scope='Supplemental probe/reference archive hash computed now; no materialization eviction indexed here.')
assert len(artifacts)==zstd_count+3
result=dict(passed=True,observed_unix=time.time(),complete_studies=base['studies']+[new[0],new[2]],unfinished_study_subsets=[new[1]],archive_root=str(b),archive_files=artifacts,archive_bytes=sum(r['bytes'] for r in artifacts.values()),scope='13 complete study inventories plus one1599member subset reconciled.All indexed zstd receipts all bound; no missing in-scope paths unaccounted. Current review does not rehash/redecode unchanged zstd archives or all retained raw fields; their prior decoded hashes retained.3 small supplemental gzip archives hashed now. Migration still requires copied-file SHA verification before local removal and valid restoration path mapping.',source_sha256=sha(Path(__file__)))
(b/'current-archive-catalog.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(complete_studies=13,unfinished_subsets=1,archive_files=len(artifacts),archive_bytes=result['archive_bytes'],missing_in_complete_studies=sum(s.get('currently_missing_members',s.get('missing_members_in_scope',0)) for s in result['complete_studies'])),indent=2))
