"""Bounded, recoverable archival of completed geometry boundary snapshots only."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,re,time,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent; root=b.parents[1]; w=b/'elastic-s24-l1-n800-tautime-n400'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
# Solver held; immutable accepted-prefix boundary inventory required; read-only audit uses PVD volume fields.
manifest=b/'tau-boundary-through23638-before-archive.json'
m=json.loads(manifest.read_text())
hold=json.loads((b/'fsi-tau-control-capacity-hold-third.json').read_text());assert hold['status']=='held' and hold['pid']==hold['pgid']==35782
import subprocess
observed=subprocess.check_output(['ps','-p',str(hold['pid']),'-o','pgid=,state=,command='],text=True).strip().split(None,2)
assert int(observed[0])==hold['pgid'] and 'T' in observed[1] and observed[2]==hold['command']
assert json.loads((w/'early/receipt.json').read_text())['exit_code']==0

raw=(w/'dense/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];assert hashlib.sha256(raw).hexdigest()==m['log_prefix_sha256']
rows={r['path']:r for r in m['files']};assert len(rows)==len(m['files'])
refs=set()
for p in w.rglob('*.pvd'):
 for node in ET.parse(p).findall('.//DataSet'):refs.add((p.parent/node.attrib['file']).resolve())
pattern=re.compile(r'^(early|dense)/solution(?:_restart\d+)?_step(\d+)_(solid_)?boundary\.vtu$')
selected={};groups={}
for rel,row in rows.items():
 match=pattern.fullmatch(rel)
 if not match:continue
 q=w/rel;assert q.resolve() not in refs and not q.is_symlink()
 selected[rel]=row;groups.setdefault((match[1],int(match[2])),set()).add(bool(match[3]))
assert len(selected)==934 and all(v=={False,True} for v in groups.values())
assert {s for label,s in groups if label=='early'}==set(range(800,23201,800))
assert {s for label,s in groups if label=='dense'}==set(range(23201,23639))
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-boundary-through23638-chunks');out.mkdir(exist_ok=True)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Unfinished study immutable boundary prefix through23638 only; volume/PVD/checkpoint/logs retained. Restore this receipt with restore-womersley-materialization.py before any boundary consumer or full raw inventory replay.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
assert all(p.is_file() for p in refs)
print('All boundary chunks decoded/SHA-verified; volume fields retained',flush=True)
