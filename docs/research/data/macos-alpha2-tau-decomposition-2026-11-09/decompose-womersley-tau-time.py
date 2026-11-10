"""Three actual cycle-six fields: timestep path plus tau-time path, no norm subtraction."""
from pathlib import Path
import argparse,importlib.util,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('budget',Path(__file__).with_name('audit-womersley-budget.py'));budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)

def validate(definitions,receipts):
 a,b,c=definitions;n=a['steps_per_cycle']
 if n<8 or n%2 or [d['steps_per_cycle'] for d in definitions]!=[n,2*n,2*n]:raise ValueError('Need N default,2N fixed-tau-time,2N default')
 ignored={'steps_per_cycle','phases','tau_time_scale'}
 if any({k:v for k,v in d.items() if k not in ignored}!={k:v for k,v in a.items() if k not in ignored} for d in definitions):raise ValueError('Unmatched physics, mesh level or solver')
 if any(d['tau'] is not None or d['phases']!=d['steps_per_cycle'] or d['warmup']!=2 or r['step']!=6*d['steps_per_cycle'] for d,r in zip(definitions,receipts)):raise ValueError('Need default full tau and complete six-cycle dense studies')
 expected=(2/3)*a['period']/n
 if a.get('tau_time_scale') is not None or c.get('tau_time_scale') is not None or not math.isclose(b.get('tau_time_scale',0),expected,rel_tol=1e-14,abs_tol=0):raise ValueError('Wrong tau-time intervention')
 return n

def inner(mesh,x,y):
 x=x[mesh.cells];y=y[mesh.cells]
 return float(np.sum(mesh.volumes*(np.sum(x.sum(axis=1)*y.sum(axis=1),axis=1)+np.sum(x*y,axis=(1,2)))/20))

def main():
 p=argparse.ArgumentParser()
 for k in ['target','control','fine','target-analysis','control-analysis','fine-analysis','output']:p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();works=[a.target,a.control,a.fine]
 definitions=[json.loads((w/'definition.json').read_text()) for w in works];receipts=[json.loads((w/'receipt.json').read_text()) for w in works]
 n=validate(definitions,receipts)
 if a.output.exists():raise ValueError('Refuse overwrite')
 studies=[budget.TrackedStudy(w.resolve()) for w in works]
 if len({budget.sha(s.work/'fluid.msh') for s in studies})!=1:raise ValueError('Meshes differ')
 paths=[a.target_analysis,a.control_analysis,a.fine_analysis];gates=[budget.checked_analysis(p,s) for p,s in zip(paths,studies)]
 if not all(g['periodic'] and g['global_mass'] for g in gates):raise ValueError('Control needs demonstrated periodicity and mass conservation')
 mesh=studies[0].mesh;_,ref=mesh.reference(definitions[0],4);scales={'velocity':math.sqrt(ref/(2*mesh.volume)),'pressure':definitions[0]['pressure_amplitude']/math.sqrt(6)}
 sums={f:dict(timestep_path=0.,tau_time_path=0.,total=0.,cross_inner=0.) for f in scales};closure=0.
 for phase in range(1,n+1):
  x,y,z=[s.state(5*d['steps_per_cycle']+phase*d['steps_per_cycle']//n) for s,d in zip(studies,definitions)]
  t=y-x;q=z-y;total=z-x;closure=max(closure,float(np.max(abs(total-t-q))))
  for field,sl in [('velocity',slice(0,3)),('pressure',slice(3,4))]:
   weight=1/(n*mesh.volume*scales[field]**2)
   for name,delta in [('timestep_path',t),('tau_time_path',q),('total',total)]:sums[field][name]+=inner(mesh,delta[:,sl],delta[:,sl])*weight
   sums[field]['cross_inner']+=inner(mesh,t[:,sl],q[:,sl])*weight
 fields={}
 for field,row in sums.items():
  closure_squared=row['total']-row['timestep_path']-row['tau_time_path']-2*row['cross_inner']
  scale=max(row['total'],row['timestep_path'],row['tau_time_path'],1e-30)
  if abs(closure_squared)>1e-11*scale:raise ValueError('P1 energy identity failed')
  fields[field]=dict(relative_rms={k:math.sqrt(max(0,v)) for k,v in row.items() if k!='cross_inner'},cross_inner=row['cross_inner'],energy_identity_error=closure_squared)
 result=dict(fields=fields,common_phases=n,cycle=6,maximum_node_closure=closure,eligibility=dict(zip(['target','control','fine'],gates)),input_sha256={str(s.work):s.evidence() for s in studies},analysis_sha256={str(p):budget.sha(p) for p in paths},source_sha256={str(p):budget.sha(p) for p in [Path(__file__),Path(budget.__file__),ROOT/'scripts/analyze_womersley.py']},scope='Path-dependent vector-field decomposition. Timestep path holds only the explicit tau time scale fixed; velocity-dependent tau terms still evolve. Tau-time path is at fixed2N timestep. Cross term measures cancellation/reinforcement. Not a pure continuum temporal-error estimate or replacement qualification gate.')
 a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(fields,indent=2))
if __name__=='__main__':main()
