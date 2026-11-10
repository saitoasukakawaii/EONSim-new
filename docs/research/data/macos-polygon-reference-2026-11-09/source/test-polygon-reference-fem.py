from pathlib import Path
import json,hashlib
import numpy as np
from polygon_reference_fem import Space,refine
x=np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.]]);t=np.array([[0,1,2],[0,2,3]])
for _ in range(3):x,t,_=refine(x,t)
s=Space(x,t);one=np.ones(len(s.nodes));assert abs(s.area-1)<1e-14;assert abs(s.squared(one)-1)<1e-14;assert np.max(abs(s.K@one))<1e-13
# Independent analytic integrals on the unit square, including degree-four mass.
xn,yn=s.nodes.T
assert abs(s.squared(xn**2+yn**2)-(2/5+2/9))<1e-13
cases=[]
for coef in [np.array([1,2,3,4,5,6],complex)*(1+2j),np.array([2+1j,-3j,4-2j,1j,2,3-1j]),np.array([-.5j,1,2j,-3,4j,2])]:
 def exact(p):
  x,y=p.T;return coef[0]+coef[1]*x+coef[2]*y+coef[3]*x*x+coef[4]*x*y+coef[5]*y*y
 alpha=2.;h,l,report,_=s.solve(alpha,lambda p:-2*(coef[3]+coef[5])+1j*alpha**2*exact(p),exact)
 error=float(np.max(abs((h-exact(s.nodes))+l)));assert error<1e-11;assert report['residual_history'][-1]<1e-11;cases.append(dict(maximum_nodal_error=error,**report))
result=dict(passed=True,nodes=len(s.nodes),triangles=len(t),manufactured=cases,scope='Independent P2 square patch/mass/manufactured verification only; polygon geometry and reference convergence not yet computed',sources={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['polygon_reference_fem.py','polygon_reference_dd.py']})
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
