from pathlib import Path
import importlib.util,json,numpy as np
b=Path(__file__).resolve().parent
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
wrapper=module('budget_wrapper',b/'audit-womersley-budget-streaming.py');original=module('budget_original',b/'audit-womersley-budget.py');mat=module('budget_baseline_materializer',b/'streaming-hdf-materialization.py');w=(b/'alpha2-s96-l1-n1600').resolve();base=original.TrackedStudy(w);receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-prefix8800-chunks').glob('*.json'));assert len(receipts)==20;store=mat.Volumes(w,receipts);expected={};hashes={}
try:
 for step in [8002,8400,8800]:
  path=base.generations[step][0]/'state_rank0.h5'
  with store.frame([path]):expected[step]=base.state(step);hashes[str(path.relative_to(w))]=original.sha(path)
 expected[8801]=base.state(8801)
finally:store.close()
cls,call,finish,reports=wrapper.adapter(original);actual=cls(w)
def check(sequence):
 for step in sequence:assert np.array_equal(expected[step],actual.state(step)),step
try:
 call(check,[8002,8400]);call(check,[8002,8400]);call(check,[8400,8801,8800])
 evidence=actual.evidence()
 for key,digest in hashes.items():assert evidence[key]==digest and not (w/key).exists()
finally:finish()
(b/'womersley-budget-fine-streaming-check.json').write_text(json.dumps(dict(passed=True,exact_arrays=True,sequences=[[8002,8400],[8002,8400],[8400,8801,8800]],archived_hashes=hashes,baseline=store.report(),passes=reports,scope='Actual archived fine prefix repeated passes, retained endpoint and reverse retained/archived order; full numerical budget pending.'),indent=2)+'\n');print('Actual fine repeated/retained-endpoint reads exact; archived hashes and cleanup pass')
