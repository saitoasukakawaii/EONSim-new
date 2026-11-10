"""Capture immutable terminal raw inventory independently of ongoing read-only physics audit."""
from pathlib import Path
import json,hashlib,re,time
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-geometry48';out=b/(w.name+'-raw-before-archive.json')
assert not out.exists()
c=json.loads((w/'completion.json').read_text());assert c['accepted_steps']==25600 and all(r['exit_code']==0 for r in c['receipts'])
for label,first,last in [('early',1,23200),('dense',23201,25600)]:
 t=(w/label/'solve.log').read_text();assert list(map(int,re.findall(r'^fsi_step=(\d+)',t,re.M)))==list(range(first,last+1));assert 'status=success' in t
files=[]
for p in sorted(w.rglob('*')):
 if not p.is_file() or p.name.endswith('.compressed-pending'):continue
 assert not p.is_symlink();before=p.stat()
 with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
actual={str(p.relative_to(w)) for p in w.rglob('*') if p.is_file() and not p.name.endswith('.compressed-pending')};assert actual=={r['path'] for r in files}
out.write_text(json.dumps(dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(r['bytes'] for r in files),finished_unix=time.time(),scope='Complete terminal raw inventory before boundary archival. Physics audit still pending; no numerical qualification claimed.'),indent=2)+'\n')
print(len(files),sum(r['bytes'] for r in files),flush=True)
