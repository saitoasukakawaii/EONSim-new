from pathlib import Path
import importlib.util,json,numpy as np
b=Path(__file__).resolve().parent
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
wrapper=module('budget_wrapper',b/'audit-womersley-budget-streaming.py');original=module('budget_original',b/'audit-womersley-budget.py');mat=module('budget_baseline_materializer',b/'streaming-hdf-materialization.py');w=(b/'alpha2-s96-l1-n800').resolve();base=original.TrackedStudy(w);receipt=b/'archives/alpha2-s96-l1-n800-late-capacity-materialization.json';store=mat.Volumes(w,[receipt]);expected={};hashes={}
try:
 for step in [3201,4001,4002]:
  path=base.generations[step][0]/'state_rank0.h5'
  with store.frame([path]):expected[step]=base.state(step);hashes[str(path.relative_to(w))]=original.sha(path)
 expected[4000]=base.state(4000)
finally:store.close()
cls,call,finish,reports=wrapper.adapter(original);actual=cls(w)
def check(sequence):
 for step in sequence:assert np.array_equal(expected[step],actual.state(step)),step
try:
 call(check,[3201,4001]);call(check,[3201,4001]);call(check,[4001,4000,4002])
 evidence=actual.evidence()
 for key,digest in hashes.items():assert evidence[key]==digest and not (w/key).exists()
finally:finish()
(b/'womersley-budget-streaming-check.json').write_text(json.dumps(dict(passed=True,exact_arrays=True,sequences=[[3201,4001],[3201,4001],[4001,4000,4002]],archived_hashes=hashes,baseline=store.report(),passes=reports,scope='Actual archived target repeated passes, interleaved cycles, retained endpoint and sampling read order; full numerical budget pending.'),indent=2)+'\n');print('Actual repeated/cycle-interleaved/sampling reads exact; archived hashes and cleanup pass')
