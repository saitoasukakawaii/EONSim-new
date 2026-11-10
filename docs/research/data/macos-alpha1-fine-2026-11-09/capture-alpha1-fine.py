from pathlib import Path
import json,hashlib,shutil,re
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109';w=b/'alpha1-s96-l1-n400';e=root/'docs/research/data/macos-alpha1-fine-2026-11-09';e.mkdir()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
a=json.loads((b/'alpha1-s96-l1-n400-analysis.json').read_text());receipt=json.loads((w/'receipt.json').read_text());execution=json.loads((b/'alpha1-s96-l1-n400.execution.json').read_text());assert receipt['step']==2400 and execution['exit_code']==0 and all(a['preliminary_gates'].values())
steps=[]
for i in range(1,7):
 d=w/f'attempt-{i:03}';t=(d/'solve.log').read_text();current=list(map(int,re.findall(r'^fluid_step=(\d+) ',t,re.M)));assert current==list(range((i-1)*400+1,i*400+1)) and t.rstrip().endswith('status=success');steps+=current
assert steps==list(range(1,2401))
files=[]
for p in sorted(w.rglob('*')):
 if p.is_file():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
dump(e/'raw-manifest.json',dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(x['bytes'] for x in files),scope='Complete fresh local dataset hashes, raw trajectories not embedded/uploaded'))
for name in ('definition.json','receipt.json','mesh-sha256.txt'):shutil.copy2(w/name,e/name)
for name,target in [('alpha1-s96-l1-n400-analysis.json','analysis.json'),('alpha1-s96-l1-n400.execution.json','execution.json')]:shutil.copy2(b/name,e/target)
dump(e/'completion.json',dict(accepted_steps=2400,cycles=6,numerical_exit_code=0,analysis_exit_code=0,preliminary_gates=a['preliminary_gates'],source_sha256={name:sha(root/'scripts'/name) for name in ('study_womersley.py','analyze_womersley.py','compare_womersley.py')},qualification='Analytic/periodic gates pass; independent time/space/tail/sampling budget, geometry and remaining production evidence still required'))
(e/'README.md').write_text('''# Fresh alpha1 S96 level1 N400: analytic and periodic gates pass

All2400 contiguous accepted steps from zero were checked in the six original
solve logs. Session93103 ended0; analysis87037 ended0. BDF2/defaulttau, serial
MUMPS/LU32/chord, two computed warmup cycles then every phase saved.

Velocity relativeL2 .4284161805%, pressureRMS/amplitude .4019189207%, flow
amplitude .2078921825%, phase .0230144475 degrees; maximum netflux1.5663e-17.
Last cycle differences velocity6.3299e-15/pressure6.1378e-15; preceding cycle
also below1e-6. All original analytic/periodic gates pass.

This does not prove independent10% time/tail/sampling budgets. Matched fineN800
is still computing; use the prepared budget entry only after complete six cycles
and analysis. CoarseN400 flow failure remains preserved. All fresh raw files are
hashed in raw-manifest.json and stay locally, not uploaded by this evidence.
No old-workspace raw input, relaxed gate or production completion claim.
''')
print(json.dumps(dict(files=len(files),bytes=sum(x['bytes'] for x in files),metrics=a['metrics']),indent=2))
