"""Rigid BE balance and ALE exact preservation on moving meshes, 1/2 ranks."""
import argparse
import re
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
p=argparse.ArgumentParser(); p.add_argument('--executable',type=Path,required=True)
p.add_argument('--mpiexec',required=True); p.add_argument('--case',type=Path,required=True)
p.add_argument('--work',type=Path,required=True); a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args,ok=True):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    if (r.returncode==0)!=ok: raise RuntimeError(r.stdout)
    return r.stdout
def values(path,ranks):
    owned={}; ghosts=[]
    for rank in range(ranks):
        tree=ET.parse(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
        f={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
        for i,node in enumerate(f['mesh_node_id']):
            v=f['velocity'][3*i:3*i+3]+f['mesh_displacement'][3*i:3*i+3]+f['mesh_velocity'][3*i:3*i+3]
            if int(f['owner'][i])==rank: assert node not in owned; owned[node]=v
            else: ghosts.append((node,v))
    for node,v in ghosts: assert max(abs(x-y) for x,y in zip(v,owned[node]))<1e-10
    return owned
rigid=run([a.executable,'-case',a.case/'rigid.yaml'])
q=v=0
for line in rigid.splitlines():
    if not line.startswith('rigid_step='): continue
    f={k:float(x) for k,x in re.findall(r'(\w+)=([^\s]+)',line)}
    assert abs(f['position']-q-.02*f['velocity'])<1e-13
    assert abs(2*(f['velocity']-v)/.02+.3*f['velocity']+5*f['position']-1)<1e-12
    q,v=f['position'],f['velocity']
partition=a.work/'partition2'
run([a.executable,'-case',a.case/'uniform.yaml','-prepare',partition,'-parts',2])
for mode in ('uniform','shear'):
    case=a.case/f'{mode}.yaml'; out=a.work/f'{mode}.vtu'; out2=a.work/f'{mode}2.vtu'
    for args in ([a.executable,'-case',case,'-output',out],
                 [a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',partition,'-output',out2]):
        text=run(args)
        errors=list(map(float,re.findall(r'velocity_max_error=([^\s]+)',text)))
        assert len(errors)==5 and max(errors)<1e-10
        assert min(map(float,re.findall(r'min_volume=([^\s]+)',text)))>0
    x,y=values(out,1),values(out2,2)
    assert x.keys()==y.keys()
    assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<1e-10
    assert max(abs(v) for state in x.values() for v in state[3:6])>.01
    print(mode,'preserved velocity on nonzero mesh motion')
bad=a.work/'invalid.yaml'; bad.write_text((a.case/'uniform.yaml').read_text().replace('../poisson/cube.msh',str((a.case/'../poisson/cube.msh').resolve())).replace('amplitude: 0.1','amplitude: 20'))
run([a.executable,'-case',bad,'-output',a.work/'invalid.vtu'],False)
print('motion verification passed')
