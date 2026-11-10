"""Analysis-only: resolve pinned filenames by numerical step, including padding."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from svfsi_restart_evidence import native_checkpoint
from audit_pressure_tube import Domain,svfsi_frame
base=ROOT/'build/recompute-20261109';w=base/'reference-backend-screen'
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def actual(folder,kind,step):
 matches=[p for p in folder.glob(kind+'_*') if p.stem.rsplit('_',1)[1].isdecimal() and int(p.stem.rsplit('_',1)[1])==step]
 assert len(matches)==1,(folder,kind,step);return matches[0]
definition=json.loads((w/'definition.json').read_text());results=json.loads((w/'failure.json').read_text())['completed']
assert len(results)==7 and all(r['exit_code']==0 for r in results.values())
assert not (w/'report.json').exists()
case=base/'reference-elastic-s24-l0-n400-nu0-case';domains=[Domain(case/'fluid.msh'),Domain(case/'solid.msh')]
ds=.01*(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
comparisons={}
for name,baseline in [('startup-fsils','startup-old'),('startup-ilut','startup-old'),('loaded-fsils','loaded-old'),('loaded-ilut','loaded-old'),('loaded-replay','loaded-ilut')]:
 row=results[name];node=mass=history=norm_delta=0.;pairs=0;norms_exact=True
 for step in range(row['start']+1,row['stop']+1):
  folders=[w/baseline/'results',w/name/'results'];frames=[svfsi_frame(actual(folder,'result',step),domains) for folder in folders]
  for i,domain in enumerate(domains):
   for field,scale in scales[i].items():
    x,y=frames[0][i],frames[1][i];delta=max(abs(a-b) for n in x for a,b in zip(x[n][field],y[n][field]));node=max(node,delta);mass=max(mass,domain.rms_difference(x,y,field)/scale)
  records=[native_checkpoint(actual(folder,'stFile',step)) for folder in folders]
  assert records[0]['stamp']==records[1]['stamp'] and records[0]['time']==records[1]['time']
  values=[np.frombuffer((actual(folder,'stFile',step)).read_bytes(),dtype='<f8',offset=32) for folder in folders]
  assert values[0].shape==values[1].shape
  norms_exact=norms_exact and np.array_equal(values[0][2:4],values[1][2:4]);norm_delta=max(norm_delta,float(np.max(np.abs(values[0][2:4]-values[1][2:4]))))
  history=max(history,float(np.max(np.abs(values[0][4:]-values[1][4:]),initial=0)));pairs+=1
 assert node<2e-9 and mass<1e-8 and history<2e-9,(name,node,mass,history)
 comparisons[name]=dict(pairs=pairs,maximum_node_delta=node,maximum_relative_mass=mass,maximum_native_history_delta=history,exact_native_time=True,exact_saved_equation_norms=bool(norms_exact),maximum_saved_norm_delta=norm_delta,field_and_history_tolerances_passed=True,passed=bool(norms_exact))
dump(w/'report.json',dict(definition=definition,runs=results,comparisons=comparisons,passed=all(v['passed'] for v in comparisons.values()),adopted=False,scope=definition['scope']))
print((w/'report.json').read_text(),flush=True)
