"""Bind complete fresh N800 trajectory and analytic report, retaining failed gates."""
from pathlib import Path
import argparse,json,hashlib,shutil,re
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109'
p=argparse.ArgumentParser();p.add_argument('--alpha',type=int,choices=[2],required=True);p.add_argument('--tau-control',action='store_true');args=p.parse_args();assert not args.tau_control
name=f'alpha{args.alpha}-s96-l0-n800'+('-tautime-n400' if args.tau_control else '');w=b/name;e=root/f'docs/research/data/macos-{name}-2026-11-09';assert not e.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
a_path=b/(name+'-analysis.json');execution_path=b/(name+'.execution.json');a=json.loads(a_path.read_text());receipt=json.loads((w/'receipt.json').read_text());execution=json.loads(execution_path.read_text());assert receipt['step']==4800 and execution['exit_code']==0 and a['last_cycle']==6 and a['definition']==receipt['definition'] and a['definition']['level']==0
steps=[]
for i in range(1,7):
 d=w/f'attempt-{i:03}';t=(d/'solve.log').read_text();current=list(map(int,re.findall(r'^fluid_step=(\d+) ',t,re.M)));assert current==list(range((i-1)*800+1,i*800+1)) and t.rstrip().endswith('status=success');steps+=current
assert steps==list(range(1,4801))
files=[]
for p in sorted(w.rglob('*')):
 if p.is_file():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
e.mkdir();dump(e/'raw-manifest.json',dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(x['bytes'] for x in files),scope='Complete fresh local dataset hashes; raw trajectories remain local'))
for n in ['definition.json','receipt.json','mesh-sha256.txt']:shutil.copy2(w/n,e/n)
shutil.copy2(a_path,e/'analysis.json');shutil.copy2(execution_path,e/'execution.json');shutil.copy2(Path(__file__),e/'capture.py')
dump(e/'completion.json',dict(accepted_steps=4800,cycles=6,numerical_exit_code=0,preliminary_gates=a['preliminary_gates'],all_preliminary_gates_passed=all(a['preliminary_gates'].values()),tau_control=args.tau_control,source_sha256={n:sha(root/'scripts'/n) for n in ['study_womersley.py','analyze_womersley.py','compare_womersley.py']},qualification='Numerical trajectory and analytic diagnostics complete; independent budgets, tau decomposition and remaining production qualification are separate. Failed analytic gates remain failures.'))
(e/'README.md').write_text('# Fresh '+name+' complete trajectory\n\nAll4800 accepted steps from zero verified contiguous across six solve logs; complete original files hash bound. Analytic and periodic gate outcomes are recorded in analysis.json and completion.json, including any failures. This is not full production qualification. For a tau-time control, only the explicit time term is fixed; other tau terms evolve and this run cannot substitute for default-tau acceptance.\n')
print(json.dumps(dict(evidence=str(e),files=len(files),preliminary_gates=a['preliminary_gates'],metrics=a['metrics']),indent=2))
