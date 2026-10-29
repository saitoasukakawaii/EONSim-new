"""Independent domains, unequal cell counts, shared kinematics/force balance and restart."""
import argparse,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_domains import generate
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
case=generate(a.work)
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
def compare(first,second,ranks):
 for solid in (False,True):
  x,_,_=data(first,ranks,solid);y,_,_=data(second,ranks,solid)
  assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
solutions=[]
for ranks in (1,2):
 part=a.work/f'part{ranks}';run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
 prefix=([a.mpiexec,'-n',ranks] if ranks>1 else [])+[a.executable,'-case',case,'-partition',part]
 out=a.work/f'full{ranks}.vtu';text=run(prefix+['-output',out]);f,fn,nf=data(out,ranks);s,sn,ns=data(out,ranks,True)
 assert nf!=ns and len(fn)!=len(sn)
 interface=fn&sn;assert len(interface)==9
 assert max(abs(v-w) for n in interface for v,w in zip(f[n],s[n]))<2e-10
 assert max(abs(float(x)) for x in re.findall('body_balance=(\\S+)',text))<2e-9
 assert float(re.findall('position=(\\S+)',text)[-1])>0
 solutions.append((f,s))
 checkpoint=a.work/f'checkpoint{ranks}';run(prefix+['-checkpoint',checkpoint,'-stop_after',2,'-output',a.work/'partial.vtu'])
 resumed=a.work/f'resumed{ranks}.vtu';run(prefix+['-restart',checkpoint,'-output',resumed]);compare(out,resumed,ranks)
 if ranks==1:run(prefix+['-snes_test_jacobian','-output',a.work/'jac.vtu'])
 print('domains',ranks,'cells',nf,ns,'interface nodes',len(interface))
for x,y in zip(*solutions):assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
# A shifted solid must fail interface matching, not silently generate a mirrored solid.
solid=a.work/'solid.msh';original=solid.read_text();lines=original.splitlines()
for i in range(lines.index('$Nodes')+2,lines.index('$EndNodes')):
 row=lines[i].split();row[1]=str(float(row[1])+.01);lines[i]=' '.join(row)
solid.write_text('\n'.join(lines)+'\n');run([a.executable,'-case',case,'-prepare',a.work/'bad','-parts',2],'Unmatched');solid.write_text(original)
print('independent FSI domains passed')
