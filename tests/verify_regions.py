"""Piecewise exact two-material bar and mixed-component incompressible flow, 1/2 rank."""
import argparse,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh
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
   if int(data['owner'][i])==rank:result[int(n)]={key:list(map(float,v[3*i:3*i+3])) if key!='pressure' else [float(v[i])] for key,v in data.items() if key in ('displacement','velocity','pressure')}
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
 base[physics]['regions'].pop();case.write_text(json.dumps(base));run([a.executable,'-case',case],'Missing material for region')
print('regions and component constraints passed')
