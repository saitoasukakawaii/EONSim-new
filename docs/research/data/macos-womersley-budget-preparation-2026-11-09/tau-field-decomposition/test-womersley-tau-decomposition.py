"""Exact P1 cancellation and actual intervention/completeness input checks."""
import importlib.util,numpy as np,json,copy
from pathlib import Path
p=Path(__file__).with_name('decompose-womersley-tau-time.py');spec=importlib.util.spec_from_file_location('tau',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Mesh:cells=np.array([[0,1,2,3]]);volumes=np.array([1/6])
x=np.array([[1.,2.]]*4);y=-x
assert abs(m.inner(Mesh,x,x)-5/6)<1e-15
assert abs(m.inner(Mesh,x,y)+5/6)<1e-15
assert m.inner(Mesh,x+y,x+y)==0
b=p.parent;names=['alpha1-s96-l1-n400','alpha1-s96-l1-n800-tautime-n400','alpha1-s96-l1-n800'];d=[json.loads((b/n/'definition.json').read_text()) for n in names];r=[dict(step=6*v['steps_per_cycle']) for v in d];assert m.validate(d,r)==400
bad=copy.deepcopy(d);bad[1]['tau_time_scale']*=2
try:m.validate(bad,r)
except ValueError:pass
else:raise AssertionError('Wrong tau time accepted')
r[1]['step']-=1
try:m.validate(d,r)
except ValueError:pass
else:raise AssertionError('Incomplete study accepted')
print('Exact P1 constant/cancellation checks and intervention/completeness checks passed; actual full decomposition not run.')
