"""Independent80-digit scalar oracle, including cancellation and complex CSR rows."""
from pathlib import Path
import json,sys,decimal,hashlib
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import splu
from polygon_reference_dd import product,two_sum,residual,solve_refined
D=decimal.Decimal;decimal.getcontext().prec=80
def dec(x):return D.from_float(float(x))
rng=np.random.default_rng(9121);a=rng.uniform(-2,2,200);b=rng.uniform(-2,2,200)
for fn,oracle in [(product,lambda x,y:x*y),(two_sum,lambda x,y:x+y)]:
 hi,lo=fn(a,b)
 assert all(dec(h)+dec(l)==oracle(dec(x),dec(y)) for h,l,x,y in zip(hi,lo,a,b))
A=csr_matrix(np.array([[1e8+2j,1+3j,-1e8-2j,0],[0,0,0,0],[.3+4j,-2-.2j,.7+1j,3-.7j]],dtype=complex));xh=np.array([1+1j,1e-10+2e-10j,1+1j,.1-.2j]);xl=np.array([1e-18+2e-18j,-1e-27+1e-27j,0,1e-19-1e-19j]);rhs=np.array([3e-10+2e-10j,2-3j,.3-.4j]);rh,rl=residual(A,xh,xl,rhs);errors=[]
for row in range(A.shape[0]):
 real=dec(rhs[row].real);imag=dec(rhs[row].imag);scale=D(1)
 for k in range(A.indptr[row],A.indptr[row+1]):
  col=A.indices[k];v=A.data[k];ar,ai=dec(v.real),dec(v.imag);xr=dec(xh[col].real)+dec(xl[col].real);xi=dec(xh[col].imag)+dec(xl[col].imag)
  real-=ar*xr-ai*xi;imag-=ar*xi+ai*xr;scale+=abs(ar*xr)+abs(ai*xi)+abs(ar*xi)+abs(ai*xr)
 error=max(abs(dec(rh[row].real)+dec(rl[row].real)-real),abs(dec(rh[row].imag)+dec(rl[row].imag)-imag));assert error<D('1e-29')*scale;errors.append(str(error))
# Real solve with true complex residual. This tests the correction path using
# an intentionally perturbed initial LU solve, while subsequent solves are exact LU.
B=csr_matrix(np.array([[4+1j,-1,0],[-1,3+2j,-1],[0,-1,2+.5j]],complex));f=np.array([1+.2j,2-.3j,-.4+.1j]);factor=splu(B.tocsc())
class PerturbedInitial:
 calls=0
 def solve(self,r):
  x=factor.solve(r);self.calls+=1
  return x+(1e-5+2e-5j) if self.calls==1 else x
hi,lo,history=solve_refined(B,f,PerturbedInitial());assert len(history)>=2 and history[-1]<1e-11
out=dict(passed=True,scalar_error_free_cases=400,decimal_precision=80,csr_row_absolute_errors=errors,correction_residuals=history,longdouble_epsilon=float(np.finfo(np.longdouble).eps),float64_epsilon=float(np.finfo(np.float64).eps),source_sha256=hashlib.sha256(Path(__file__).with_name('polygon_reference_dd.py').read_bytes()).hexdigest(),scope='Arithmetic/correction verification only. No polygon FEM matrix or geometry result computed yet; original1e-11 gate unchanged.')
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
