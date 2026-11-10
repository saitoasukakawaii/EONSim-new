from pathlib import Path
import importlib.util,json,numpy as np
b=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('wrapper',b/'analyze-womersley-n1600-streaming.py');wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
spec=importlib.util.spec_from_file_location('materializer',b/'streaming-hdf-materialization.py');mat=importlib.util.module_from_spec(spec);spec.loader.exec_module(mat)
w=b/'alpha2-s96-l1-n1600';receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-tail9360-chunks').glob('*.json'));baseline=wrapper.original.Study(w);store=mat.Volumes(w,receipts);expected={};steps=[8801,9080,9360,9361]
try:
 for step in steps:
  path=baseline.generations[step][0]/'state_rank0.h5'
  if step==9361:expected[step]=baseline.state(step)
  else:
   with store.frame([path]):expected[step]=baseline.state(step)
finally:store.close()
cls,stores=wrapper.make_study(wrapper.original,b);actual=cls(w)
try:
 for step in steps:assert np.array_equal(expected[step],actual.state(step)),step
finally:
 for s in stores.values():s.close()
for step in [8801,9080,9360]:assert not (actual.generations[step][0]/'state_rank0.h5').exists()
report=dict(passed=True,steps=steps,exact_arrays=True,baseline_restoration=store.report(),streamed_restoration={str(w):s.report() for w,s in stores.items()},scope='Three archived tail states and retained9361 endpoint match original reader exactly; full9600 analytic audit pending')
(b/'womersley-cycle6-tail-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Four states match exactly; restored copies removed')
