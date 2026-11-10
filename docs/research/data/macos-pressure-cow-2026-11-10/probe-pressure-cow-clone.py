from pathlib import Path
import ctypes,hashlib,json,os
b=Path(__file__).resolve().parent;out=b/'pressure-cow-clone-probe.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
r=json.loads((b/'idle-reference-pressure-compression.json').read_text());row=r['files'][0];src=b/row['path'];assert sha(src)==row['sha256'] and not src.is_symlink();q=b/'pressure-cow-clone-probe.tmp';assert not q.exists()
lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True);clone=lib.clonefile;clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];clone.restype=ctypes.c_int
assert clone(os.fsencode(src),os.fsencode(q),0)==0,ctypes.get_errno()
assert sha(q)==row['sha256'] and q.stat().st_ino!=src.stat().st_ino and q.stat().st_nlink==1
with q.open('r+b') as f:
 value=f.read(1);f.seek(0);f.write(bytes([value[0]^1]));f.flush();os.fsync(f.fileno())
modified=sha(q);assert modified!=row['sha256'] and sha(src)==row['sha256'];q.unlink()
out.write_text(json.dumps(dict(passed=True,clonefile_return=0,source=str(src),source_sha256=row['sha256'],independent_inode=True,clone_modified_sha256=modified,source_unchanged_after_clone_write=True,temporary_removed=True,scope='Actual clonefile call with a compressed pressure input; mutation only to disposable clone, no production replacement yet'),indent=2)+'\n');print('clone succeeded; independent mutation verified; source unchanged')
