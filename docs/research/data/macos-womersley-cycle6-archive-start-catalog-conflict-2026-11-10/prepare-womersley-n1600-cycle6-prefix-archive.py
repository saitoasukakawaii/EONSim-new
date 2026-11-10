"""Snapshot published immutable HDF generations8001..8800 behind active writer."""
from pathlib import Path
import json,hashlib,re,subprocess
b=Path(__file__).resolve().parent;root=b.parents[1];w=b/'alpha2-s96-l1-n1600';out=b/(w.name+'-cycle6-prefix8800-before-archive.json');assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
d=json.loads((w/'definition.json').read_text());execution=json.loads(w.with_suffix('.execution.json').read_text());assert sha(w/'eonsim')==d['executable_sha256'] and d['steps_per_cycle']==1600 and d['phases']==1600 and d['ranks']==1
frozen=subprocess.check_output(['git','show',execution['source_commit']+':src/physics/fluid.cpp'],cwd=root);current=(root/'src/physics/fluid.cpp').read_bytes();assert frozen==current
assert current.index(b'write_checkpoint(comm,config.checkpoint,mesh,signature,saved);')<current.index(b'"fluid_step="')
raw=(w/'attempt-006/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fluid_step=(\d+) ',raw,re.M)));assert steps==list(range(8001,steps[-1]+1)) and steps[-1]>8800
marker,generation=(w/'checkpoint/current').read_text().split();assert marker=='EONSim_checkpoint_v4';cp=w/'checkpoint'/generation;assert int((cp/'manifest').read_text().split()[2])>8800
files=[]
for p in (w/'checkpoint').glob('generation_*/manifest'):
 fields=p.read_text().split();assert fields[:2]==['EONSim_checkpoint_v4','1'];step=int(fields[2])
 if not 8001<=step<=8800:continue
 q=p.parent/'state_rank0.h5';assert q.parent!=cp and not q.is_symlink();before=q.stat();digest=sha(q);after=q.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 files.append(dict(path=str(q.relative_to(w)),bytes=after.st_size,sha256=digest,step=step,checkpoint_manifest=str(p.relative_to(w)),checkpoint_manifest_sha256=sha(p),checkpoint_manifest_text=p.read_text()))
assert len(files)==800 and {x['step'] for x in files}==set(range(8001,8801))
out.write_text(json.dumps(dict(work=str(w),files=sorted(files,key=lambda x:x['path']),count=800,definition_sha256=sha(w/'definition.json'),accepted_log_prefix_bytes=len(raw),accepted_log_prefix_sha256=hashlib.sha256(raw).hexdigest(),last_complete_step=steps[-1],frozen_source_commit=execution['source_commit'],fluid_source_sha256=hashlib.sha256(frozen).hexdigest(),published_current_manifest_sha256=sha(cp/'manifest'),scope='Only800 immutable published checkpoint payloads8001..8800 behind current writer; original source writes checkpoint before accepted log. No whole-cycle6 completion claim.'),indent=2)+'\n');print('Verified800 immutable published checkpoint payloads')
