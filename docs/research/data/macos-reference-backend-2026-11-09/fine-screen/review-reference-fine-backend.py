"""Independent raw reread with explicit tetrahedral mass and native payload checks."""
from pathlib import Path
import json,sys,hashlib,struct
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from audit_pressure_tube import Domain,svfsi_frame
from analyze_womersley import Mesh
b=ROOT/'build/recompute-20261109';w=b/'reference-fine-backend-screen'
r=json.loads((w/'report.json').read_text());assert r['passed'] and not r['adopted']
case=b/'elastic-s24-l1-n800';domains=[Domain(case/name) for name in ('fluid.msh','solid.msh')];meshes=[Mesh(d.path) for d in domains]
ds=.01*(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));scales=[dict(velocity=12*ds,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
volumes=[]
for m in meshes:
 p=m.xyz[m.cells];v=np.abs(np.linalg.det(p[:,1:]-p[:,:1]))/6;assert abs(v.sum()-m.volume)<1e-10;volumes.append(v)
def paths(label,prefix):
 result={}
 for p in (w/label/'results').glob(prefix+'_*'):
  token=p.stem.rsplit('_',1)[1]
  if not token.isdecimal():continue
  i=int(token);assert i not in result;result[i]=p
 return result
def payload(p):
 data=p.read_bytes();meta=struct.unpack_from('<8i',data);assert meta[:3]==(1,2,2) and meta[4:7]==(0,7,1)
 count=4+21*meta[3];assert len(data)==32+8*count
 a=np.frombuffer(data,dtype='<f8',offset=32);assert np.isfinite(a).all();return meta,a
out={}
for candidate,original,start in [('startup-fsils','startup-old',1),('startup-ilut','startup-old',1),('startup-replay','startup-ilut',91)]:
 snaps=[paths(x,'result') for x in (original,candidate)];native=[paths(x,'stFile') for x in (original,candidate)]
 assert set(snaps[1])==set(native[1])==set(range(start,101))
 node=mass=history=norm=0.;allbits=True
 for step in range(start,101):
  x,y=[svfsi_frame(s[step],domains) for s in snaps]
  for i,(m,vol) in enumerate(zip(meshes,volumes)):
   for field,scale in scales[i].items():
    delta=np.array([x[i][int(n)][field] for n in m.ids])-np.array([y[i][int(n)][field] for n in m.ids]);node=max(node,float(np.max(np.abs(delta),initial=0)))
    q=delta[m.cells];squared=np.sum(vol*(np.sum(q*q,axis=(1,2))+np.sum(q.sum(axis=1)**2,axis=1)))/20
    mass=max(mass,float(np.sqrt(squared/vol.sum())/scale))
  (ma,a),(mb,c)=[payload(s[step]) for s in native];assert ma==mb and a[0]==c[0]
  history=max(history,float(np.max(np.abs(a[4:]-c[4:]),initial=0)));norm=max(norm,float(np.max(np.abs(a[2:4]-c[2:4]))));allbits=allbits and np.array_equal(a[2:],c[2:])
 assert node<2e-9 and mass<1e-8 and history<2e-9 and norm<2e-9
 if candidate=='startup-replay':assert allbits and max(node,mass,history,norm)==0
 out[candidate]=dict(states=101-start,maximum_node=node,maximum_relative_mass=mass,maximum_native_history=history,maximum_saved_norm=norm,exact_time=True,bitwise_algorithm_except_elapsed=bool(allbits),passed=True)
result=dict(passed=True,pairs=out,report_sha256=hashlib.sha256((w/'report.json').read_bytes()).hexdigest(),reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Independent raw reread on actual fine startup; no long-run physical claim')
(w/'independent-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
