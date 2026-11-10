from pathlib import Path
import json,hashlib,math,shutil
b=Path(__file__).resolve().parent;root=b.parents[1];p=b/'alpha2-tau-decomposition.json';d=json.loads(p.read_text());budget=json.loads((b/'alpha2-n400-budget.json').read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert d['common_phases']==400 and d['cycle']==6 and d['maximum_node_closure']<1e-15
for k,row in d['fields'].items():
 n=row['relative_rms'];v=n['timestep_path']**2+n['tau_time_path']**2+2*row['cross_inner']
 assert math.isclose(v,n['total']**2,rel_tol=1e-11,abs_tol=0)
 assert math.isclose(n['total'],budget['fields'][k]['terms']['time']['relative_rms'],rel_tol=1e-12,abs_tol=0)
count=0
for work,files in d['input_sha256'].items():
 for rel,digest in files.items():assert sha(Path(work)/rel)==digest;count+=1
for field in ['analysis_sha256','source_sha256']:
 for name,digest in d[field].items():assert sha(Path(name))==digest
assert budget['passed'] is False
out=root/'docs/research/data/macos-alpha2-tau-decomposition-2026-11-09';out.mkdir(exist_ok=False)
for src,name in [(p,'decomposition.json'),(Path(__file__),'check.py'),(b/'decompose-womersley-tau-time.py','decompose-womersley-tau-time.py'),(b/'alpha2-tau-decomposition.log','execution.log')]:shutil.copy2(src,out/name)
r=dict(passed=True,decomposition_sha256=sha(p),consumed_files_rehashed=count,default_total_matches_original_budget=True,default_budget_still_failed=True,scope='Report energy identity and original default total independently checked; all consumed input files rehashed. Path decomposition does not prove pure temporal error.')
(out/'independent-energy-check.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
