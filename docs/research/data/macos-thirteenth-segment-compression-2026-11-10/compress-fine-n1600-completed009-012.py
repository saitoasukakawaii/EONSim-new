"""Transparent filesystem compression, verified bytes before replacing originals."""
from pathlib import Path
import subprocess,hashlib,json,os,stat,time
w=Path(__file__).resolve().parent/'elastic-s24-l1-n1600'
selected=[];receipts=[]
import re
pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu$')
for segment in range(9,13):
 label=f'dense-{segment:03d}';receipt=json.loads((w/label/'receipt.json').read_text());receipts.append(receipt)
 assert receipt['exit_code']==0 and receipt['accepted_first']==46401+(segment-1)*256 and receipt['accepted_last']==46400+segment*256
 assert (w/label/'solve.log').read_text().rstrip().endswith('status=success')
 groups={}
 for p in sorted((w/label).glob('*.vtu')):
  m=pattern.fullmatch(p.name)
  if not m:continue
  step=int(m[1]);groups.setdefault(step,set()).add(m[2] or '');selected.append(p)
 assert set(groups)==set(range(receipt['accepted_first'],receipt['accepted_last']+1))
 assert all(v=={'','_boundary','_solid','_solid_boundary'} for v in groups.values())
report=w.parent/'elastic-fine-n1600-completed-segments009-012-compression.json';assert not report.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
rows=[];started=time.time()
try:
 for p in selected:
  if not p.is_file() or p.is_symlink() or p.suffix != '.vtu' or p.stat().st_size<65536:continue
  before=p.stat()
  if before.st_flags & stat.UF_COMPRESSED:continue
  digest=sha(p);temp=p.with_name(p.name+'.compressed-pending');assert not temp.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(temp)],check=True)
  assert temp.stat().st_size==before.st_size and sha(temp)==digest
  assert p.stat().st_mtime_ns==before.st_mtime_ns and sha(p)==digest
  compressed=temp.stat()
  if compressed.st_blocks<before.st_blocks:
   os.replace(temp,p);assert sha(p)==digest
   rows.append(dict(path=str(p.relative_to(w)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
  else:temp.unlink() # Verified duplicate only; original remains.
 result=dict(root=str(w),receipts=receipts,selected_files=len(selected),files=rows,seconds=time.time()-started,logical_content_unchanged=True,saved_allocated_bytes=sum(x['allocated_before']-x['allocated_after'] for x in rows));report.write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='files'},'files',len(rows))
except BaseException as e:
 report.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),verified_replacements=rows),indent=2)+'\n');raise
