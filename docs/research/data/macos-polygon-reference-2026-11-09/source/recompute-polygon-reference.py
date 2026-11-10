"""Fresh polygon reference and unchanged numerical gates; keep every level's state."""
from pathlib import Path
import sys,json,time,hashlib,argparse,decimal
import numpy as np
from scipy.special import jv
from polygon_reference_fem import Space,refine,rule,basis
from polygon_reference_dd import residual
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube
from womersley_reference import flow_amplitude
p=argparse.ArgumentParser();p.add_argument('--sectors',type=int,choices=[48,96],required=True);a=p.parse_args();out=Path(__file__).resolve().parent/f'polygon-reference-s{a.sectors}';assert not out.exists();out.mkdir()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def decimal_rows(A,b,h,l):
 decimal.getcontext().prec=80;D=decimal.Decimal;dec=lambda x:D.from_float(float(x));rh,rl=residual(A,h,l,b);errors=[]
 for row in sorted(set([0,len(b)//3,len(b)//2,len(b)-1])):
  rr=dec(b[row].real);ii=dec(b[row].imag);scale=D(1)
  for k in range(A.indptr[row],A.indptr[row+1]):
   col=A.indices[k];v=A.data[k];ar,ai=dec(v.real),dec(v.imag);xr=dec(h[col].real)+dec(l[col].real);xi=dec(h[col].imag)+dec(l[col].imag)
   rr-=ar*xr-ai*xi;ii-=ar*xi+ai*xr;scale+=abs(ar*xr)+abs(ai*xi)+abs(ar*xi)+abs(ai*xr)
  error=max(abs(dec(rh[row].real)+dec(rl[row].real)-rr),abs(dec(rh[row].imag)+dec(rl[row].imag)-ii));assert error<D('1e-29')*scale;errors.append(dict(row=row,absolute_error=str(error)))
 return errors
def metrics(s,h,l,alpha,order):
 lam,w=rule(order);N=basis(lam);error=norm=0.;Q=0j;z=np.sqrt(-1j)*alpha
 for bary,weight,shape in zip(lam,w,N):
  points=np.einsum('i,tij->tj',bary,s.v);r=np.linalg.norm(points,axis=1);ref=.01/(1j*alpha**2)*(1-jv(0,z*r)/jv(0,z));v=h[s.conn]@shape+l[s.conn]@shape;weights=weight*s.det
  error+=np.sum(weights*abs(v-ref)**2);norm+=np.sum(weights*abs(ref)**2);Q+=np.sum(weights*v)
 qr=flow_amplitude(alpha);return dict(velocity_relative_l2=float(np.sqrt(error/norm)),flow_amplitude_relative=float(abs(abs(Q)-abs(qr))/abs(qr)),flow_phase_degrees=float(abs(np.angle(Q/qr))*180/np.pi),flow=[Q.real,Q.imag])
def increment(s,h,l,old,parents):
 prev,ph,pl=old;lam,w=rule(4);N=basis(lam);error=norm=0.
 pv=prev.v[parents];J=np.stack((pv[:,1]-pv[:,0],pv[:,2]-pv[:,0]),axis=-1);inv=np.linalg.inv(J)
 for bary,weight,shape in zip(lam,w,N):
  points=np.einsum('i,tij->tj',bary,s.v);rs=np.einsum('tij,tj->ti',inv,points-pv[:,0]);bl=np.column_stack((1-rs.sum(axis=1),rs));assert np.min(bl)>-1e-12;B=basis(bl)
  ov=np.sum((ph[prev.conn[parents]]+pl[prev.conn[parents]])*B,axis=1);v=h[s.conn]@shape+l[s.conn]@shape;error+=np.sum(weight*s.det*abs(v-ov)**2);norm+=np.sum(weight*s.det*abs(v)**2)
 return float(np.sqrt(error/norm))
try:
 tube.generate(out/'base',sectors=a.sectors,radial=4,axial=2,radius=1.,length=2.)
 nodes,_,faces=tube.read_mesh(out/'base/fluid.msh');tris=[tri for tag,tri in faces if tag==1];ids=sorted({i for t in tris for i in t});ix={i:j for j,i in enumerate(ids)};x=np.array([nodes[i][1:] for i in ids]);t=np.array([[ix[i] for i in tri] for tri in tris]);cross=np.linalg.det(np.stack((x[t[:,1]]-x[t[:,0]],x[t[:,2]]-x[t[:,0]]),axis=-1));t[cross<0]=t[cross<0][:,[0,2,1]]
 assert len(t)==7*a.sectors;old={};reports=[];parents=None;start=time.monotonic()
 for level in range(4):
  s=Space(x,t);expected=a.sectors*np.sin(2*np.pi/a.sectors)/2;assert abs(s.area-expected)<1e-12
  np.savez_compressed(out/f'mesh-level{level}.npz',vertices=x,triangles=t,nodes=s.nodes,connectivity=s.conn,boundary=s.boundary)
  for alpha in [1,2]:
   h,l,solve,(A,b)=s.solve(alpha,lambda p:.01,lambda p:np.zeros(len(p)));oracle=decimal_rows(A,b,h[s.free],l[s.free]);m6=metrics(s,h,l,alpha,6);m8=metrics(s,h,l,alpha,8)
   delta=max(abs(m6[k]-m8[k]) for k in ['velocity_relative_l2','flow_amplitude_relative','flow_phase_degrees']);assert delta<1e-9
   change=increment(s,h,l,old[alpha],parents) if level else None
   np.savez_compressed(out/f'alpha{alpha}-level{level}.npz',state_hi=h,state_lo=l)
   row=dict(sectors=a.sectors,alpha=alpha,level=level,nodes=len(s.nodes),triangles=len(t),area=s.area,metrics=m8,quadrature_change=delta,successive_field_change=change,solve=solve,decimal_csr_checks=oracle);reports.append(row);dump(out/'progress.json',reports);print(json.dumps(row),flush=True);old[alpha]=(s,h,l)
  if level<3:x,t,parents=refine(x,t)
 assert all(r['successive_field_change']<1e-4 for r in reports if r['level']==3)
 dump(out/'completion.json',dict(passed=True,seconds=time.monotonic()-start,reports=reports,sources={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['recompute-polygon-reference.py','polygon_reference_fem.py','polygon_reference_dd.py']},scope='Fresh independent P2 polygon geometry diagnostic. Successive increment is not a rigorous error bound; does not replace3D qualification.'))
except BaseException as e:dump(out/'failure.json',dict(error=repr(e)));raise
