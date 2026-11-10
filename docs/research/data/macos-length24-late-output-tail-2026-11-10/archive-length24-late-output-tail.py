"""Bounded, recoverable archival of completed geometry boundary snapshots only."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil,os,re,time,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent; root=b.parents[1]; w=b/'elastic-s24-l1-n800-length24'
e=root/'docs/research/data/macos-elastic-coarse-n1600-2026-11-09'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):
 tmp=p.with_suffix(p.suffix+'.pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
# Immutable accepted prefix from the same held process; full physical audit will restore these inputs.
manifest=b/'length24-late-output-tail-through25550-before-archive.json';m=json.loads(manifest.read_text())
assert m['through']==25550 and sha(w/'early/receipt.json')==m['early_receipt_sha256']
h=json.loads((b/'length24-capacity-hold-eighth.json').read_text());assert sha(b/'length24-capacity-hold-eighth.json')==m['hold_receipt_sha256']
raw=subprocess.check_output(['ps','-p',str(h['pid']),'-o','pgid=,state=,command='],text=True).strip();group,state,cmd=raw.split(None,2)
assert int(group)==h['pgid'] and 'T' in state and cmd==h['command']
rows={r['path']:r for r in m['files']};assert len(rows)==len(m['files'])
refs=set()
for p in w.rglob('*.pvd'):
 for node in ET.parse(p).findall('.//DataSet'):refs.add((p.parent/node.attrib['file']).resolve())
missing_before={p for p in refs if not p.is_file()}
selected=rows
assert len(selected)==1142
for rel in selected:
 match=re.fullmatch(r'dense/solution_restart23200_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu',rel);assert match
 step=int(match[1]);boundary='boundary' in (match[2] or '')
 assert (25181 if boundary else 25350)<=step<=25550
 assert ((w/rel).resolve() not in refs if boundary else (w/rel).resolve() in refs)
assert sum('boundary' in rel for rel in selected)==740
chunks=[];chunk=[];size=0
for rel in sorted(selected):
 if chunk and size+selected[rel]['bytes']>128*1024**2:chunks.append(chunk);chunk=[];size=0
 chunk.append(rel);size+=selected[rel]['bytes']
if chunk:chunks.append(chunk)
out=b/'archives'/(w.name+'-late-output-tail-through25550-chunks');out.mkdir(exist_ok=True)
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
 record=dict(work=str(w),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,source_manifest=str(manifest),source_manifest_sha256=sha(manifest),selected=batch,status='verified-before-eviction',scope='Immutable length24 late outputs:740 boundary and402 body through25550; current checkpoint and later fields retained. Full physical audit must restore every required archived frame with audit-pressure-streaming.py or full restoration; no phases or gates waived.')
 dump(receipt,record)
 for rel,row in batch.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(r['allocated_bytes'] for r in batch.values()),finished_unix=time.time());dump(receipt,record)
 print(i,len(rels),record['removed_allocated_bytes'],flush=True)
assert {p for p in refs if not p.is_file()}==missing_before|{(w/rel).resolve() for rel in selected if (w/rel).resolve() in refs}
print('Length prefix decoded/SHA-verified; restore before full physical audit',flush=True)
