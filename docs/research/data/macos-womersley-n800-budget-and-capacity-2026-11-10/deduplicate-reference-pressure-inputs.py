"""Share identical immutable reference pressure inputs; preserve every path and byte."""
from pathlib import Path
import json,hashlib,os,time,shutil
b=Path(__file__).resolve().parent;out=b/'reference-pressure-input-deduplication.json';assert not out.exists()
groups=json.loads((b/'reference-pressure-input-duplicates.json').read_text());rows=[];free=shutil.disk_usage(b).free
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for group in groups:
 group.sort(key=lambda r:(r['allocated'],r['path']));canonical=Path(group[0]['path']);base=canonical.stat();assert sha(canonical)==group[0]['sha256']
 for r in group[1:]:
  p=Path(r['path']);assert p.is_relative_to(b) and p.name in ['pressure-1.txt','pressure-2.txt'] and not p.is_symlink()
  s=p.stat();assert s.st_size==r['bytes'] and s.st_ino==r['inode'] and s.st_mtime_ns==r['mtime_ns'] and s.st_nlink==1 and s.st_dev==base.st_dev and s.st_mode==base.st_mode
  assert sha(p)==sha(canonical)==r['sha256'];temp=p.with_name(p.name+'.dedup-pending');assert not temp.exists();os.link(canonical,temp)
  assert sha(temp)==r['sha256'] and p.stat().st_ino==s.st_ino;os.replace(temp,p);assert p.stat().st_ino==canonical.stat().st_ino and sha(p)==r['sha256']
  rows.append(dict(path=str(p),canonical=str(canonical),bytes=s.st_size,sha256=r['sha256'],released_allocated_bytes=s.st_blocks*512))
for r in rows:assert sha(Path(r['path']))==r['sha256'] and Path(r['path']).stat().st_ino==Path(r['canonical']).stat().st_ino
out.write_text(json.dumps(dict(passed=True,files=rows,released_allocated_bytes=sum(r['released_allocated_bytes'] for r in rows),free_before=free,free_after=shutil.disk_usage(b).free,finished_unix=time.time(),scope='All paths and bytes retained. Shared immutable input inodes; do not edit in-place. Atomic replace for any future input change.'),indent=2)+'\n');print('verified',len(rows),'shared paths; released',sum(r['released_allocated_bytes'] for r in rows),flush=True)
