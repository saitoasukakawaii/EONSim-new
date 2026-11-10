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
 ('elastic-s24-l0-n1600',str(b.parents[1]/'docs/research/data/macos-elastic-coarse-n1600-2026-11-09/raw-manifest.json'),['-boundary-chunks','-volume-chunks'],19418,True),
 ('elastic-s24-l1-n800-length24','length24-boundary-through24453-before-archive.json',['-boundary-through24453-chunks'],2564,False),
 ('elastic-s24-l0-n800','coarse-n800-raw-before-archive.json',['-snapshot-chunks'],9819,True),
 ('alpha2-s96-l1-n1600','alpha2-s96-l1-n1600-cycle4-before-archive.json',['-cycle4-chunks'],1599,False),
 ('elastic-s24-l1-n1600',str(b.parents[1]/'docs/research/data/macos-elastic-fine-n1600-2026-11-10/raw-manifest.json'),['-boundary-through48448-chunks','-boundary-segments009-013-chunks','-boundary-segments014-015-chunks','-boundary-segments016-017-chunks','-boundary-segments018-019-chunks','-volume-through48000-chunks','-volume-after48000-chunks'],19672,True),
 ('elastic-s24-l1-n800-length24','length24-volumes-through24584-before-archive.json',['-volume-through24584-chunks'],2826,False),
 ('elastic-s24-l1-n800-length24','length24-boundary-tail-through25180-before-archive.json',['-boundary-tail-through25180-chunks'],1454,False),
 ('elastic-s24-l1-n800-length24','length24-volumes-tail-through25349-before-archive.json',['-volume-tail-through25349-chunks'],1530,False),
 ('elastic-s24-l1-n800-length24','length24-late-output-tail-through25550-before-archive.json',['-late-output-tail-through25550-chunks'],1142,False),
 ('elastic-s24-l1-n800-tautime-n400','tau-boundary-through23638-before-archive.json',['-boundary-through23638-chunks'],934,False),
 ('reference-kinematic-elastic-s24-l1-n400-nu0',str(b.parents[1]/'docs/research/data/macos-kinematic-fine-n400-physics-2026-11-10/raw-manifest.json'),['-completed-fields-through12799-chunks'],1405,True),
 ('alpha2-s96-l1-n1600','alpha2-s96-l1-n1600-cycle5-prefix7200-before-archive.json',['-cycle5-prefix7200-chunks'],800,False),
 ('','reference-native-n800-dual-path-before-archive.json',['reference-native-n800-dual-path-chunks'],4697,False),
 ('alpha2-s96-l1-n1600','alpha2-s96-l1-n1600-cycle5-tail7999-before-archive.json',['-cycle5-tail7999-chunks'],799,False)
]:
 w=b/name;manifest=b/manifest_name;m=json.loads(manifest.read_text());expected={r['path']:r for r in m['files']};assert len(expected)==count;mh=sha(manifest)
 missing={rel for rel in expected if not (w/rel).is_file()};covered=set();receipts=[]
 for suffix in suffixes:
  for rp in sorted((b/'archives'/(name+suffix)).glob('*.json')):
   r=json.loads(rp.read_text());assert r['status']=='evicted' and Path(r['work'])==w
   source_manifest=manifest
   if name=='elastic-s24-l1-n1600' and suffix.startswith('-boundary-'):
    source_manifest=b/('fine-n1600'+suffix.removesuffix('-chunks')+'-before-archive.json')
   assert Path(r['source_manifest'])==source_manifest and r['source_manifest_sha256']==sha(source_manifest)
   source_rows={x['path']:x for x in json.loads(source_manifest.read_text())['files']}
   assert set(source_rows)<=set(expected)
   for rel,row in source_rows.items():
    assert (row['bytes'],row['sha256'])==(expected[rel]['bytes'],expected[rel]['sha256'])
   assert set(r['selected'])<=set(source_rows)
   archive=Path(r['archive']);assert archive.is_file() and archive.stat().st_size==r['archive_bytes']
   relarchive=str(archive.relative_to(b));assert relarchive not in artifacts
   artifacts[relarchive]=dict(bytes=archive.stat().st_size,sha256=r['archive_sha256'],scope='Previously decoded chunk; current existence/size and receipt/manifest bindings checked.')
   for rel,row in r['selected'].items():
    assert rel in missing and rel not in covered
    assert row['bytes']==expected[rel]['bytes'] and row['sha256']==expected[rel]['sha256'];covered.add(rel)
   receipts.append(dict(receipt=str(rp),sha256=sha(rp),members=len(r['selected']),restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(rp)]))
 assert missing==covered
 if name=='reference-kinematic-elastic-s24-l1-n400-nu0':assert len(missing)==1200 and len(receipts)==9
 if name=='elastic-s24-l0-n1600':assert len(missing)==19316
 if name=='elastic-s24-l1-n1600':assert len(missing)==19316
 if complete:
  actual={str(p.relative_to(w)):p for p in w.rglob('*') if p.is_file() and not p.name.endswith('.compressed-pending')};assert set(actual)==set(expected)-missing
  for rel,p in actual.items():assert not p.is_symlink() and p.stat().st_size==expected[rel]['bytes']
 else:
  assert missing==set(expected)
  if name=='alpha2-s96-l1-n1600':
   for row in expected.values():assert sha(w/row['checkpoint_manifest'])==row['checkpoint_manifest_sha256']
   assert {r['step'] for r in expected.values()}==set(range(7201,8000) if 'cycle5-tail7999' in manifest.name else range(6401,7201) if 'cycle5-prefix7200' in manifest.name else (range(4801,6400) if 'cycle4' in manifest.name else range(3201,4800)))
  elif name=='':
   assert len(missing)==4697 and len(receipts)==32 and m['count']==4697 and len(m['groups'])==2398
   assert sha(Path(m['source_manifest']))==m['source_manifest_sha256']
  elif name=='elastic-s24-l1-n800-length24':
   assert (len(missing),m['through'])==(1142,25550) if 'late-output' in manifest.name else (len(missing),m['through'])==(((1530,25349) if 'tail-through' in manifest.name else (2826,24584)) if 'volumes' in manifest.name else ((1454,25180) if 'tail-through' in manifest.name else (2564,24453)))
  elif name=='elastic-s24-l1-n800-tautime-n400':
   assert (len(missing),m['through'],m['last_complete_step'])==(934,23638,23639)
  else:
   assert name=='elastic-s24-l1-n1600' and (len(missing),m['through']) in [(4154,48448),(2560,49728),(1024,50240),(1024,50752),(896,51200)]
   for rel,digest in m['receipt_sha256'].items():assert sha(w/rel)==digest
 new.append(dict(work=str(w),scope='Complete terminal raw inventory' if complete else 'Only recorded immutable subset of study; no whole-study inventory claim',manifest=str(manifest),manifest_sha256=mh,original_members_in_scope=count,missing_members_in_scope=len(missing),missing_paths_exactly_accounted=True,restoration_receipts=receipts))
