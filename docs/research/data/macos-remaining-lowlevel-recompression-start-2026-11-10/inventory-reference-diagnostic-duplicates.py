"""Read-only content/inode inventory of three completed reference diagnostic scopes."""
from pathlib import Path
import hashlib,json,time
b=Path(__file__).resolve().parent;names=['reference-kinematic-increment-fine-diagnostic','reference-mesh-backend-diagnostic','reference-mesh-increment-diagnostic'];groups={};count=0
for name in names:
 for p in sorted((b/name).rglob('*.vtu')):
  assert not p.is_symlink();a=p.stat()
  with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
  c=p.stat();assert (a.st_size,a.st_mtime_ns,a.st_ino)==(c.st_size,c.st_mtime_ns,c.st_ino)
  groups.setdefault((a.st_size,digest),[]).append(dict(path=str(p.relative_to(b)),bytes=a.st_size,sha256=digest,device=a.st_dev,inode=a.st_ino,nlink=a.st_nlink,mtime_ns=a.st_mtime_ns,allocated_bytes=a.st_blocks*512));count+=1
selected=[];saving=0
for key,rows in groups.items():
 unique={(r['device'],r['inode']) for r in rows}
 if len(unique)<2:continue
 # Do not claim bytes for existing external aliases.
 if not all(r['nlink']==1 for r in rows):continue
 rows.sort(key=lambda r:(r['allocated_bytes'],r['path']));selected.append(rows);saving+=sum(r['allocated_bytes'] for r in rows[1:])
result=dict(scopes=names,scanned_files=count,duplicate_groups=selected,potential_saved_bytes=saving,observed_unix=time.time(),scope='Read-only exact content inventory; no files modified. Active production directories excluded.')
(b/'reference-diagnostic-duplicate-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print('scanned',count,'groups',len(selected),'potential_saved_bytes',saving)
