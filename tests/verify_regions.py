"""Piecewise exact two-material bar and mixed-component incompressible flow, 1/2 rank."""
import argparse,copy,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fluid'))
from generate_layered_channel import layered_mesh
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
mesh=a.work/'regions.msh';write_mesh(mesh,4)
lines=mesh.read_text().splitlines();positions={}
for line in lines[lines.index('$Nodes')+2:lines.index('$EndNodes')]:
 r=line.split();positions[int(r[0])]=list(map(float,r[1:]))
for i in range(lines.index('$Elements')+2,lines.index('$EndElements')):
 r=lines[i].split()
 if r[1]=='4' and sum(positions[int(n)][0] for n in r[-4:])/4>.5:r[3]='20';lines[i]=' '.join(r)
mesh.write_text('\n'.join(lines)+'\n')
def run(args,error=None):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
 if (r.returncode==0)!=(error is None) or (error and error not in r.stdout):raise RuntimeError(r.stdout)
 return r.stdout
def fields(path,ranks):
 result={}
 for rank in range(ranks):
  root=ET.parse(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
  data={x.attrib['Name']:x.text.split() for x in root.findall('.//PointData/DataArray')}
  for i,n in enumerate(data['mesh_node_id']):
   if int(data['owner'][i])==rank:result[int(n)]={key:list(map(float,v[3*i:3*i+3])) if key!='pressure' else [float(v[i])] for key,v in data.items() if key in ('displacement','velocity','pressure','momentum_residual')}
 return result
solid=dict(mode='static',boundaries=[dict(tag=1,type='displacement',components=[0],value=[0,0,0]),dict(tag=2,type='traction',value=[1,0,0]),dict(tag=3,type='displacement',components=[1],value=[0,0,0]),dict(tag=4,type='traction',value=[0,0,0]),dict(tag=5,type='displacement',components=[2],value=[0,0,0]),dict(tag=6,type='traction',value=[0,0,0])],regions=[dict(tag=tag,young=E,poisson=0,density=1) for tag,E in ((10,100),(20,200))])
fluid=dict(mode='stokes',pressure_normalization='mean',boundaries=[dict(tag=t,type='velocity',components=[(t-1)//2],value=[.2,0,0]) for t in range(1,7)],regions=[dict(tag=t,density=1,viscosity=mu) for t,mu in ((10,1),(20,2))])
for physics,cfg in (('solid',solid),('fluid',fluid)):
 case=a.work/f'{physics}.yaml';base=dict(mesh=str(mesh.resolve()),output=str((a.work/'out.vtu').resolve()));base[physics]=cfg;case.write_text(json.dumps(base))
 part=a.work/'parts';run([a.executable,'-case',case,'-prepare',part,'-parts',2]);solutions=[]
 for ranks in (1,2):
  out=a.work/f'{physics}{ranks}.vtu';cmd=([a.mpiexec,'-n',2] if ranks==2 else [])+[a.executable,'-case',case,'-output',out]
  if ranks==2:cmd+=['-partition',part]
  run(cmd);values=fields(out,ranks);solutions.append(values);error=0
  for node,fs in values.items():
   x=positions[node][0]
   exact=[min(x,.5)/100+max(x-.5,0)/200,0,0] if physics=='solid' else [.2,0,0]
   error=max(error,max(abs(u-v) for u,v in zip(fs['displacement' if physics=='solid' else 'velocity'],exact)))
   if physics=='fluid':error=max(error,abs(fs['pressure'][0]))
  assert error<2e-10,error
  print(physics,ranks,'error',error)
 for n in solutions[0]:
  for field in solutions[0][n]:assert max(abs(x-y) for x,y in zip(solutions[0][n][field],solutions[1][n][field]))<2e-10
 base[physics]=dict(cfg,regions=cfg['regions'][:-1]);case.write_text(json.dumps(base));run([a.executable,'-case',case],'Missing material for region')

# Tagged observations must follow the physical tags after translation/rotation.
# The two-material side mean is 0.004375; its nodal arithmetic mean is 0.00425.
# The rotated case also shares an axial displacement constraint across two tags:
# per-tag reactions overlap, but the total support force must count each DoF once.
for rotated in (False,True):
 name='rotated_support' if rotated else 'translated_bar'
 transformed=lines.copy();cfg=copy.deepcopy(solid)
 for i in range(lines.index('$Nodes')+2,lines.index('$EndNodes')):
  node=int(lines[i].split()[0]);x,y,z=positions[node]
  xyz=[2+2*y,3+x,-1-.5*z] if rotated else [x+2,y,z]
  transformed[i]=f'{node} '+ ' '.join(map(str,xyz))
 if rotated:
  for b in cfg['boundaries']:
   b['components']=[1-c if c<2 else c for c in b.get('components',[0,1,2])]
   x,y,z=b['value'];b['value']=[y,x,-z]
  cfg['regions'][1]['young']=100
  cfg['boundaries'][2].update(components=[0,1],origin=[2,3,-1],gradient=[[0,0,0],[0,.01,0],[0,0,0]])
 moved_mesh=a.work/f'{name}.msh';moved_mesh.write_text('\n'.join(transformed)+'\n')
 case=a.work/f'{name}.yaml';part=a.work/f'{name}_parts'
 case.write_text(json.dumps(dict(mesh=str(moved_mesh.resolve()),output=str((a.work/f'{name}.vtu').resolve()),solid=cfg)))
 run([a.executable,'-case',case,'-prepare',part,'-parts',2]);observations=[]
 axis='y' if rotated else 'x';component=1 if rotated else 0
 for ranks in (1,2):
  out=a.work/f'{name}{ranks}.vtu'
  cmd=([a.mpiexec,'-n',2] if ranks==2 else [])+[a.executable,'-case',case,'-output',out]
  if ranks==2:cmd+=['-partition',part]
  log=run(cmd);values=fields(out,ranks)
  assert 'tip_displacement=' not in log,log
  boundaries={};support={}
  for line in log.splitlines():
   if line.startswith('solid_boundary_tag='):
    data={k:float(v) for k,v in (item.split('=') for item in line.split())}
    boundaries[int(data.pop('solid_boundary_tag'))]=data
   elif line.startswith('support_reaction_'):
    support={k:float(v) for k,v in (item.split('=') for item in line.split())}
  assert set(boundaries)==set(range(1,7)) and len(support)==3,log
  for node,fs in values.items():
   x=positions[node][0];exact=[0.,0.,0.]
   exact[component]=.01*x if rotated else min(x,.5)/100+max(x-.5,0)/200
   assert max(abs(u-v) for u,v in zip(fs['displacement'],exact))<2e-10
  for tag,b in boundaries.items():
   area=([1,1,.5,.5,2,2][tag-1] if rotated else 1)
   mean=0 if tag==1 else ((.01 if rotated else .0075) if tag==2 else (.005 if rotated else .004375))
   assert abs(b['reference_area']-area)<2e-12,(name,tag,b)
   for c in 'xyz':
    assert abs(b[f'mean_displacement_{c}']-(mean if c==axis else 0))<2e-10,(name,tag,b)
    assert abs(b[f'mean_velocity_{c}'])<2e-10
   bc=cfg['boundaries'][tag-1]
   expected={f'reaction_{"xyz"[c]}' for c in bc['components']} if bc['type']=='displacement' else set()
   assert {k for k in b if k.startswith('reaction_')}==expected,(tag,b)
  assert abs(boundaries[1][f'reaction_{axis}']+1)<2e-10,log
  for c in 'xyz':assert abs(support[f'support_reaction_{c}']-(-1 if c==axis else 0))<2e-10,log
  if rotated:
   assert abs(sum(b.get('reaction_y',0) for b in boundaries.values())-support['support_reaction_y'])>1e-3,log
  observations.append((boundaries,support))
  print(name,ranks,'tip',boundaries[2][f'mean_displacement_{axis}'],'support',support[f'support_reaction_{axis}'])
 for tag in observations[0][0]:
  for key,value in observations[0][0][tag].items():assert abs(value-observations[1][0][tag][key])<2e-10
 for key,value in observations[0][1].items():assert abs(value-observations[1][1][key])<2e-10

# Pressure normalization must shift constrained reactions as well as the pressure field.
# Extensional inflow has a nonconstant pressure; choosing its normalized nodal pressure
# as a point gauge must reproduce every field, including wall reactions.
cfg=dict(mode='steady',pressure_normalization='mean',boundaries=[dict(tag=t,type='velocity',value=[0,0,0],gradient=[[.2,0,0],[0,-.2,0],[0,0,0]]) for t in range(1,7)])
base=dict(mesh=str(mesh.resolve()),output=str((a.work/'normalization.vtu').resolve()),fluid=cfg)
case=a.work/'normalization.yaml';part=a.work/'normalization_parts'
case.write_text(json.dumps(base));run([a.executable,'-case',case,'-prepare',part,'-parts',2])
for ranks in (1,2):
 prefix=([a.mpiexec,'-n',2] if ranks==2 else [])+[a.executable,'-case',case]
 if ranks==2:prefix+=['-partition',part]
 cfg.pop('pressure_gauge',None);cfg['pressure_normalization']='mean';case.write_text(json.dumps(base))
 out=a.work/f'mean{ranks}.vtu';run(prefix+['-output',out]);mean=fields(out,ranks)
 pressure=mean[min(mean)]['pressure'][0];assert abs(pressure)>1e-4
 cfg.pop('pressure_normalization');cfg['pressure_gauge']=dict(node=min(mean),value=pressure);case.write_text(json.dumps(base))
 out=a.work/f'gauge{ranks}.vtu';run(prefix+['-output',out]);gauge=fields(out,ranks)
 assert max(abs(x-y) for n in mean for key in mean[n] for x,y in zip(mean[n][key],gauge[n][key]))<2e-9
# Nonzero piecewise shear exercises viscosity jumps and interface traction transfer.
# Only the top/bottom velocity is prescribed; open x faces carry the exact traction.
layer_mesh=a.work/'layered.msh';layered_mesh(layer_mesh)
layer_lines=layer_mesh.read_text().splitlines()
layer_points={int(r[0]):list(map(float,r[1:])) for r in
 (line.split() for line in layer_lines[layer_lines.index('$Nodes')+2:layer_lines.index('$EndNodes')])}
layer_part=a.work/'layer_parts'
for lower,upper,flow in ((1.,4.,.65),(4.,1.,.35)):
 tau=1/(.5/lower+.5/upper)
 cfg=dict(mode='stokes',regions=[dict(tag=t,density=1,viscosity=mu) for t,mu in ((10,lower),(20,upper))],
  boundaries=[dict(tag=1,type='traction',value=[2,-tau,0]),dict(tag=2,type='traction',value=[-2,tau,0]),
   dict(tag=3,type='velocity',value=[0,0,0]),dict(tag=4,type='velocity',value=[1,0,0]),
   dict(tag=5,type='velocity',components=[2],value=[0,0,0]),dict(tag=6,type='velocity',components=[2],value=[0,0,0])])
 case=a.work/f'layer_{int(lower)}.yaml'
 case.write_text(json.dumps(dict(mesh=str(layer_mesh.resolve()),output=str((a.work/'layered.vtu').resolve()),fluid=cfg,
  solver=dict(relative_tolerance=1e-10,absolute_tolerance=1e-12,maximum_iterations=30))))
 if lower==1:run([a.executable,'-case',case,'-prepare',layer_part,'-parts',2])
 solutions=[]
 for ranks in (1,2):
  out=a.work/f'layer_{int(lower)}_{ranks}.vtu'
  cmd=([a.mpiexec,'-n',2] if ranks==2 else [])+[a.executable,'-case',case,'-output',out]
  if ranks==2:cmd+=['-partition',layer_part]
  log=run(cmd);values=fields(out,ranks);solutions.append(values);error=0
  for node,fs in values.items():
   y=layer_points[node][1];exact=[tau*(min(y,.5)/lower+max(y-.5,0)/upper),0,0]
   error=max(error,abs(fs['pressure'][0]-2),max(abs(u-v) for u,v in zip(fs['velocity'],exact)))
  assert error<2e-9,error
  profile={xyz[1]:values[n]['velocity'][0] for n,xyz in layer_points.items() if xyz[0]==xyz[2]==.5}
  lower_stress=lower*(profile[.5]-profile[.25])/.25
  upper_stress=upper*(profile[.75]-profile[.5])/.25
  assert max(abs(lower_stress-tau),abs(upper_stress-tau))<2e-9
  for side,sign in ((0.,-1),(1.,1)):
   reaction=sum(fs['momentum_residual'][0] for n,fs in values.items() if layer_points[n][1]==side)
   assert abs(reaction-sign*tau)<2e-9,(side,reaction,tau)
  for tag,sign in ((1,-1),(2,1)):
   summary=re.search(rf'boundary_tag={tag} area=(\S+) outward_flow=(\S+) mean_pressure=(\S+)',log)
   assert summary and abs(float(summary[1])-1)<2e-12 and abs(float(summary[2])-sign*flow)<2e-9 and abs(float(summary[3])-2)<2e-9,log
  assert abs(float(re.search(r'net_outward_flow=(\S+)',log)[1]))<2e-9
  assert abs(float(re.search(r'divergence_l2=(\S+)',log)[1]))<2e-9
  print('layered shear',lower,upper,'ranks',ranks,'field_error',error,'interface_stress',lower_stress,upper_stress,'flow',flow)
 for n in solutions[0]:
  for field in solutions[0][n]:assert max(abs(x-y) for x,y in zip(solutions[0][n][field],solutions[1][n][field]))<2e-9
print('regions, layered shear, tagged observations, component constraints and normalized reactions passed')
