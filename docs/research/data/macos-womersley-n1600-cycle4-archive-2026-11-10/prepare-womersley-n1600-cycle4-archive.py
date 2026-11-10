"""Snapshot immutable non-endpoint cycle4 checkpoints after completed cycle4 solve."""
from pathlib import Path
import json,hashlib,re
b=Path(__file__).resolve().parent;w=b/'alpha2-s96-l1-n1600';out=b/(w.name+'-cycle4-before-archive.json')
assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
r=json.loads((w/'receipt.json').read_text());d=json.loads((w/'definition.json').read_text());assert r['step']>=6400 and d['steps_per_cycle']==1600 and d['phases']==1600 and d['warmup']==2 and d['ranks']==1
t=(w/'attempt-004/solve.log').read_text();assert list(map(int,re.findall(r'^fluid_step=(\d+) ',t,re.M)))==list(range(4801,6401)) and t.rstrip().endswith('status=success')
pointer=(w/'checkpoint/current').read_text().split();assert pointer[0]=='EONSim_checkpoint_v4'
current=w/'checkpoint'/pointer[1];assert int((current/'manifest').read_text().split()[2])>6400
files=[];endpoints=set()
for p in (w/'checkpoint').glob('generation_*/manifest'):
 fields=p.read_text().split();assert fields[0]=='EONSim_checkpoint_v4' and fields[1]=='1'
 step=int(fields[2])
 if step in [1600,3200,4800,6400]:endpoints.add(step);assert (p.parent/'state_rank0.h5').is_file()
 if not 4800<step<6400:continue
 q=p.parent/'state_rank0.h5';assert q.parent!=current and not q.is_symlink();before=q.stat();digest=sha(q);after=q.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 files.append(dict(path=str(q.relative_to(w)),bytes=after.st_size,sha256=digest,step=step,checkpoint_manifest=str(p.relative_to(w)),checkpoint_manifest_sha256=sha(p),checkpoint_manifest_text=p.read_text()))
assert endpoints=={1600,3200,4800,6400} and len(files)==1599 and {r['step'] for r in files}==set(range(4801,6400))
out.write_text(json.dumps(dict(work=str(w),files=sorted(files,key=lambda r:r['path']),count=len(files),definition_sha256=sha(w/'definition.json'),completed_log_sha256=sha(w/'attempt-004/solve.log'),scope='Only immutable cycle4 internal HDF; endpoints/current and cycles5/6 retained; cycle3 previously archived. No completion or physical qualification claimed.'),indent=2)+'\n');print('Captured',len(files),'immutable cycle4 states',flush=True)
