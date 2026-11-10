"""Independent straight-triangle P2 complex scalar reference; no production solver."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from polygon_reference_dd import solve_refined
EDGES=((0,1),(1,2),(2,0))
def rule(order):
 x,w=np.polynomial.legendre.leggauss(order);x=(x+1)/2;w=w/2
 r,s=np.meshgrid(x,x,indexing='ij');wr,ws=np.meshgrid(w,w,indexing='ij')
 return np.stack(((1-r)*(1-s),r,(1-r)*s),axis=-1).reshape(-1,3),(wr*ws*(1-r)).ravel()
def basis(lam):
 return np.column_stack([*(lam[:,i]*(2*lam[:,i]-1) for i in range(3)),*(4*lam[:,i]*lam[:,j] for i,j in EDGES)])
def enrich(x,t):
 nodes=list(np.asarray(x));edges={};counts={};conn=[]
 for tri in t:
  row=list(tri)
  for i,j in EDGES:
   edge=tuple(sorted((int(tri[i]),int(tri[j]))));counts[edge]=counts.get(edge,0)+1
   if edge not in edges:edges[edge]=len(nodes);nodes.append((x[edge[0]]+x[edge[1]])/2)
   row.append(edges[edge])
  conn.append(row)
 boundary=set()
 for edge,count in counts.items():
  assert count in (1,2)
  if count==1:boundary.update((*edge,edges[edge]))
 return np.asarray(nodes),np.asarray(conn),np.array(sorted(boundary),dtype=int)
def refine(x,t):
 nodes,conn,_=enrich(x,t);result=[];parents=[]
 for parent,(a,b,c,ab,bc,ca) in enumerate(conn):
  result.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)));parents.extend([parent]*4)
 return nodes,np.asarray(result),np.asarray(parents)
def geometry(x,t):
 v=x[t];J=np.stack((v[:,1]-v[:,0],v[:,2]-v[:,0]),axis=-1);det=np.linalg.det(J)
 if np.any(det<=0):raise ValueError('Nonpositive triangle')
 grad=np.einsum('ij,tjk->tik',np.array([[-1.,-1.],[1.,0.],[0.,1.]]),np.linalg.inv(J))
 return v,det,grad
class Space:
 def __init__(self,x,t,order=4):
  self.vertices=np.asarray(x);self.triangles=np.asarray(t);self.nodes,self.conn,self.boundary=enrich(x,t)
  self.v,self.det,self.grad=geometry(x,t);self.lam,self.weights=rule(order);self.N=basis(self.lam)
  count=len(t);k=np.zeros((count,6,6));m=np.zeros_like(k)
  for lam,w,N in zip(self.lam,self.weights,self.N):
   g=np.stack([*((4*lam[i]-1)*self.grad[:,i] for i in range(3)),*(4*(lam[i]*self.grad[:,j]+lam[j]*self.grad[:,i]) for i,j in EDGES)],axis=1)
   k+=w*self.det[:,None,None]*np.einsum('tia,tja->tij',g,g)
   m+=w*self.det[:,None,None]*np.outer(N,N)[None,:,:]
  row=np.broadcast_to(self.conn[:,:,None],k.shape).ravel();col=np.broadcast_to(self.conn[:,None,:],k.shape).ravel();shape=(len(self.nodes),)*2
  self.K=coo_matrix((k.ravel(),(row,col)),shape=shape).tocsr();self.M=coo_matrix((m.ravel(),(row,col)),shape=shape).tocsr()
  self.free=np.setdiff1d(np.arange(len(self.nodes)),self.boundary);self.area=float(self.det.sum()/2)
 def load(self,fun):
  local=np.zeros((len(self.conn),6),dtype=complex)
  for lam,w,N in zip(self.lam,self.weights,self.N):
   points=np.einsum('i,tij->tj',lam,self.v);f=np.broadcast_to(fun(points),len(points))
   local+=(w*self.det*f)[:,None]*N[None,:]
  out=np.zeros(len(self.nodes),dtype=complex);np.add.at(out,self.conn.ravel(),local.ravel());return out
 def solve(self,alpha,forcing,boundary):
  A=(self.K+1j*alpha**2*self.M).tocsr();full=np.zeros(len(self.nodes),dtype=complex);full[self.boundary]=boundary(self.nodes[self.boundary]);b=self.load(forcing)[self.free]-A[self.free]@full
  reduced=A[self.free][:,self.free].tocsr();lu=splu(reduced.tocsc());xh,xl,history=solve_refined(reduced,b,lu)
  full[self.free]=xh;low=np.zeros_like(full);low[self.free]=xl
  return full,low,dict(residual_history=history,free_dofs=len(self.free)),(reduced,b)
 def squared(self,u):
  return float(np.real(np.vdot(u,self.M@u)))
