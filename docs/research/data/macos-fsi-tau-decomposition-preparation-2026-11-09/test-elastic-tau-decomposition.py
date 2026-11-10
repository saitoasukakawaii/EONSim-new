from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,copy,math
import numpy as np
p=Path(__file__).with_name('decompose-elastic-tau-time.py');spec=importlib.util.spec_from_file_location('decomposition',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rng=np.random.default_rng(93271);worst=0.;cases=0
# Independent degree-two tetrahedron quadrature, including non-orthogonal fields and cancellation.
a=(5+3*math.sqrt(5))/20;b=(5-math.sqrt(5))/20;Q=np.full((4,4),b);np.fill_diagonal(Q,a)
mesh=SimpleNamespace(cells=np.array([[0,1,2,3]]),volumes=np.array([.37]))
for components in [1,3]:
 for _ in range(30):
  x,y,z=[rng.normal(size=(4,components)) for i in range(3)]
  if _%3==0:z=x+1e-5*rng.normal(size=x.shape)
  row,closure=m.contributions(mesh,x,y,z);t=y-x;q=z-y;d=z-x
  for key,left,right in [('timestep_path',t,t),('tau_time_path',q,q),('total',d,d),('cross_inner',t,q)]:
   exact=.37*np.sum((Q@left)*(Q@right))/4
   error=abs(exact-row[key]);assert error<2e-14*max(1,abs(exact));worst=max(worst,error)
  assert closure<2e-15;cases+=1
base=Path(__file__).parent
configs=[json.loads((base/n/'case.json').read_text()) for n in ['elastic-s24-l1-n400','elastic-s24-l1-n800-tautime-n400','elastic-s24-l1-n800']]
assert m.configuration(configs)==400
rejected=[]
for name in ['wrong-tau','changed-viscosity','changed-ramp','wrong-time-scheme','wrong-clock','fixed-whole-tau']:
 bad=copy.deepcopy(configs)
 if name=='wrong-tau':bad[1]['fsi']['stabilization_time_scale']*=1.01
 elif name=='changed-viscosity':bad[1]['fsi']['viscosity']*=1.01
 elif name=='changed-ramp':bad[1]['fsi']['pressure_time']['ramp_time']*=.5
 elif name=='wrong-time-scheme':bad[1]['time']['scheme']='bdf2'
 elif name=='wrong-clock':bad[1]['fsi']['dt']*=2
 else:bad[1]['fsi']['stabilization_tau']=.01
 try:m.configuration(bad)
 except ValueError:rejected.append(name)
 else:raise AssertionError(name)
result=dict(passed=True,manufactured_cases=cases,maximum_quadrature_difference=worst,rejected=rejected,actual_three_case_configuration_checked=True,scope='Independent exact degree-two quadrature versus P1 bilinear product and config guards; no claim of completed physical decomposition.')
(base/'elastic-tau-decomposition-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