zstd_count=len(artifacts)
assert len(artifacts)==zstd_count and set(artifacts)=={str(p.relative_to(b)) for p in (b/'archives').rglob('*.tar.zst')}
for p in sorted((b/'archives').glob('*.tar.gz')):
 artifacts[str(p.relative_to(b))]=dict(bytes=p.stat().st_size,sha256=sha(p),scope='Supplemental probe/reference archive hash computed now; no materialization eviction indexed here.')
assert len(artifacts)==zstd_count+4
result=dict(passed=True,observed_unix=time.time(),complete_studies=base['studies']+[new[0],new[2],new[4],new[6],new[12]],unfinished_study_subsets=[new[1],new[3],new[5],new[7],new[8],new[9],new[10],new[11],new[13],new[14],new[15]],archive_root=str(b),archive_files=artifacts,archive_bytes=sum(r['bytes'] for r in artifacts.values()),scope='16 complete study inventories plus two immutable1599HDF 2564boundary,1454boundary-tail and2826volume/1530volume-tail/1142late-output and934 tau-boundary plus800 cycle5-prefix and799 cycle5-tail HDF and4697 native-reference dual-path subsets reconciled.All indexed zstd receipts all bound; no missing in-scope paths unaccounted. Current review does not rehash/redecode unchanged zstd archives or all retained raw fields; their prior decoded hashes retained.4 small supplemental gzip archives hashed now. Migration still requires copied-file SHA verification before local removal and valid restoration path mapping.',source_sha256=sha(Path(__file__)))
(b/'current-archive-catalog.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(complete_studies=16,unfinished_subsets=11,archive_files=len(artifacts),archive_bytes=result['archive_bytes'],missing_in_complete_studies=sum(s.get('currently_missing_members',s.get('missing_members_in_scope',0)) for s in result['complete_studies'])),indent=2))
