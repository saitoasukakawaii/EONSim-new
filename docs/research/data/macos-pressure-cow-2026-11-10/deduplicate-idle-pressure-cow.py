from pathlib import Path
import ctypes,hashlib,json,os,shutil,subprocess,time
b=Path(__file__).resolve().parent;out=b/'idle-pressure-cow.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert json.loads((b/'pressure-cow-clone-probe.json').read_text())['passed']
rows=json.loads((b/'idle-reference-pressure-compression.json').read_text())['files']
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines()
for row in rows:
 p=b/row['path'];root=b/p.relative_to(b).parts[0]
 assert root.name!='reference-kinematic-elastic-s24-l1-n800-nu0'
 assert not any(str(root) in line or ('recompute-20261109/'+root.name) in line for line in processes)
 assert p.is_file() and not p.is_symlink() and sha(p)==row['sha256']
lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True);clone=lib.clonefile;clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];clone.restype=ctypes.c_int
free=shutil.disk_usage(b).free;groups={};done=[];start=time.time()
try:
 for row in rows:
  p=b/row['path'];key=(row['logical_bytes'],row['sha256'])
  if key not in groups:groups[key]=p;continue
  src=groups[key];before=p.stat();q=p.with_name(p.name+'.cow-pending');assert not q.exists()
  assert sha(src)==key[1] and sha(p)==key[1]
  assert clone(os.fsencode(src),os.fsencode(q),0)==0,ctypes.get_errno()
  assert q.stat().st_size==before.st_size and sha(q)==key[1]
  assert q.stat().st_ino!=src.stat().st_ino and q.stat().st_nlink==1
  os.chmod(q,before.st_mode&0o7777);os.utime(q,ns=(before.st_atime_ns,before.st_mtime_ns))
  assert p.stat().st_mtime_ns==before.st_mtime_ns and sha(p)==key[1]
  os.replace(q,p);assert sha(p)==key[1] and sha(src)==key[1]
  done.append(dict(path=row['path'],canonical=str(src.relative_to(b)),sha256=key[1],logical_bytes=before.st_size,independent_inode=p.stat().st_ino!=src.stat().st_ino))
 for row in rows:assert sha(b/row['path'])==row['sha256']
 result=dict(passed=True,files=done,verified_files=len(rows),unique_contents=len(groups),free_before=free,free_after=shutil.disk_usage(b).free,seconds=time.time()-start,source_sha256=sha(Path(__file__)),scope='Actual clonefile without fallback; independent inodes, all paths and logical SHA retained. Free-space delta is observed shared-filesystem change, not isolated allocation measurement.')
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
except BaseException as e:
 out.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),verified_replacements=done),indent=2)+'\n');raise
