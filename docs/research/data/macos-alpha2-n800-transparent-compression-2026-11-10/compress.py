"""Transparent filesystem compression, verified bytes before replacing originals."""
from pathlib import Path
import subprocess,hashlib,json,os,stat,time
w=Path(__file__).resolve().parent/'alpha2-s96-l1-n800'
assert json.loads((w/'receipt.json').read_text())['step']==4800
assert json.loads(w.with_suffix('.execution.json').read_text())['exit_code']==0
manifest=Path(__file__).resolve().parents[2]/'docs/research/data/macos-alpha2-s96-l1-n800-2026-11-09/raw-manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='9f516f1494b4e606c8eb2f6935b0f125ab196c2d13cf7f0819d70c51dbe64fe9'
expected={r['path']:r for r in json.loads(manifest.read_text())['files']}
report=w.parent/'alpha2-fine-n800-compression.json';assert not report.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
rows=[];started=time.time()
try:
 for p in sorted(w.rglob('*')):
  if not p.is_file() or p.is_symlink() or p.suffix not in ('.vtu','.h5') or p.stat().st_size<65536:continue
  before=p.stat()
  if before.st_flags & stat.UF_COMPRESSED:continue
  digest=sha(p);assert digest==expected[str(p.relative_to(w))]['sha256'] and before.st_size==expected[str(p.relative_to(w))]['bytes'];temp=p.with_name(p.name+'.compressed-pending');assert not temp.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(temp)],check=True)
  assert temp.stat().st_size==before.st_size and sha(temp)==digest
  assert p.stat().st_mtime_ns==before.st_mtime_ns and sha(p)==digest
  compressed=temp.stat()
  if compressed.st_blocks<before.st_blocks:
   os.replace(temp,p);assert sha(p)==digest
   rows.append(dict(path=str(p.relative_to(w)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
  else:temp.unlink() # Verified duplicate only; original remains.
 result=dict(root=str(w),original_manifest_sha256=sha(manifest),controller_sha256=sha(Path(__file__)),files=rows,seconds=time.time()-started,logical_content_unchanged=True,saved_allocated_bytes=sum(x['allocated_before']-x['allocated_after'] for x in rows));report.write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='files'},'files',len(rows))
except BaseException as e:
 report.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),verified_replacements=rows),indent=2)+'\n');raise
