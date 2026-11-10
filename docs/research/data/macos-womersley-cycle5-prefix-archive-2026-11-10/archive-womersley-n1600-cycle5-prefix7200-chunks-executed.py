"""Archive only verified immutable cycle5-prefix7200 internal HDF, with bounded temporary disk."""
from pathlib import Path
import json,hashlib,shutil,tarfile,subprocess,os,time
b=Path(__file__).resolve().parent;w=b/'alpha2-s96-l1-n1600';manifest=b/(w.name+'-cycle5-prefix7200-before-archive.json')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
m=json.loads(manifest.read_text());assert m['count']==800 and sha(w/'definition.json')==m['definition_sha256']
raw=(w/'attempt-005/solve.log').read_bytes()[:m['accepted_log_prefix_bytes']];assert hashlib.sha256(raw).hexdigest()==m['accepted_log_prefix_sha256']
assert json.loads((w/'receipt.json').read_text())['step']>=6400 and m['last_complete_step']>7200
selected={r['path']:r for r in m['files']};assert len(selected)==800 and {r['step'] for r in selected.values()}==set(range(6401,7201))
for row in selected.values():assert sha(w/row['checkpoint_manifest'])==row['checkpoint_manifest_sha256']
refs=[]
for p in (w/'checkpoint').glob('generation_*/manifest'):
 if int(p.read_text().split()[2]) in [1600,3200,4800,6400]:refs.append(p.parent/'state_rank0.h5')
assert len(refs)==4 and all(p.is_file() for p in refs)
pointer=(w/'checkpoint/current').read_text().split();assert pointer[0]=='EONSim_checkpoint_v4'
current=w/'checkpoint'/pointer[1];assert int((current/'manifest').read_text().split()[2])>7200
assert str((current/'state_rank0.h5').relative_to(w)) not in selected
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-cycle5-prefix7200-chunks');out.mkdir(exist_ok=True)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Immutable cycle5-prefix7200 internal HDF only; endpoints/current and cycles5/6 retained; cycle3 previously archived. Restore using restore-womersley-materialization.py before cycle5-prefix7200 analysis or a full raw directory replay.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
assert all(p.is_file() for p in refs)
print('All cycle5-prefix7200 chunks decoded/SHA-verified; endpoints retained',flush=True)
