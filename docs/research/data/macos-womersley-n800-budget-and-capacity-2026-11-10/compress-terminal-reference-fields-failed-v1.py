"""Compress terminal reference field/restart files without changing paths or bytes."""
from pathlib import Path
import subprocess,hashlib,json,os,stat,time,shutil
b=Path(__file__).resolve().parent;names=['reference-elastic-s24-l1-n400-nu0','reference-mesh-backend-diagnostic','reference-kinematic-increment-fine-diagnostic','reference-mesh-increment-diagnostic'];out=b/'terminal-reference-fields-compression.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
commands=subprocess.check_output(['ps','-axo','command='],text=True).splitlines();proof={}
for name in names:
 w=b/name;assert not any(str(w)+'/' in c for c in commands)
 reports=[w/n for n in ['diagnostic.json','continuation-failure.json','process-result.json','completion.json'] if (w/n).exists()];assert reports;proof[name]={p.name:sha(p) for p in reports}
rows=[];beforefree=shutil.disk_usage(b).free
for name in names:
 for p in sorted((b/name).rglob('*')):
  if not p.is_file() or p.suffix not in ['.vtu','.bin']:continue
  assert not p.is_symlink();s=p.stat()
  if s.st_flags&stat.UF_COMPRESSED:continue
  assert s.st_nlink==1 and shutil.disk_usage(b).free>20*2**30+s.st_size+64*2**20
  digest=sha(p);temp=p.with_name(p.name+'.compressed-pending');assert not temp.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(temp)],check=True)
  assert temp.stat().st_size==s.st_size and sha(temp)==digest
  assert (p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino)==(s.st_size,s.st_mtime_ns,s.st_ino) and sha(p)==digest
  if temp.stat().st_blocks<s.st_blocks:
   os.replace(temp,p);assert sha(p)==digest;rows.append(dict(path=str(p),sha256=digest,bytes=s.st_size,allocated_before=s.st_blocks*512,allocated_after=p.stat().st_blocks*512))
  else:temp.unlink()
  if len(rows)%50==0:print('verified replacements',len(rows),flush=True)
for r in rows:assert sha(Path(r['path']))==r['sha256']
for name,reports in proof.items():
 for n,h in reports.items():assert sha(b/name/n)==h
out.write_text(json.dumps(dict(passed=True,terminal_reports=proof,files=rows,free_before=beforefree,free_after=shutil.disk_usage(b).free,allocated_reduction=sum(r['allocated_before']-r['allocated_after'] for r in rows),finished_unix=time.time(),scope='All selected terminal paths and bytes preserved including failed diagnostic evidence; no scientific pass inferred.'),indent=2)+'\n');print('Terminal field compression verified',len(rows),flush=True)
