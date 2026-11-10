"""Byte-preserving filesystem compression for two terminal reference N400 result sets."""
from pathlib import Path
import hashlib,json,subprocess,os,stat,time
b=Path(__file__).resolve().parent;out=b/'terminal-reference-n400-compression.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines();selected=[];proof={}
for name in ['reference-elastic-s24-l1-n400-nu0','reference-kinematic-elastic-s24-l1-n400-nu0']:
 w=b/name;c=w/'completion.json';d=json.loads(c.read_text());assert d['steps']==12800 and d['process']['exit_code']==0 and d['full_equation_convergence_passed']
 assert not any(str(w) in line or 'recompute-20261109/'+name in line for line in processes)
 ps=sorted(w.rglob('*.vtu'));assert len(ps)==1203
 proof[name]=dict(completion_sha256=sha(c),selected_vtu=1203)
 for p in ps:
  assert not p.is_symlink();st=p.stat()
  if not st.st_flags&stat.UF_COMPRESSED:selected.append(p)
rows=[];start=time.time()
try:
 for p in selected:
  before=p.stat();digest=sha(p);pending=p.with_name(p.name+'.compressed-pending');assert not pending.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(pending)],check=True)
  assert pending.stat().st_size==before.st_size and sha(pending)==digest
  assert (p.stat().st_size,p.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns) and sha(p)==digest
  after=pending.stat()
  if after.st_blocks<before.st_blocks:
   os.replace(pending,p);assert sha(p)==digest
   rows.append(dict(path=str(p.relative_to(b)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
  else:pending.unlink()
 result=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=b.parents[1],text=True).strip(),proof=proof,files=rows,selected_uncompressed=len(selected),saved_allocated_bytes=sum(r['allocated_before']-r['allocated_after'] for r in rows),seconds=time.time()-start,logical_content_unchanged=True)
 out.write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='files'},'replaced',len(rows),flush=True)
except BaseException as e:
 out.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),proof=proof,verified_replacements=rows),indent=2)+'\n');raise
