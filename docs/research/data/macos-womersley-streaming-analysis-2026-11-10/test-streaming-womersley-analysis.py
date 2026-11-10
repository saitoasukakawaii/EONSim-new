from pathlib import Path
import importlib.util,json,hashlib,numpy as np
b=Path(__file__).resolve().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
wrapper=module('streaming_analysis',b/'analyze-womersley-n1600-streaming.py');m=module('hdf_restore',b/'streaming-hdf-materialization.py')
w=b/'alpha2-s96-l1-n1600';out=b/'streaming-womersley-analysis-check';out.mkdir()
base=wrapper.original.Study(w);steps=[4801,4802,6399,6400];paths=[base.generations[k][0]/'state_rank0.h5' for k in steps[:-1]]
assert all(not p.exists() for p in paths)
receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle4-chunks').glob('*.json'));store=m.Volumes(w,receipts)
try:
 with store.frame(paths):baseline=[base.state(k) for k in steps]
finally:store.close()
cls,stores=wrapper.make_study(wrapper.original,b)
try:
 study=cls(w);actual=[study.state(k) for k in steps]
finally:
 for store in stores.values():store.close()
assert all(np.array_equal(x,y) for x,y in zip(baseline,actual))
assert all(not p.exists() for p in paths)
assert (base.generations[6400][0]/'state_rank0.h5').exists()
store=m.Volumes(w,receipts)
try:
 try:
  with store.frame(paths[:1]):raise RuntimeError('consumer failure probe')
 except RuntimeError as e:assert str(e)=='consumer failure probe'
finally:store.close()
assert not paths[0].exists()
r=dict(passed=True,steps=steps,exact_state_equality=True,original_reader_used=True,retained_endpoint_preserved=True,consumer_failure_cleanup=True,all_restored_inputs_removed=True,wrapper_sha256=wrapper.sha(Path(wrapper.__file__)),materializer_sha256=wrapper.sha(Path(m.__file__)),analyzer_sha256=wrapper.sha(wrapper.ROOT/'scripts/analyze_womersley.py'),proof={str(w):s.report() for w,s in stores.items()},scope='Four real accepted states including three archived and one retained endpoint; not complete six-cycle analytic or budget acceptance')
(out/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='proof'}))
