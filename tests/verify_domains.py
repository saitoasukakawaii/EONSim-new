"""Independent domains, unequal cell counts, shared kinematics/force balance and restart."""
import argparse,hashlib,json,math,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_domains import generate
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--scheme',choices=['be','bdf2'],default='be');a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
case=generate(a.work)
if a.scheme!='be':
 cfg=json.loads(case.read_text());cfg['time']=dict(scheme=a.scheme);cfg['fsi']['stabilization_tau']=.05;case.write_text(json.dumps(cfg))
def run(args,error=None):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=80)
 if (r.returncode==0)!=(error is None) or (error and error not in r.stdout):raise RuntimeError(r.stdout)
 return r.stdout
def data(path,ranks,solid=False):
 result={};nodes=set();count=0
 for rank in range(ranks):
  suffix=('_solid' if solid else '')+(f'_rank{rank}' if ranks>1 else '')+'.vtu';root=ET.parse(path.with_name(path.stem+suffix))
  f={x.attrib['Name']:x.text.split() for x in root.findall('.//PointData/DataArray')};ids=list(map(int,f['mesh_node_id']));xyz=list(map(float,root.find('.//Points/DataArray').text.split()))
  connectivity=list(map(int,root.find('.//Cells/DataArray[@Name="connectivity"]').text.split()));count+=len(connectivity)//4
  nodes.update(ids[i] for i in connectivity)
  for i,n in enumerate(ids):
   if int(f['owner'][i])==rank:result[n]=xyz[3*i:3*i+3]+list(map(float,f['velocity'][3*i:3*i+3]))+list(map(float,f['displacement' if solid else 'mesh_displacement'][3*i:3*i+3]))
 return result,nodes,count
def pressure(path,ranks):
 result={}
 for rank in range(ranks):
  suffix=(f'_rank{rank}' if ranks>1 else '')+'.vtu';root=ET.parse(path.with_name(path.stem+suffix))
  f={x.attrib['Name']:x.text.split() for x in root.findall('.//PointData/DataArray')}
  for i,node in enumerate(f['mesh_node_id']):
   if int(f['owner'][i])==rank:result[int(node)]=float(f['pressure'][i])
 return result
def compare(first,second,ranks):
 for solid in (False,True):
  x,_,_=data(first,ranks,solid);y,_,_=data(second,ranks,solid)
  assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
 x,y=pressure(first,ranks),pressure(second,ranks);assert x.keys()==y.keys()
 assert max(abs(x[n]-y[n]) for n in x)<2e-9
solutions=[];pressures=[]
for ranks in ((1,2,4) if a.scheme=='bdf2' else (1,2)):
 part=a.work/f'part{ranks}';run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
 prefix=([a.mpiexec,'-n',ranks] if ranks>1 else [])+[a.executable,'-case',case,'-partition',part]
 out=a.work/f'full{ranks}.vtu';text=run(prefix+['-output',out]);f,fn,nf=data(out,ranks);s,sn,ns=data(out,ranks,True)
 assert nf!=ns and len(fn)!=len(sn)
 interface=fn&sn;assert len(interface)==9
 assert max(abs(v-w) for n in interface for v,w in zip(f[n],s[n]))<2e-10
 assert max(abs(float(x)) for x in re.findall('body_balance=(\\S+)',text))<2e-9
 assert max(abs(float(x)) for x in re.findall('power_balance=(\\S+)',text))<2e-9
 assert float(re.findall('position=(\\S+)',text)[-1])>0
 reports=[dict(item.split('=') for item in line.split()[1:]) for line in text.splitlines() if line.startswith('field_residual ')]
 assert len(reports)==20 and {f['name'] for f in reports}=={'velocity','pressure','mesh','structure'}
 for report in reports:
  assert report['accepted']=='1' and float(report['rms'])<=float(report['limit'])
  assert int(report['equation_rows'])>0 and int(report['constraint_rows'])==0
 solutions.append((f,s))
 pressures.append(pressure(out,ranks))
 checkpoint=a.work/f'checkpoint{ranks}';run(prefix+['-checkpoint',checkpoint,'-stop_after',2,'-output',a.work/'partial.vtu'])
 snapshot={p:hashlib.sha256(p.read_bytes()).digest() for p in checkpoint.rglob('*') if p.is_file()}
 rejected=run(prefix+['-restart',checkpoint,'-checkpoint',checkpoint,'-snes_convergence_test','skip','-snes_max_it',0,
                      '-output',a.work/f'rejected{ranks}.vtu'],'Field acceptance failed')
 assert 'fsi_step=' not in rejected and 'status=success' not in rejected
 assert snapshot=={p:hashlib.sha256(p.read_bytes()).digest() for p in checkpoint.rglob('*') if p.is_file()}
 resumed=a.work/f'resumed{ranks}.vtu';run(prefix+['-restart',checkpoint,'-output',resumed]);compare(out,resumed,ranks)
 jacobian=run(prefix+['-snes_test_jacobian','-output',a.work/f'jac{ranks}.vtu'])
 (a.work/f'jacobian{ranks}.log').write_text(jacobian)
 errors=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([^,\s]+)',jacobian)))
 # PETSc 默认单边差分的整体矩阵诊断；这不替代局部高精度方向导数或离散误差研究。
 assert len(errors)>=5 and all(math.isfinite(e) and 0<=e<1e-6 for e in errors),errors
 print('assembled Jacobian',ranks,'relative Frobenius error',max(errors))
 print('domains',ranks,'cells',nf,ns,'interface nodes',len(interface))
for parallel in solutions[1:]:
 for x,y in zip(solutions[0],parallel):assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
for y in pressures[1:]:
 x=pressures[0];assert x.keys()==y.keys() and max(abs(x[n]-y[n]) for n in x)<2e-9
# Field names and scales are input contracts; typos or incomplete declarations cannot fall back silently.
original_case=case.read_text()
for mode,error in (('scale','Invalid field tolerance or scale'),('missing','Missing solver field'),('unknown','Unknown solver field')):
 cfg=json.loads(original_case)
 if mode=='scale':cfg['solver']['fields']['mesh']['residual_scale']=0
 elif mode=='missing':del cfg['solver']['fields']['pressure']
 else:cfg['solver']['fields']['typo']=cfg['solver']['fields'].pop('pressure')
 case.write_text(json.dumps(cfg));run([a.executable,'-case',case],error)
case.write_text(original_case)
# A shifted solid must fail interface matching, not silently generate a mirrored solid.
solid=a.work/'solid.msh';original=solid.read_text();lines=original.splitlines()
for i in range(lines.index('$Nodes')+2,lines.index('$EndNodes')):
 row=lines[i].split();row[1]=str(float(row[1])+.01);lines[i]=' '.join(row)
solid.write_text('\n'.join(lines)+'\n');run([a.executable,'-case',case,'-prepare',a.work/'bad','-parts',2],'Unmatched');solid.write_text(original)
print('independent FSI domains passed')
