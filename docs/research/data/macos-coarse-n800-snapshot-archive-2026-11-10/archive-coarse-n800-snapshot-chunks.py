"""Bounded, recoverable archival of completed geometry boundary snapshots only."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,re,time,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent; root=b.parents[1]; w=b/'elastic-s24-l0-n800'
e=root/'docs/research/data/macos-elastic-coarse-n1600-2026-11-09'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
# Terminal source only; pending N1600 budget MUST restore volume receipts first.
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines()
assert not any(str(w) in line or 'recompute-20261109/elastic-s24-l0-n800' in line for line in processes)
manifest=b/'coarse-n800-raw-before-archive.json'
m=json.loads(manifest.read_text())
c=json.loads((w/'completion-postflight.json').read_text());assert c['accepted_steps']==25600
assert all(r['exit_code']==0 for r in c['receipts'])
rows={r['path']:r for r in m['files']};assert len(rows)==len(m['files'])
refs=set()
for p in w.rglob('*.pvd'):
 for node in ET.parse(p).findall('.//DataSet'):refs.add((p.parent/node.attrib['file']).resolve())
pattern=re.compile(r'^(early|dense)/solution(?:_restart\d+)?_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu$')
selected={};groups={}
for rel,row in rows.items():
 match=pattern.fullmatch(rel)
 if not match:continue
 q=w/rel;assert not q.is_symlink()
 selected[rel]=row;groups.setdefault((match[1],int(match[2])),set()).add(match[3] or '')
assert len(selected)==9716 and all(v=={'','_solid','_boundary','_solid_boundary'} for v in groups.values())
assert {s for label,s in groups if label=='early'}==set(range(800,23201,800))
assert {s for label,s in groups if label=='dense'}==set(range(23201,25601))
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-snapshot-chunks');out.mkdir(exist_ok=True)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Terminal coarse N800 step snapshots only; PVD/logs/checkpoints retained. MUST restore all snapshot receipts before any repeated original N800 budget, matched coarse field comparison, physical replay or full raw inventory replay. Complete original byte manifest remains authoritative; no numerical task waived.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
assert {p for p in refs if not p.is_file()}=={(w/rel).resolve() for rel in selected if (w/rel).resolve() in refs}
print('All snapshots decoded/SHA-verified; restore before raw replay',flush=True)
