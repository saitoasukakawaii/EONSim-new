"""Bind complete fresh N1600 trajectory and analytic report, retaining failed gates."""
from pathlib import Path
import argparse,json,hashlib,shutil,re
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109'
p=argparse.ArgumentParser();p.add_argument('--alpha',type=int,choices=[2],required=True);args=p.parse_args()
name=f'alpha{args.alpha}-s96-l1-n1600';w=b/name;e=root/f'docs/research/data/macos-{name}-2026-11-09';assert not e.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
definition=json.loads((w/'definition.json').read_text());assert definition['steps_per_cycle']==definition['phases']==1600 and definition['warmup']==2 and definition['tau'] is None and definition.get('stabilization_time_scale') is None
if not (w/'receipt.json').exists() or json.loads((w/'receipt.json').read_text())['step']!=9600:raise RuntimeError('Incomplete N1600 trajectory; no completion evidence written')
a_path=b/(name+'-analysis.json');execution_path=b/(name+'.execution.json');a=json.loads(a_path.read_text());receipt=json.loads((w/'receipt.json').read_text());execution=json.loads(execution_path.read_text());assert receipt['step']==9600 and execution['exit_code']==0 and a['last_cycle']==6 and a['definition']==receipt['definition']
steps=[]
for i in range(1,7):
 d=w/f'attempt-{i:03}';t=(d/'solve.log').read_text();current=list(map(int,re.findall(r'^fluid_step=(\d+) ',t,re.M)));assert current==list(range((i-1)*1600+1,i*1600+1)) and t.rstrip().endswith('status=success');steps+=current
assert steps==list(range(1,9601))
import importlib.util
vp=b/'verify-womersley-n1600-cycle3-archives.py'
spec=importlib.util.spec_from_file_location('cycle3_archives',vp);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
files=module.verified_archived_rows(b)
for p in sorted(w.rglob('*')):
 if p.is_file():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
assert len({row['path'] for row in files})==len(files)
e.mkdir();shutil.copy2(vp,e/vp.name);dump(e/'raw-manifest.json',dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(x['bytes'] for x in files),scope='Complete fresh dataset hashes; cycle3 internal HDF in decoded/SHA-verified chunk archives, other files materialized locally. Restore archived members before whole-directory replay.'))
for n in ['definition.json','receipt.json','mesh-sha256.txt']:shutil.copy2(w/n,e/n)
shutil.copy2(a_path,e/'analysis.json');shutil.copy2(execution_path,e/'execution.json');shutil.copy2(Path(__file__),e/'capture.py')
dump(e/'completion.json',dict(accepted_steps=9600,cycles=6,numerical_exit_code=0,preliminary_gates=a['preliminary_gates'],all_preliminary_gates_passed=all(a['preliminary_gates'].values()),tau_control=False,source_sha256={n:sha(root/'scripts'/n) for n in ['study_womersley.py','analyze_womersley.py','compare_womersley.py']},qualification='Numerical trajectory and analytic diagnostics complete; independent budgets, tau decomposition and remaining production qualification are separate. Failed analytic gates remain failures.'))
(e/'README.md').write_text('# Fresh '+name+' complete trajectory\n\nAll9600 accepted steps from zero verified contiguous across six solve logs; complete original files hash bound, including decoded cycle3 archive members. Analytic and periodic gate outcomes are recorded in analysis.json and completion.json, including any failures. This is not full production qualification. This default-tau N1600 time control contributes to the N800 budget; it is not independently spatially qualified.\n')
print(json.dumps(dict(evidence=str(e),files=len(files),preliminary_gates=a['preliminary_gates'],metrics=a['metrics']),indent=2))
