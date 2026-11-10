"""Bounded, recoverable archival of completed final fine N1600 volume snapshots after the complete budget consumer terminates."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,re,time,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent; root=b.parents[1]; w=b/'elastic-s24-l1-n1600'
e=root/'docs/research/data/macos-elastic-fine-n1600-2026-11-10'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
# The final window remains untouched until the complete consumer has finished.
audit=b/(w.name+'-audit.json')
assert sha(audit)=='5437bea4958c35c4a9ad4a1dd21b2fd60d444a6b5d330b724bdc2799765fd2b7'
budget_dir=b/'elastic-n1600-budgets-streaming'
required=[budget_dir/'eonsim'/name for name in ['space.json','time.json','tail.json','sampling.json','budget.json']]+[budget_dir/'eonsim-materialization-proof.json']
assert all(p.is_file() for p in required), 'Complete budget and cleanup proof required before archival'
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines()
assert not any('analyze-elastic-n1600-budget-streaming.py' in line or str(w) in line or 'recompute-20261109/elastic-s24-l1-n1600' in line for line in processes)
proof=json.loads(required[-1].read_text())
for name,count in [('elastic-s24-l0-n1600',3200),('elastic-s24-l1-n800',1600)]:
 work=b/name;members=proof[str(work)]['restored_members'];assert len(members)==count
 assert len({r['path'] for r in members})==count and all(not (work/r['path']).exists() for r in members)
consumer_sha={str(p):sha(p) for p in required}
manifest=e/'raw-manifest.json'
m=json.loads(manifest.read_text())
c=json.loads((w/'completion.json').read_text());assert c['accepted_steps']==51200
assert all(r['exit_code']==0 for r in c['receipts'])
rows={r['path']:r for r in m['files']};assert len(rows)==len(m['files'])
refs=set()
missing_before=set()
for p in w.rglob('*.pvd'):
 for node in ET.parse(p).findall('.//DataSet'):refs.add((p.parent/node.attrib['file']).resolve())
missing_before={p for p in refs if not p.is_file()}
pattern=re.compile(r'^(early|dense-\d{3})/solution(?:_restart\d+)?_step(\d+)(_solid)?\.vtu$')
selected={};groups={}
for rel,row in rows.items():
 match=pattern.fullmatch(rel)
 if not match or not 48000<int(match[2])<=51200:continue
 q=w/rel;assert q.resolve() in refs and not q.is_symlink()
 selected[rel]=row;groups.setdefault((match[1],int(match[2])),set()).add(bool(match[3]))
assert len(selected)==6400 and all(v=={False,True} for v in groups.values())
assert {s for label,s in groups if label=='early'}==set()
assert {s for label,s in groups if label.startswith('dense-')}==set(range(48001,51201))
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-volume-after48000-chunks');out.mkdir(exist_ok=True)
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
 proc=subprocess.Popen(['zstd','-q','-9','-T1','-o',str(pending)],stdin=subprocess.PIPE)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',consumer_sha256=consumer_sha,scope='Completed fine N1600 volumes48001..51200 after terminal complete budget and cleanup proof. Restore before any replay or future consumer. Budget failure is preserved; archival does not waive any numerical task.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
assert {p for p in refs if not p.is_file()}==missing_before|{(w/rel).resolve() for rel in selected}
print('Final volumes decoded/SHA-verified after complete budget consumer',flush=True)
