from pathlib import Path
import json,ast
import numpy as np
from polygon_reference_fem import Space,refine,rule,basis
# Exercise the exact driver's increment function without invoking its CLI.
p=Path(__file__).with_name('recompute-polygon-reference.py');tree=ast.parse(p.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='increment');scope=dict(np=np,rule=rule,basis=basis);exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope)
x=np.array([[0.,0.],[1.,0.],[.2,1.],[1.2,1.]]);t=np.array([[0,1,2],[1,3,2]]);coarse=Space(x,t);xf,tf,parents=refine(x,t);fine=Space(xf,tf)
def f(p):
 x,y=p.T;return (1+2j)+(3-4j)*x+(2+1j)*y+(1-3j)*x*x+(2j)*x*y+(5-2j)*y*y
old=(coarse,f(coarse.nodes),np.zeros(len(coarse.nodes),complex));h=f(fine.nodes);l=np.zeros_like(h);error=scope['increment'](fine,h,l,old,parents);assert error<1e-14
result=dict(passed=True,exact_quadratic_nested_relative_error=error,scope='Actual driver nested-field quadrature and parent mapping checked on skewed non-axis-aligned triangles');Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
