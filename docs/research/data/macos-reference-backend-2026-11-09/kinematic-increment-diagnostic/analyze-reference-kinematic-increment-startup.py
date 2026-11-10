from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from svfsi_restart_evidence import native_checkpoint
from audit_pressure_tube import Domain,svfsi_frame
base=ROOT/'build/recompute-20261109';w=base/'reference-kinematic-increment-startup'
assert (w/'diagnostic.json').exists(),'All diagnostic solves required'
assert not (w/'field-diagnostic.json').exists(),'Refuse overwrite'
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def actual(folder,kind,step):
 matches=[p for p in folder.glob(kind+'_*') if p.stem.rsplit('_',1)[1].isdecimal() and int(p.stem.rsplit('_',1)[1])==step]
 assert len(matches)==1;return matches[0]
definition=json.loads((w/'definition.json').read_text());results=json.loads((w/'diagnostic.json').read_text())['runs']
case=base/'elastic-s24-l1-n800';domains=[Domain(case/'fluid.msh'),Domain(case/'solid.msh')]
ds=.01*(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
comparisons={};consumed={}
def bind(p):
 consumed[str(p.relative_to(base))]=hashlib.sha256(p.read_bytes()).hexdigest();return p
for name in ['cg-fsils']:
 row=results[name];node=mass=history=norm_delta=0.;pairs=0;norms_exact=True
 assert row['start']==0 and row['stop']==600 and row['convergence_passed']
 for step in range(401,541):
  folders=[base/'reference-mesh-backend-diagnostic/cg-fsils/results',w/name/'results'];frames=[svfsi_frame(bind(actual(folder,'result',step)),domains) for folder in folders]
  for i,domain in enumerate(domains):
   for field,scale in scales[i].items():
    x,y=frames[0][i],frames[1][i];delta=max(abs(a-b) for n in x for a,b in zip(x[n][field],y[n][field]));node=max(node,delta);mass=max(mass,domain.rms_difference(x,y,field)/scale)
  records=[native_checkpoint(bind(actual(folder,'stFile',step))) for folder in folders]
  assert records[0]['stamp']==records[1]['stamp'] and records[0]['time']==records[1]['time']
  values=[np.frombuffer((actual(folder,'stFile',step)).read_bytes(),dtype='<f8',offset=32) for folder in folders]
  assert values[0].shape==values[1].shape
  norms_exact=norms_exact and np.array_equal(values[0][2:4],values[1][2:4]);norm_delta=max(norm_delta,float(np.max(np.abs(values[0][2:4]-values[1][2:4]))))
  history=max(history,float(np.max(np.abs(values[0][4:]-values[1][4:]),initial=0)));pairs+=1

 comparisons[name]=dict(first_step=401,last_step=540,pairs=pairs,maximum_node_delta=node,maximum_relative_mass=mass,maximum_native_history_delta=history,exact_native_time=True,exact_saved_equation_norms=bool(norms_exact),maximum_saved_norm_delta=norm_delta,field_and_history_tolerances_passed=node<2e-9 and mass<1e-8 and history<2e-9,saved_norm_bound_passed=norm_delta<definition['saved_norm_limit'])
dump(w/'field-diagnostic.json',dict(definition=definition,runs=results,comparisons=comparisons,consumed_sha256=consumed,analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),production_adopted=False,scope='Fresh kinematic derivative401..540 vs failed original CG replay from original step400; full zero-state1..600 convergence is a separate gate. All compared raw states bound; no full production qualification'))
print((w/'field-diagnostic.json').read_text())
