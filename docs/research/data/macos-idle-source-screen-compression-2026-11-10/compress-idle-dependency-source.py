"""Transparent compression of static reference pressure inputs outside live work roots."""
from pathlib import Path
import subprocess,hashlib,json,os,stat,time
b=Path(__file__).resolve().parent;out=b/'idle-trilinos-source-compression.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
excluded={'.git'}
root=b/'trilinos-source'
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines()
assert not any(str(root) in line or 'recompute-20261109/trilinos-source' in line for line in processes),'Live process references dependency source'
selected=[]
for p in sorted(root.rglob('*')):
 if '.git' in p.relative_to(root).parts or p.is_symlink() or not p.is_file():continue
 st=p.stat()
 if st.st_size<16384 or st.st_nlink!=1:continue
 selected.append(p)
assert selected;rows=[];started=time.time()
try:
 for p in selected:
  before=p.stat()
  if before.st_flags&stat.UF_COMPRESSED:continue
  digest=sha(p);q=p.with_name(p.name+'.compressed-pending');assert not q.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(q)],check=True)
  assert q.stat().st_size==before.st_size and sha(q)==digest
  assert (p.stat().st_size,p.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns) and sha(p)==digest
  if q.stat().st_blocks<before.st_blocks:
   os.replace(q,p);assert sha(p)==digest
   rows.append(dict(path=str(p.relative_to(b)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
  else:q.unlink()
 result=dict(files=rows,selected_files=len(selected),excluded_roots=sorted(excluded),seconds=time.time()-started,source_sha256=sha(Path(__file__)),saved_allocated_bytes=sum(r['allocated_before']-r['allocated_after'] for r in rows),scope='Only idle Trilinos source byte-preserving filesystem compression; git metadata, install libraries and build objects excluded. No files removed; logical input hashes/path remain unchanged. No live process referenced selected roots at preflight; no numerical qualification inferred.')
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
except BaseException as e:
 out.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),verified_replacements=rows),indent=2)+'\n');raise
