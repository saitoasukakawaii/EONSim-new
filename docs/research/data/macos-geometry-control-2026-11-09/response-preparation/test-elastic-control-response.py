"""Observable arithmetic checks only; no actual control response claim."""
import importlib.util,json
from pathlib import Path
b=Path(__file__).resolve().parent;p=b/'compare-elastic-control-response.py';s=importlib.util.spec_from_file_location('control',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=dict(mean=2.,amplitude=3.,phase_degrees=179.);c=dict(mean=3.,amplitude=6.,phase_degrees=-179.);r=m.response(a,c)
assert r['mean_relative_to_baseline']==.5 and r['amplitude_relative_to_baseline']==1 and r['phase_difference_degrees']==2
z=dict(mean=0.,amplitude=0.,phase_degrees=0.);r=m.response(z,z);assert r['phase_difference_degrees'] is None and r['amplitude_relative_to_baseline'] is None
works=[b/'elastic-s24-l1-n800',b/'elastic-s24-l1-n800-length24'];assert json.loads((works[0]/'case.json').read_text())==json.loads((works[1]/'case.json').read_text())
d=[json.loads((w/'definition.json').read_text()) for w in works]
assert all(d[0][k]==d[1][k] for k in ['binary_sha256','solver_options','ranks','threads'])
# Verify actual equal axial spacing and cross-sectional nodes before full runs finish.
for name in ['fluid.msh','solid.msh']:
 data=[m.tube.read_mesh(w/name) for w in works];axes=[sorted({v[0] for v in row[0].values()}) for row in data]
 assert all(abs(y-x-.5)<1e-12 for ax in axes for x,y in zip(ax,ax[1:]))
 assert {(v[1],v[2]) for v in data[0][0].values()}=={(v[1],v[2]) for v in data[1][0].values()}
print('Observable arithmetic/wrapped phase/undefined phase and actual length-input consistency checks passed; no actual control response computed.')
