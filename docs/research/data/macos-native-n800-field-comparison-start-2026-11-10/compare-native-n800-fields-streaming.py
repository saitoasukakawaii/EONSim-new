"""Original full800-phase cross-code P1 comparison with verified EON field restoration."""
from pathlib import Path
import importlib.util,json,hashlib,sys
b=Path(__file__).resolve().parent;root=b.parents[1];sys.path.insert(0,str(root/'scripts'))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
fields=module('native_cross_fields',b/'compare-pressure-fields.py')
reader=module('tested_tau_streaming_reader',b/'decompose-elastic-tau-time-streaming.py')
for name,row in json.loads((b/'pressure-comparison-source.json').read_text()).items():assert sha(b/name)==row['sha256']
assert sha(b/'streaming-volume-materialization.py')=='29e7f658b80f46499b6d3f445a73ba2b5b669cbc723d1315bafcb0c1018396cd'
case=b/'elastic-s24-l1-n800/case.json';leftwork=case.parent;rightwork=b/'reference-kinematic-elastic-s24-l1-n800-nu0-native25500'
leftaudit=b/'elastic-s24-l1-n800-audit.json';rightaudit=rightwork/'audit.json'
from svfsi_restart_evidence import analyze_chain
fresh=analyze_chain(rightwork/'chain.json',expected_work=rightwork,expected_steps=25600)
assert fresh==json.loads(rightaudit.read_text())['reference_convergence'] and fresh['passed']
adoption=json.loads((b/'reference-kinematic-adoption.json').read_text())
for segment in fresh['segments']:
 build=segment['reference_build'];assert build['base_commit']==adoption['base_commit'] and build['binary']['sha256']==adoption['binary_sha256'] and build['patch']['sha256']==adoption['patch_sha256']
out=b/'reference-native-n800-full-fields.json';proof=out.with_suffix('.materialization.json');assert not out.exists() and not proof.exists()
cls,stores=reader.make_study(fields)
left=cls(case,leftwork,leftaudit);right=cls(case,rightwork,rightaudit)
assert left.n==right.n==800 and left.steps==right.steps==25600
assert left.periodic_at(32) and right.periodic_at(32)
assert all(left.valid.values()) and all(right.valid.values())
try:
 result=fields.compare(left,right,32,32,800)
 result.update(helper_sha256=sha(b/'compare-pressure-fields.py'),wrapper_sha256=sha(Path(__file__)),reference_chain_sha256=sha(rightwork/'chain.json'),reference_adoption_sha256=sha(b/'reference-kinematic-adoption.json'),analysis_sources_sha256={name:sha(root/name) for name in ['scripts/audit_pressure_tube.py','scripts/analyze_womersley.py','scripts/compare_womersley.py','scripts/study_rigid_tube.py']})
 with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({k:v for k,v in result.items() if k!='input_files_sha256'},allow_nan=False),flush=True)
finally:
 for store in stores.values():store.close()
 with proof.open('x') as f:json.dump(dict(wrapper_sha256=sha(Path(__file__)),reader_sha256=sha(b/'decompose-elastic-tau-time-streaming.py'),materializer_sha256=sha(b/'streaming-volume-materialization.py'),stores={str(w):s.report() for w,s in stores.items()},scope='Unchanged full800-phase comparison. Exact archived EON bytes restored per frame; created copies removed after read. Reference native outputs retained; differences are diagnostic, no invented nodal gates or causal attribution.'),f,indent=2);f.write('\n')
