"""Matched EON geometry/length response sensitivity; no invented acceptance gate."""
from pathlib import Path
import argparse,json,math,hashlib,sys,importlib.util
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube
spec=importlib.util.spec_from_file_location('observables',Path(__file__).with_name('compare-pressure-audits.py'));audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def response(left,right):
 scale=max(abs(left['mean']),left['amplitude'],1e-30);floor=1e-12*scale
 return dict(baseline=left,control=right,mean_difference=right['mean']-left['mean'],mean_relative_to_baseline=(right['mean']-left['mean'])/abs(left['mean']) if abs(left['mean'])>floor else None,amplitude_difference=right['amplitude']-left['amplitude'],amplitude_relative_to_baseline=(right['amplitude']-left['amplitude'])/left['amplitude'] if left['amplitude']>floor else None,phase_difference_degrees=(right['phase_degrees']-left['phase_degrees']+180)%360-180 if min(left['amplitude'],right['amplitude'])>floor else None)
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['geometry','length'],required=True)
 for k in ['baseline-work','control-work','baseline-audit','control-audit','output']:p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();works=[a.baseline_work.resolve(),a.control_work.resolve()];paths=[a.baseline_audit.resolve(),a.control_audit.resolve()]
 if a.output.exists():raise ValueError('Refuse overwrite')
 reports=[json.loads(p.read_text()) for p in paths];prerequisites=[audit.validate(r,'EONSim') for r in reports]
 if not all(all(v.values()) for v in prerequisites):raise ValueError('Both actual complete audits must pass periodicity, geometry and quality prerequisites')
 if any(r.get('synthetic_fixture_not_a_solver_result') for r in reports):raise ValueError('Synthetic reports are not study evidence')
 for r in reports:
  if r['steps']!=25600 or r['samples_per_cycle']!=800 or r['first_step']!=23201:raise ValueError('Need matched final3cycles of full32cycleN800 studies')
 cfg=[json.loads((w/'case.json').read_text()) for w in works];geo=[json.loads((w/'geometry.json').read_text()) for w in works]
 if cfg[0]!=cfg[1]:raise ValueError('Physical/time cases differ')
 definitions=[json.loads((w/'definition.json').read_text()) for w in works]
 if any(definitions[0][k]!=definitions[1][k] for k in ['binary_sha256','solver_options','ranks','threads']):raise ValueError('Solver execution differs')
 consumed={str(p):sha(p) for p in paths}
 for w,r in zip(works,reports):
  if r['case_sha256']!=sha(w/'case.json'):raise ValueError('Audit case binding changed')
  for name in ['fluid.msh','solid.msh']:
   if r['reference_meshes'][name]!=sha(w/name):raise ValueError('Audit mesh binding changed')
  for name in ['case.json','geometry.json','definition.json','fluid.msh','solid.msh']:consumed[str(w/name)]=sha(w/name)
 fixed=dict(reports[0]['physical_definition']);other=dict(reports[1]['physical_definition'])
 if a.mode=='geometry':
  if fixed!=other or geo[0]['sectors']!=24 or geo[1]['sectors']!=48:raise ValueError('Wrong fixed-physics polygon intervention')
  for name in ['fluid.msh','solid.msh']:
   x,c,f=tube.read_mesh(works[0]/name);y,d,g=tube.read_mesh(works[1]/name)
   if c!=d or f!=g or x.keys()!=y.keys() or any(x[k][0]!=y[k][0] for k in x):raise ValueError('Geometry control changed topology or axial coordinates')
   width=2*math.pi/24
   for k,(ax,yy,zz) in x.items():
    angle=math.atan2(zz,yy);factor=math.cos(angle-(math.floor(angle/width)+.5)*width)/math.cos(math.pi/24)
    if max(abs(y[k][1]-yy*factor),abs(y[k][2]-zz*factor))>1e-13:raise ValueError('Wrong radial geometry map')
  scope='Fixed topology24-to48-sided polygon response sensitivity; includes geometry/basis interaction, not exact continuum geometry error.'
 else:
  if fixed.pop('length')!=12 or other.pop('length')!=24 or fixed!=other:raise ValueError('Wrong length-only physical intervention')
  if geo[0]['sectors']!=geo[1]['sectors'] or geo[0]['red_refinements']!=geo[1]['red_refinements']:raise ValueError('Cross-section/refinement differs')
  for name in ['fluid.msh','solid.msh']:
   data=[tube.read_mesh(w/name) for w in works];axes=[sorted({v[0] for v in row[0].values()}) for row in data]
   increments=[[y-x for x,y in zip(ax,ax[1:])] for ax in axes]
   if any(abs(v-.5)>1e-12 for dx in increments for v in dx):raise ValueError('Axial spacing is not matched at0.5')
   sections=[{(v[1],v[2]) for v in row[0].values()} for row in data]
   if sections[0]!=sections[1]:raise ValueError('Cross-section nodes differ')
  scope='L12-toL24 response sensitivity at matched axial spacing; raw end-flow differences also reflect doubled compliant length. Not an exact infinite-length error estimate.'
 result=dict(mode=a.mode,prerequisites=prerequisites,observables={k:response(reports[0]['harmonics'][k],reports[1]['harmonics'][k]) for k in audit.FIELDS},input_sha256=consumed,source_sha256={str(p):sha(p) for p in [Path(__file__),Path(audit.__file__),ROOT/'scripts/audit_pressure_tube.py']},scope=scope,qualification='Response diagnostic only; full independent budgets and original Lamé/cross-solver gates remain required.')
 a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result['observables'],indent=2))
if __name__=='__main__':main()
