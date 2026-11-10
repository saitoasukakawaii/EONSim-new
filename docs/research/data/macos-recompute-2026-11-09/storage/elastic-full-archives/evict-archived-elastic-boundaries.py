"""Recover redundant boundary VTU materializations; keep all volume fields used by audits/budgets."""
from pathlib import Path
import argparse,json,hashlib,subprocess,tarfile,time,shutil,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--n',type=int,choices=[400,800],required=True);a=p.parse_args();b=Path(__file__).resolve().parent;w=b/f'elastic-s24-l1-n{a.n}'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
receipt_path=b/'archives'/(w.name+'.json');receipt=json.loads(receipt_path.read_text());archive=Path(receipt['archive']);manifest=Path(receipt['source_manifest']);assert sha(archive)==receipt['archive_sha256'] and sha(manifest)==receipt['source_manifest_sha256']
completion=json.loads((w/'completion-postflight.json').read_text());assert completion['accepted_steps']==32*a.n and all(r['exit_code']==0 for r in completion['receipts'])
out=b/'archives'/(w.name+'-boundary-materialization.json');assert not out.exists();rows={r['path']:r for r in json.loads(manifest.read_text())['files']}
# Every actual PVD target is retained, including nested per-stage and joined indexes.
referenced=set()
for p in w.rglob('*.pvd'):
 for item in ET.parse(p).findall('.//DataSet'):referenced.add((p.parent/item.attrib['file']).resolve())
selected={}
for label in ['early','dense']:
 for q in (w/label).glob('*_boundary.vtu'):
  assert q.resolve() not in referenced and not q.is_symlink();rel=str(q.relative_to(w));assert rel in rows;assert sha(q)==rows[rel]['sha256'] and q.stat().st_size==rows[rel]['bytes']
  selected[rel]=dict(sha256=rows[rel]['sha256'],bytes=rows[rel]['bytes'],allocated_bytes=q.stat().st_blocks*512)
assert len(selected)==2*(29+3*a.n)
proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
 for m in tar:
  if m.name in selected:
   assert m.isfile() and m.name not in seen and m.size==selected[m.name]['bytes'];assert hashlib.file_digest(tar.extractfile(m),'sha256').hexdigest()==selected[m.name]['sha256'];seen.add(m.name)
proc.stdout.read();assert proc.wait()==0 and seen==set(selected)
record=dict(work=str(w),archive=str(archive),archive_sha256=receipt['archive_sha256'],source_manifest=str(manifest),source_manifest_sha256=receipt['source_manifest_sha256'],selected=selected,status='verified-before-eviction',retained_pvd_targets=len(referenced),completion_sha256=sha(w/'completion-postflight.json'),scope='Only redundant boundary VTU materializations removed after fresh decoded archive verification. All volume fields, checkpoints, logs and every actual PVD target retained for ongoing/future physics and budget consumers. Boundary-specific consumers and full inventory checks must restore these members first.',restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(out)])
out.write_text(json.dumps(record,indent=2)+'\n');free=shutil.disk_usage(b).free
for rel,row in selected.items():
 q=w/rel;assert sha(q)==row['sha256'];q.unlink()
assert all(p.is_file() for p in referenced)
record.update(status='evicted',removed_allocated_bytes=sum(v['allocated_bytes'] for v in selected.values()),observed_free_change_bytes=shutil.disk_usage(b).free-free,finished_unix=time.time());out.write_text(json.dumps(record,indent=2)+'\n');print(w.name,len(selected),record['removed_allocated_bytes'])
