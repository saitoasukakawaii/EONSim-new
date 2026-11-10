from pathlib import Path
import json,sys,hashlib
import numpy as np,h5py
sys.path.insert(0,'scripts')
from analyze_womersley import Mesh
w=Path('build/recompute-20261109/alpha1-s96-l1-screen')
r=json.loads((w/'report.json').read_text());assert r['eligible']
m=Mesh(w/'fluid.msh');assert hashlib.sha256((w/'eonsim').read_bytes()).hexdigest()==r['definition']['binary_sha256']
# Reconstruct element volumes and exact linear tetrahedral mass independently.
p=m.xyz[m.cells];vol=np.abs(np.linalg.det(p[:,1:]-p[:,:1]))/6
assert abs(vol.sum()-m.volume)<1e-12
maps={}
for name in r['runs']:
 d={}
 for manifest in (w/name/'checkpoint').glob('generation_*/manifest'):
  parts=manifest.read_text().split();d[int(parts[2])]=manifest.parent/'state_rank0.h5'
 expected=set(range(17 if name=='replay16' else 1,33));assert set(d)==expected
 maps[name]=d
pairs=0;datasets=0;maxnode=0.;maxmass=0.
for name in ('window8','window32','direct-last','replay16'):
 for step,file in maps[name].items():
  with h5py.File(maps['direct-first'][step]) as a,h5py.File(file) as b:
   assert set(a)==set(b)
   for key in a:
    x=a[key][()];y=b[key][()];assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
    if key in ('clock','metadata','time_metadata'):assert np.array_equal(x,y)
    else:
     delta=x-y;v=float(np.max(np.abs(delta),initial=0));maxnode=max(maxnode,v);assert v<2e-9
     if key in ('fluid','time_previous') and x.size:
      z=delta.reshape(-1,4)[m.cells]
      for sl,scale in ((slice(0,3),.0025),(slice(3,4),.02)):
       q=z[:,:,sl];squared=np.sum(vol*(np.sum(q*q,axis=(1,2))+np.sum(np.sum(q,axis=1)**2,axis=1)))/20
       value=float(np.sqrt(squared/vol.sum())/scale);maxmass=max(maxmass,value);assert value<1e-8
    datasets+=1
  pairs+=1
assert pairs==112 and datasets==560
out=dict(pairs=pairs,datasets=datasets,maximum_node_delta=maxnode,maximum_relative_mass=maxmass,clock_and_metadata_exact=True,independent_tetrahedral_mass=True,passed=True)
(w/'raw-review.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
