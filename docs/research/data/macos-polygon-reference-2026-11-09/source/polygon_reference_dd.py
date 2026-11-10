"""Double-double CSR residual for the fresh polygon reference, independent of longdouble."""
import numpy as np

def two_sum(a,b):
 s=a+b;v=s-a
 return s,(a-(s-v))+(b-v)

def product(a,b):
 p=a*b
 c=134217729.*a;ah=c-(c-a);al=a-ah
 c=134217729.*b;bh=c-(c-b);bl=b-bh
 return p,((ah*bh-p)+ah*bl+al*bh)+al*bl

def add(ah,al,bh,bl):
 s,e=two_sum(ah,bh);return two_sum(s,e+(al+bl))

def multiply(a,bh,bl):
 p,e=product(a,bh);return two_sum(p,e+a*bl)

def complex_add(ah,al,bh,bl):
 rh,rl=add(ah.real,al.real,bh.real,bl.real);ih,il=add(ah.imag,al.imag,bh.imag,bl.imag)
 return rh+1j*ih,rl+1j*il

def residual(A,xh,xl,b):
 """b-A*(xh+xl), accumulating real and imaginary CSR products as hi/lo pairs."""
 A=A.tocsr();n=A.shape[0];rh=np.zeros(n);rl=np.zeros(n);ih=np.zeros(n);il=np.zeros(n)
 for slot in range(int(np.max(np.diff(A.indptr),initial=0))):
  rows=np.flatnonzero(A.indptr[:-1]+slot<A.indptr[1:]);pos=A.indptr[rows]+slot;cols=A.indices[pos];v=A.data[pos]
  ph,pl=multiply(v.real,xh[cols].real,xl[cols].real);qh,ql=multiply(v.imag,xh[cols].imag,xl[cols].imag)
  th,tl=add(ph,pl,-qh,-ql);rh[rows],rl[rows]=add(rh[rows],rl[rows],th,tl)
  ph,pl=multiply(v.real,xh[cols].imag,xl[cols].imag);qh,ql=multiply(v.imag,xh[cols].real,xl[cols].real)
  th,tl=add(ph,pl,qh,ql);ih[rows],il[rows]=add(ih[rows],il[rows],th,tl)
 rh,rl=add(np.asarray(b).real,0.,-rh,-rl);ih,il=add(np.asarray(b).imag,0.,-ih,-il)
 return rh+1j*ih,rl+1j*il

def solve_refined(A,b,lu,limit=1e-11,maximum=5):
 xh=np.asarray(lu.solve(b),dtype=np.complex128);xl=np.zeros_like(xh);history=[];den=np.linalg.norm(b)
 if den==0:raise ValueError('Reference requires nonzero right hand side')
 for iteration in range(maximum+1):
  rh,rl=residual(A,xh,xl,b);ratio=float(np.linalg.norm(rh+rl)/den);history.append(ratio)
  if not np.isfinite(ratio):raise ValueError('Nonfinite residual')
  if ratio<limit:return xh,xl,history
  if iteration<maximum:xh,xl=complex_add(xh,xl,lu.solve(rh+rl),np.zeros_like(xh))
 raise ValueError('Original true residual gate failed: '+repr(history))
