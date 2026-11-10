"""User-authorized capacity scheduling: evict verified duplicate completed-study volumes.
Restore the receipt before any field consumer; no numerical acceptance is changed.
"""
from pathlib import Path
import argparse,json,hashlib,subprocess,tarfile,time,shutil,re
p=argparse.ArgumentParser();p.add_argument('--n',type=int,choices=[400,800],required=True);a=p.parse_args()
b=Path(__file__).resolve().parent;w=b/f'elastic-s24-l1-n{a.n}'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
r=json.loads((b/'archives'/(w.name+'.json')).read_text());archive=Path(r['archive']);manifest=Path(r['source_manifest'])
assert sha(archive)==r['archive_sha256'] and sha(manifest)==r['source_manifest_sha256']
c=json.loads((w/'completion-postflight.json').read_text());assert c['accepted_steps']==32*a.n and all(v['exit_code']==0 for v in c['receipts'])
out=b/'archives'/(w.name+'-volume-materialization.json');assert not out.exists()
rows={x['path']:x for x in json.loads(manifest.read_text())['files']};selected={};groups={}
pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)(_solid)?\.vtu$')
for label in ['early','dense']:
 for q in (w/label).glob('*.vtu'):
  m=pattern.fullmatch(q.name)
  if not m:continue
  step=int(m[1]);groups.setdefault((label,step),set()).add(bool(m[2]));rel=str(q.relative_to(w));row=rows[rel]
  assert not q.is_symlink() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256']
  selected[rel]=dict(step=step,bytes=row['bytes'],sha256=row['sha256'],allocated_bytes=q.stat().st_blocks*512)
assert len(selected)==2*(29+3*a.n) and all(v=={False,True} for v in groups.values())
assert {s for l,s in groups if l=='early'}==set(range(a.n,29*a.n+1,a.n))
assert {s for l,s in groups if l=='dense'}==set(range(29*a.n+1,32*a.n+1))
proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
 for m in t:
  if m.name in selected:
   row=selected[m.name];assert m.isfile() and m.name not in seen and m.size==row['bytes']
   assert hashlib.file_digest(t.extractfile(m),'sha256').hexdigest()==row['sha256'];seen.add(m.name)
proc.stdout.read();assert proc.wait()==0 and seen==set(selected)
record=dict(work=str(w),archive=str(archive),archive_sha256=r['archive_sha256'],source_manifest=str(manifest),source_manifest_sha256=r['source_manifest_sha256'],selected=selected,status='verified-before-eviction',completion_sha256=sha(w/'completion-postflight.json'),scope='User authorized cleanup of redundant prior calculation files. Every selected immutable volume freshly decoded and SHA-verified against original manifest and expanded bytes. PVD indexes retained but selected targets archived. Mandatory restore before future/repeated physics, cross-program, tau, or budget field consumers. Checkpoints, aliases, meshes, logs and reports retained. No unique raw bytes discarded.',restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(out)])
out.write_text(json.dumps(record,indent=2)+'\n');free=shutil.disk_usage(b).free
for rel,row in selected.items():
 q=w/rel;assert sha(q)==row['sha256'];q.unlink()
record.update(status='evicted',removed_allocated_bytes=sum(x['allocated_bytes'] for x in selected.values()),observed_free_change_bytes=shutil.disk_usage(b).free-free,finished_unix=time.time())
out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['work','status','removed_allocated_bytes','observed_free_change_bytes']},indent=2),flush=True)
