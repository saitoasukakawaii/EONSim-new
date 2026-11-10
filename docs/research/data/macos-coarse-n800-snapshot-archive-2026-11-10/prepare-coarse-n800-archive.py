from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l0-n800';out=b/'coarse-n800-raw-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
ps=subprocess.check_output(['ps','-axo','pid=,command='],text=True);assert str(w) not in ps and 'recompute-20261109/elastic-s24-l0-n800' not in ps
c=json.loads((w/'completion-postflight.json').read_text());assert c['accepted_steps']==25600 and all(r['exit_code']==0 for r in c['receipts'])
for key in ['input_sha256','index_sha256']:
 for rel,digest in c[key].items():assert sha(w/rel)==digest
files=[]
for p in sorted(w.rglob('*')):
 assert not p.is_symlink()
 if p.is_file():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
out.write_text(json.dumps(dict(local_root=str(w),files=files,count=len(files),completion_sha256=sha(w/'completion-postflight.json'),scope='Terminal numerical phases and repaired indexes; original collection failure retained. Full current raw inventory, no new physical qualification.'),indent=2)+'\n');print('captured',len(files))
