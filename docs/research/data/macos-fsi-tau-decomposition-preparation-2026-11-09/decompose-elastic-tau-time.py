"""Actual endpoint fields on cycle32; path decomposition with exact P1 cross terms."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('elastic_fields',Path(__file__).with_name('compare-pressure-fields.py'));fields=importlib.util.module_from_spec(spec);spec.loader.exec_module(fields)
sha=fields.sha

def configuration(configs):
 a,b,c=configs
 if any(x['time']!=dict(scheme='generalized_alpha',rho_infinity=.5) for x in configs):raise ValueError('Need validated generalized-alpha family')
 dt=a['fsi']['dt'];period=a['fsi']['pressure_time']['period'];n=round(period/dt)
 if n!=400 or any(not math.isclose(x['fsi']['dt'],dt/factor,rel_tol=1e-14) or x['fsi']['steps']!=32*n*factor for x,factor in zip(configs,[1,2,2])):raise ValueError('Need complete N400/N800/N800 clocks')
 expected=(8/15)*dt
 if a['fsi'].get('stabilization_time_scale') is not None or c['fsi'].get('stabilization_time_scale') is not None or not math.isclose(b['fsi'].get('stabilization_time_scale',0),expected,rel_tol=1e-14):raise ValueError('Wrong tau-time intervention')
 normalized=[]
 for x in configs:
  v=fields.physical_config(x);v['fsi'].pop('stabilization_time_scale',None)
  if v['fsi'].get('stabilization_tau') is not None:raise ValueError('Fixed whole tau is not this experiment')
  normalized.append(v)
 if normalized[0]!=normalized[1] or normalized[0]!=normalized[2]:raise ValueError('Physics or solver changed beyond intervention')
 return n

def inner(mesh,x,y):
 x=x[mesh.cells];y=y[mesh.cells]
 return float(np.sum(mesh.volumes*(np.sum(x.sum(axis=1)*y.sum(axis=1),axis=1)+np.sum(x*y,axis=(1,2)))/20))

def contributions(mesh,x,y,z):
 t=y-x;q=z-y;d=z-x
 result={k:inner(mesh,v,v) for k,v in [('timestep_path',t),('tau_time_path',q),('total',d)]}
 result['cross_inner']=inner(mesh,t,q)
 residual=result['total']-result['timestep_path']-result['tau_time_path']-2*result['cross_inner']
 if abs(residual)>1e-11*max(result['total'],result['timestep_path'],result['tau_time_path'],1e-30):raise ValueError('P1 energy identity failed')
 return result,float(np.max(abs(d-t-q)))

def main():
 p=argparse.ArgumentParser()
 for k in ['target','control','fine','target-audit','control-audit','fine-audit','default-budget-time','output']:p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();works=[a.target,a.control,a.fine];audits=[a.target_audit,a.control_audit,a.fine_audit]
 if a.output.exists():raise ValueError('Refuse overwrite')
 configs=[json.loads((w/'case.json').read_text()) for w in works];n=configuration(configs);receipts={}
 for w in works:
  path=w/('completion.json' if (w/'completion.json').exists() else 'completion-postflight.json')
  if not path.exists():raise ValueError('Incomplete numerical study')
  r=json.loads(path.read_text());assert r['accepted_steps']==json.loads((w/'case.json').read_text())['fsi']['steps'] and all(v['exit_code']==0 for v in r['receipts']);receipts[str(path)]=sha(path)
 studies=[fields.Study(w/'case.json',w,p) for w,p in zip(works,audits)]
 for s in studies:
  if s.reference or not all(s.valid.values()) or not s.periodic_at(32) or s.audit.get('synthetic_fixture_not_a_solver_result'):raise ValueError('Need physical audited EONSim periodic fields')
  if s.audit['analysis_script_sha256']!=sha(ROOT/'scripts/audit_pressure_tube.py'):raise ValueError('Audit source changed')
 if [s.n for s in studies]!=[400,800,800] or any(s.steps!=32*s.n for s in studies):raise ValueError('Audit clocks differ')
 if any(s.audit['scales']!=studies[0].audit['scales'] or s.geometry!=studies[0].geometry for s in studies):raise ValueError('Geometry or physical scales differ')
 for domain in range(2):
  if len({sha(s.domains[domain].path) for s in studies})!=1:raise ValueError('Meshes differ')
 # Bind the diagnostic producer to its verified adoption, and default producers to original binary.
 adoption=ROOT/'docs/research/data/macos-fsi-tau-option-2026-11-09/old-checkpoint-summary.json';binaries=json.loads(adoption.read_text())['binary_sha256']
 expected=[binaries['build/macos-release/eonsim'],binaries['build/macos-fsi-tau-diagnostic/eonsim'],binaries['build/macos-release/eonsim']]
 for w,digest in zip(works,expected):
  if json.loads((w/'definition.json').read_text())['binary_sha256']!=digest or sha(w/'eonsim')!=digest:raise ValueError('Unvalidated producer binary')
 sums={};closure=0.
 for phase in range(1,n+1):
  frames=[s.frame(31*s.n+phase*s.n//n) for s in studies]
  for domain,mesh in enumerate(studies[0].meshes):
   for name,scale in studies[0].audit['scales'][domain].items():
    xyz=[np.array([f[domain][int(node)][name] for node in mesh.ids]) for f in frames]
    row,error=contributions(mesh,*xyz);closure=max(closure,error);key=('solid_' if domain else 'fluid_')+name
    total=sums.setdefault(key,{k:0. for k in row})
    for k,v in row.items():total[k]+=v/(n*mesh.volume*scale**2)
 default=json.loads(a.default_budget_time.read_text());result={}
 for key,row in sums.items():
  norm=math.sqrt(max(0,row['total']));old=default['relative_rms'][key]
  if not math.isclose(norm,old,rel_tol=1e-10,abs_tol=1e-14):raise ValueError('Default total differs from original budget')
  result[key]=dict(relative_rms={k:math.sqrt(max(0,v)) for k,v in row.items() if k!='cross_inner'},cross_inner=row['cross_inner'],energy_identity_error=row['total']-row['timestep_path']-row['tau_time_path']-2*row['cross_inner'])
 report=dict(fields=result,cycle=32,common_phases=n,maximum_node_closure=closure,input_files_sha256={str(s.work):s.files for s in studies},producer_receipts=receipts,default_budget_time_sha256=sha(a.default_budget_time),adoption_sha256=sha(adoption),sources_sha256={str(p):sha(p) for p in [Path(__file__),Path(fields.__file__),ROOT/'scripts/audit_pressure_tube.py']},scope='Path-dependent endpoint field decomposition on reference meshes. Only explicit tau time factor fixed; initial BE also overridden. Not pure temporal truncation error or a replacement for the original10% default budget.')
 with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
