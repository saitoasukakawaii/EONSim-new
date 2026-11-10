"""Analysis-only recovery of completed loaded runs; no solver invocation."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,h5py
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from audit_pressure_tube import Domain,eonsim_frame
from fsi_field_cycles import series
w=ROOT/'build/recompute-20261109/elastic-loaded-screen'
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def maps(folder):
 out={}
 for p in folder.glob('generation_*/manifest'):
  step=int(p.read_text().split()[2]);assert step not in out;out[step]=p.parent
 return out
definition=json.loads((w/'definition.json').read_text());start=definition['start_step']
results=json.loads((w/'failure.json').read_text())['completed']
assert set(results)=={'direct-first','window8','window32','direct-last','replay16'}
assert all(r['exit_code']==0 for r in results.values())
assert not (w/'report.json').exists()
domains=[Domain(w/'fluid.msh'),Domain(w/'solid.msh')]
compliance=(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));ds=.01*compliance
scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
baseline=maps(w/'direct-first/checkpoint');maximum=0.;massmax=0.;pairs=0;datasets=0;fieldpairs=0
for name in ('window8','window32','direct-last','replay16'):
 for step,path in maps(w/name/'checkpoint').items():
  with h5py.File(baseline[step]/'state_rank0.h5') as a,h5py.File(path/'state_rank0.h5') as b:
   assert set(a)==set(b)
   for key in a:
    x,y=a[key][()],b[key][()];assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
    if key in ('metadata','clock','time_metadata'):assert np.array_equal(x,y),(name,step,key)
    else:
     delta=float(np.max(np.abs(x-y),initial=0));maximum=max(maximum,delta);assert delta<2e-9,(name,step,key,delta)
    datasets+=1
  pairs+=1
 for i,suffix in enumerate(('', '_solid')):
  left=dict(series(w/'direct-first'/(f'solution_restart{start}'+suffix+'.pvd')))
  for timevalue,path in series(w/name/(f'solution_restart{start+(16 if name=="replay16" else 0)}'+suffix+'.pvd')):
   assert timevalue in left
   a=eonsim_frame(left[timevalue],domains[i],bool(i));b=eonsim_frame(path,domains[i],bool(i))
   for field,scale in scales[i].items():
    delta=domains[i].rms_difference(a,b,field)/scale;massmax=max(massmax,delta);assert delta<1e-8,(name,timevalue,field,delta)
   fieldpairs+=1
assert pairs==112 and fieldpairs==224
assert definition['source_sha256']=={p.name:sha(p) for p in (w/'source').iterdir()}
ratios={name:results['window32']['seconds']/results[name]['seconds'] for name in ('direct-first','direct-last','window8')}
dump(w/'report.json',dict(definition=definition,runs=results,checkpoint_pairs=pairs,hdf_datasets=datasets,domain_frame_pairs=fieldpairs,maximum_history_node_delta=maximum,maximum_field_relative_mass=massmax,clock_metadata_exact=True,cost_ratios=ratios,correctness_passed=True,local_cost_reduction_passed=all(v<.9 for v in ratios.values()),scope=definition['scope']))
print((w/'report.json').read_text(),flush=True)
