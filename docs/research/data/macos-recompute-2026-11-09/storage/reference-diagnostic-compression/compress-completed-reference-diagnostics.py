"""Byte-preserving filesystem compression of terminal reference diagnostic frames."""
from pathlib import Path
import subprocess,hashlib,json,os,stat,time
b=Path(__file__).resolve().parent;names=['reference-kinematic-increment-startup','reference-strict-increment-startup','reference-fine-backend-screen'];report=b/'completed-reference-diagnostics-compression.json';assert not report.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
processes=subprocess.check_output(['ps','-axo','comm='],text=True).splitlines();proof={}
for name in names:
 w=b/name;p=w/('report.json' if 'screen' in name else 'diagnostic.json');d=json.loads(p.read_text());assert d['runs'] and all(r['exit_code']==0 for r in d['runs'].values())
 assert not any(str(w)+'/' in c for c in processes),'Active process under selected diagnostic'
 proof[name]=dict(terminal_report_sha256=sha(p),runs=d['runs'])
rows=[];started=time.time()
try:
 for name in names:
  w=b/name
  for p in sorted(w.rglob('*.vtu')):
   assert p.is_file() and not p.is_symlink();before=p.stat()
   if before.st_size<65536 or before.st_flags&stat.UF_COMPRESSED:continue
   digest=sha(p);temp=p.with_name(p.name+'.compressed-pending');assert not temp.exists()
   subprocess.run(['ditto','--hfsCompression',str(p),str(temp)],check=True)
   assert temp.stat().st_size==before.st_size and sha(temp)==digest
   assert (p.stat().st_size,p.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns) and sha(p)==digest
   if temp.stat().st_blocks<before.st_blocks:
    os.replace(temp,p);assert sha(p)==digest
    rows.append(dict(path=str(p.relative_to(b)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
   else:temp.unlink()
 result=dict(terminal_evidence=proof,files=rows,seconds=time.time()-started,logical_content_unchanged=True,saved_allocated_bytes=sum(x['allocated_before']-x['allocated_after'] for x in rows),source_sha256=sha(Path(__file__)))
 report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('files','terminal_evidence')}),'files',len(rows))
except BaseException as e:
 report.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),terminal_evidence=proof,verified_replacements=rows),indent=2)+'\n');raise
