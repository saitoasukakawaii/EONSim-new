"""Archive completed adopted N400 reference fields after independent budget completion."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,re,time
b=Path(__file__).resolve().parent;root=b.parents[1];w=b/'reference-kinematic-elastic-s24-l1-n400-nu0'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
assert json.loads((b/'reference-native-n800-budget/svfsi/budget.json').read_text())['passed']
assert json.loads((w/'completion.json').read_text())['process']['exit_code']==0
manifest=root/'docs/research/data/macos-kinematic-fine-n400-physics-2026-11-10/raw-manifest.json'
m=json.loads(manifest.read_text());assert Path(m['local_root'])==w
selected={row['path']:row for row in m['files'] if re.fullmatch(r'results/result_\d+\.vtu',row['path']) and int(Path(row['path']).stem.split('_')[-1])<12800}
assert len(selected)==1200 and {int(Path(x).stem.split('_')[-1]) for x in selected}==set(range(11600,12800))
assert all(not (w/x).is_symlink() and (w/x).stat().st_nlink==1 for x in selected)
assert (w/'results/result_12800.vtu').is_file()
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-completed-fields-through12799-chunks');out.mkdir(exist_ok=True)
for i,rels in enumerate(chunks):
 archive=out/f'{i:04d}.tar.zst';receipt=out/f'{i:04d}.json'
 if receipt.exists():
  old=json.loads(receipt.read_text());assert old['status']=='evicted' and set(old['selected'])==set(rels)
  assert sha(archive)==old['archive_sha256'] and all(not (w/r).exists() for r in rels);continue
 assert not archive.exists();pending=archive.with_suffix('.pending');assert not pending.exists()
 batch={}
 for rel in rels:
  q=w/rel;st=q.stat();assert st.st_size==selected[rel]['bytes'] and sha(q)==selected[rel]['sha256']
  batch[rel]=dict(bytes=st.st_size,sha256=selected[rel]['sha256'],allocated_bytes=st.st_blocks*512)
 assert shutil.disk_usage(b).free>20*1024**3+sum(v['bytes'] for v in batch.values())+256*1024**2
 proc=subprocess.Popen(['zstd','-q','-19','-T1','-o',str(pending)],stdin=subprocess.PIPE)
 with tarfile.open(fileobj=proc.stdin,mode='w|',dereference=True) as tar:
  for rel in rels:tar.add(w/rel,arcname=rel,recursive=False)
 proc.stdin.close();assert proc.wait()==0
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(pending)],stdout=subprocess.PIPE);seen=set()
 with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
  for member in tar:
   assert member.isfile() and member.name in batch and member.name not in seen
   row=batch[member.name];assert member.size==row['bytes']
   assert hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==row['sha256'];seen.add(member.name)
 proc.stdout.read();assert proc.wait()==0 and seen==set(rels)
 os.rename(pending,archive)
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Completed adopted reference N400 fields through12799. Physical audit and independent budget complete. Final12800 field, inputs, checkpoints and logs retained. Restore via restore-womersley-materialization.py before any direct field consumer.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
print('All completed N400 chunks decoded/SHA-verified; final field retained',flush=True)
