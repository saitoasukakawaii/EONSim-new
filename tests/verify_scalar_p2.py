"""P2 Poisson: exact polynomial, refinement, partition invariance and failures."""
import argparse,json,math,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/scalar2d'))
from generate import generate
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True,type=Path);a=p.parse_args()
def run(args,error=None):
 r=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
 if error:assert r.returncode!=0 and error in r.stdout,r.stdout
 else:assert r.returncode==0,r.stdout
 return r.stdout
def solve(label,n=4,ranks=1,kind='quadratic',topology='tri',change=None,error=None,extra=(),distorted=False):
 folder=a.work/label;case=generate(folder,n,topology,'4.1',distorted,ranks==2);cfg=json.loads(case.read_text());c=cfg['scalar2d'];c.update(degree=2,manufactured=kind)
 for b in c['boundaries']:b['type']='dirichlet' if b['region'] in ('left','bottom') else 'neumann';b.pop('coefficient',None)
 if change:change(cfg)
 case.write_text(json.dumps(cfg));part=folder/'part'
 if error and error.startswith('P2') and (topology!='tri' or change):
  text=run([a.executable,'-case',case,'-prepare',part,'-parts',ranks],error);return None,None
 run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
 text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra],error);(folder/'run.log').write_text(text)
 if error:assert not (folder/'solution.pvtu').exists();return None,None
 report=dict(x.split('=') for x in next(line for line in text.splitlines() if line.startswith('scalar_p2 ')).split()[1:]);report={k:float(v) for k,v in report.items()}
 values={}
 for rank in range(ranks):
  tree=ET.parse(folder/('solution.vtu' if ranks==1 else f'solution_rank{rank}.vtu'))
  fields={x.attrib['Name']:x.text.split() for x in tree.findall('.//PointData/DataArray')}
  assert set(tree.find('.//Cells/DataArray[@Name="types"]').text.split())=={'22'}
  for i,owner in enumerate(fields['owner']):
   key=(int(fields['entity_first'][i]),int(fields['entity_second'][i]));v=float(fields['u'][i])
   if key in values:assert abs(values[key]-v)<2e-9
   if int(owner)==rank:values[key]=v
 if ranks>1:ET.parse(folder/'solution.pvtu')
 return values,report
records=[]
base=None
for rank in (1,2):
 values,r=solve(f'patch-{rank}',ranks=rank,distorted=True)
 assert r['l2_error']<2e-10 and r['h1_error']<2e-9,r
 if base:assert values.keys()==base.keys() and max(abs(values[k]-base[k]) for k in base)<2e-9
 base=values;records.append(r)
previous=None
for n in (4,8,16):
 values,r=solve(f'sine-{n}',n=n,kind='sine')
 if previous:
  r['l2_order']=math.log(previous['l2_error']/r['l2_error'],2);r['h1_order']=math.log(previous['h1_error']/r['h1_error'],2)
  if n==16:assert r['l2_order']>=2.8 and r['h1_order']>=1.8,r
 previous=r;records.append(r)
parallel,_=solve('sine-16-mpi2',n=16,ranks=2,kind='sine');assert parallel.keys()==values.keys() and max(abs(parallel[k]-values[k]) for k in values)<2e-9
solve('quad',topology='quad',error='P2 requires Tri3')
solve('transient',change=lambda c:c['scalar2d'].update(mode='diffusion'),error='P2 supports steady')


# Robin can anchor the entire problem without any essential boundary.
for boundary_type in ('robin','neumann'):
 baseline=None
 for rank in (1,2):
  def boundary_case(cfg):
   for b in cfg['scalar2d']['boundaries']:
    b.update(type=boundary_type)
    if boundary_type=='robin':b['coefficient']=2
  fields,report=solve(f'{boundary_type}-{rank}',ranks=rank,distorted=True,change=boundary_case)
  assert report['l2_error']<2e-10 and report['h1_error']<2e-9,report
  if boundary_type=='neumann':assert abs(report['integral'])<1e-12,report
  if baseline:assert fields.keys()==baseline.keys() and max(abs(fields[k]-baseline[k]) for k in fields)<2e-9
  baseline=fields;records.append(dict(boundary=boundary_type,ranks=rank,**report))
# Explicit user data also exercises the non-manufactured Robin load path.
def robin_user(cfg):
 c=cfg['scalar2d'];c.pop('manufactured');c['source']=-6
 # u=1+x+2y+x²+2y², alpha=2; boundary restrictions below use full polynomials.
 values={'left':[1,2,4,2,0,4],'right':[5,2,4,2,0,4],'bottom':[0,2,4,2,0,4],'top':[8,2,4,2,0,4]}
 for b in c['boundaries']:b.update(type='robin',coefficient=2,value={'polynomial':values[b['region']]})
user_fields,user_report=solve('robin-user',ranks=2,change=robin_user)
reference,_=solve('robin-reference',ranks=2,change=lambda cfg:[b.update(type='robin',coefficient=2) for b in cfg['scalar2d']['boundaries']])
assert user_fields.keys()==reference.keys() and max(abs(user_fields[k]-reference[k]) for k in reference)<2e-9
# Neumann incompatibility must be rejected, never repaired by fixing a node.
def incompatible(cfg):
 c=cfg['scalar2d'];c.pop('manufactured');c['source']=1
 for b in c['boundaries']:b.update(type='neumann',value=0)
solve('incompatible-neumann',ranks=2,change=incompatible,error='Incompatible pure Neumann load')
solve('solver-failure',ranks=2,kind='sine',extra=['-ksp_max_it',0],error='Linear solve did not converge')
# A legacy P1 partition must never be silently interpreted as a P2 space.
folder=a.work/'missing-space';case=generate(folder,4,'tri','4.1',False,False)
cfg=json.loads(case.read_text())
for b in cfg['scalar2d']['boundaries']:b.update(type='dirichlet');b.pop('coefficient',None)
case.write_text(json.dumps(cfg));run([a.executable,'-case',case,'-prepare',folder/'part','-parts',2])
cfg['scalar2d']['degree']=2;case.write_text(json.dumps(cfg))
run([a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',folder/'part'],error='Missing P2 space')
assert not (folder/'solution.pvtu').exists()
(a.work/'evidence.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2))
