"""Archive every byte of terminal diagnostics, decode verify, then evict restorable bin/VTU duplicates."""
from pathlib import Path
import json,hashlib,subprocess,tarfile,shutil,os,time
b=Path(__file__).resolve().parent;out=b/'archives';names=['reference-kinematic-increment-startup','reference-strict-increment-startup','reference-fine-backend-screen']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
for name in names:
 w=b/name;report=w/('report.json' if 'screen' in name else 'diagnostic.json');d=json.loads(report.read_text());assert d['runs'] and all(r['exit_code']==0 for r in d['runs'].values())
 processes=subprocess.check_output(['ps','-axo','comm='],text=True).splitlines();assert not any(str(w)+'/' in p for p in processes)
 dest=out/(name+'.tar.zst');pending=dest.with_suffix('.zst.pending');receipt=out/(name+'.json');manifest=out/(name+'-raw-manifest.json');eviction=out/(name+'-materialization.json')
 assert not any(p.exists() for p in [dest,pending,receipt,manifest,eviction])
 files=[]
 for p in sorted(w.rglob('*')):
  assert not p.is_symlink()
  if p.is_file():
   before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
   files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
 expected={r['path']:r for r in files};total=sum(r['bytes'] for r in files)
 assert shutil.disk_usage(b).free>20*1024**3+total+64*1024**2
 dump(manifest,dict(local_root=str(w),files=files,count=len(files),total_bytes=total,terminal_report_sha256=sha(report)))
 t=time.time();proc=subprocess.Popen(['zstd','-q','-3','-T1','-o',str(pending)],stdin=subprocess.PIPE)
 with tarfile.open(fileobj=proc.stdin,mode='w|') as archive:
  for rel in expected:archive.add(w/rel,arcname=rel,recursive=False)
 proc.stdin.close();assert proc.wait()==0
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(pending)],stdout=subprocess.PIPE);seen=set()
 with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
  for m in archive:
   assert m.isfile() and m.name in expected and m.name not in seen and m.size==expected[m.name]['bytes']
   assert hashlib.file_digest(archive.extractfile(m),'sha256').hexdigest()==expected[m.name]['sha256'];seen.add(m.name)
 proc.stdout.read();assert proc.wait()==0 and seen==set(expected);digest=sha(pending);os.rename(pending,dest)
 dump(receipt,dict(work=str(w),archive=str(dest),archive_bytes=dest.stat().st_size,archive_sha256=digest,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),verified_members=len(seen),source_bytes=total,source_removed=False,seconds=time.time()-t,scope='Complete terminal diagnostic archived and every member decoded SHA-verified. Numerical success/failure conclusions unchanged.'))
 selected={}
 for rel,row in expected.items():
  p=w/rel
  if p.suffix in ('.bin','.vtu'):
   assert sha(p)==row['sha256'];selected[rel]=dict(sha256=row['sha256'],bytes=row['bytes'],allocated_bytes=p.stat().st_blocks*512)
 assert selected
 record=dict(work=str(w),archive=str(dest),archive_sha256=digest,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=selected,status='verified-before-eviction',restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(eviction)],scope='Only terminal diagnostic bin/VTU expanded duplicates removed after full archive decoding. Logs/configuration/reports retained. Restore all selected files before any future raw comparison, provenance replay or restart. Production studies untouched.')
 dump(eviction,record)
 for rel,row in selected.items():
  p=w/rel;assert sha(p)==row['sha256'];p.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in selected.values()),finished_unix=time.time());dump(eviction,record)
 print(name,'archived',len(seen),'evicted',len(selected),'freed',record['removed_allocated_bytes'],'archive_bytes',dest.stat().st_size,flush=True)
