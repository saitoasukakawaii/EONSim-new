"""Archive completed geometry volume snapshots only after all current field consumers finish."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,shutil,os,time,re
b=Path(__file__).resolve().parent;root=b.parents[1];w=b/'elastic-s24-l1-n800-geometry48'
e=root/'docs/research/data/macos-elastic-geometry48-n800-2026-11-09';manifest=b/(w.name+'-raw-before-archive.json')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
summary=json.loads((e/'summary.json').read_text());assert summary['all_local_physical_checks_passed'] and summary['steps']==25600
assert sha(b/(w.name+'-audit.json'))==summary['audit_sha256']
response=json.loads((e/'response.json').read_text())
for p,digest in response['input_sha256'].items():assert sha(Path(p))==digest
assert json.loads((e/'response-independent-check.json').read_text())['fields_checked']==5
c=json.loads((w/'completion.json').read_text());assert c['accepted_steps']==25600 and all(r['exit_code']==0 for r in c['receipts'])
m=json.loads(manifest.read_text());rows={r['path']:r for r in m['files']}
assert rows=={r['path']:r for r in json.loads((e/'raw-manifest.json').read_text())['files']}
pattern=re.compile(r'^(early|dense)/solution(?:_restart\d+)?_step(\d+)(_solid)?\.vtu$');selected={};groups={}
for rel,row in rows.items():
 match=pattern.fullmatch(rel)
 if not match:continue
 assert not (w/rel).is_symlink();selected[rel]=row;groups.setdefault((match[1],int(match[2])),set()).add(bool(match[3]))
assert len(selected)==4858 and all(v=={False,True} for v in groups.values())
assert {s for label,s in groups if label=='early'}==set(range(800,23201,800))
assert {s for label,s in groups if label=='dense'}==set(range(23201,25601))
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-volume-chunks');out.mkdir(exist_ok=True)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Completed geometry step-specific volume snapshots. Full physics capture and response consumers completed first. PVD files remain but these targets are archived; restore receipts with restore-womersley-materialization.py before VTU visualization, repeat physics audits or whole-directory replay. Checkpoints/logs/meshes/final aliases retained.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
print('All completed geometry volume chunks decoded/SHA-verified; restoration required for PVD replay',flush=True)
