"""Bounded lossless archival of completed output hardlink pairs; preserve both restoration paths."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,time
b=Path(__file__).resolve().parent;w=b;manifest=b/'reference-native-n800-dual-path-before-archive.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
m=json.loads(manifest.read_text());assert Path(m['work'])==b and m['count']==4697 and sha(Path(m['source_manifest']))==m['source_manifest_sha256']
selected={x['path']:x for x in m['files']};assert len(selected)==4697
for rel,row in selected.items():
 p=w/rel;st=p.stat();assert not p.is_symlink() and (st.st_dev,st.st_ino,st.st_nlink)==(row['device'],row['inode'],row['links'])
chunks=[];chunk=[];size=0
for group in m['groups']:
 amount=sum(selected[x]['bytes'] for x in group)
 if chunk and size+amount>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk+=group;size+=amount
if chunk:chunks.append(chunk)
assert len(m['groups'])==2398 and sum(map(len,chunks))==4697
out=b/'archives'/'reference-native-n800-dual-path-chunks';out.mkdir(exist_ok=True)
for i,rels in enumerate(chunks):
 archive=out/f'{i:04d}.tar.zst';receipt=out/f'{i:04d}.json'
 if receipt.exists():
  old=json.loads(receipt.read_text());assert old['status']=='evicted' and set(old['selected'])==set(rels)
  assert sha(archive)==old['archive_sha256'] and all(not (w/r).exists() for r in rels);continue
 assert not archive.exists();pending=archive.with_suffix('.pending');assert not pending.exists()
 batch={}
 for rel in rels:
  q=w/rel;st=q.stat();assert st.st_size==selected[rel]['bytes'] and sha(q)==selected[rel]['sha256']
  batch[rel]=dict(bytes=st.st_size,sha256=selected[rel]['sha256'],allocated_bytes=selected[rel]['allocated_bytes'])
 assert shutil.disk_usage(b).free>20*1024**3+sum(v['bytes'] for v in batch.values())+256*1024**2
 proc=subprocess.Popen(['zstd','-q','-3','-T1','-o',str(pending)],stdin=subprocess.PIPE)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Completed native N800 output and inherited original hardlink aliases, stored as regular files for independent restore. Unique inode allocation counted once. Restore at recompute root using receipt before direct field consumption; boundary25500, endpoint23200 and final25600 retained.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
print('All native dual-path chunks decoded/SHA-verified; boundaries retained',flush=True)
