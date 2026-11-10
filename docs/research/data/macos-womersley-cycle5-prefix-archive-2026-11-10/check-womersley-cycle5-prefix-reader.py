from pathlib import Path
import importlib.util,json,numpy as np
b=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('wrapper',b/'analyze-womersley-n1600-streaming.py');wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
spec=importlib.util.spec_from_file_location('materializer',b/'streaming-hdf-materialization.py');mat=importlib.util.module_from_spec(spec);spec.loader.exec_module(mat)
w=b/'alpha2-s96-l1-n1600';receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle5-prefix7200-chunks').glob('*.json'));baseline=wrapper.original.Study(w);store=mat.Volumes(w,receipts);expected={};steps=[6400,6401,6800,7200,7201]
try:
 for step in steps:
  path=baseline.generations[step][0]/'state_rank0.h5'
  if step in [6400,7201]:expected[step]=baseline.state(step)
  else:
   with store.frame([path]):expected[step]=baseline.state(step)
finally:store.close()
cls,stores=wrapper.make_study(wrapper.original,b);actual=cls(w)
try:
 for step in steps:assert np.array_equal(expected[step],actual.state(step)),step
finally:
 for s in stores.values():s.close()
for step in [6401,6800,7200]:assert not (actual.generations[step][0]/'state_rank0.h5').exists()
report=dict(passed=True,steps=steps,exact_arrays=True,baseline_restoration=store.report(),streamed_restoration={str(w):s.report() for w,s in stores.items()},scope='Three archived prefix states and two retained boundary states match original reader exactly; full9600 analytic audit pending')
(b/'womersley-cycle5-prefix-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Five states match exactly; restored copies removed')
