"""Analytic traction patch, reaction, unloaded BE energy and MPI consistency."""
import argparse
import re
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
p=argparse.ArgumentParser()
p.add_argument('--executable',type=Path,required=True); p.add_argument('--mpiexec',required=True)
p.add_argument('--case',type=Path,required=True); p.add_argument('--work',type=Path,required=True)
a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=80)
    if r.returncode: raise RuntimeError(r.stdout)
    return r.stdout
def metric(text,name): return float(re.search(r'\b'+name+r'=([^\s]+)',text)[1])
def values(path,ranks):
    owned={}; ghosts=[]
    for rank in range(ranks):
        tree=ET.parse(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
        f={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
        for i,node in enumerate(f['mesh_node_id']):
            v=f['displacement'][3*i:3*i+3]+f['velocity'][3*i:3*i+3]
            if int(f['owner'][i])==rank:
                assert node not in owned; owned[node]=v
            else: ghosts.append((node,v))
    for node,v in ghosts: assert max(abs(x-y) for x,y in zip(v,owned[node]))<1e-10
    return owned
partition=a.work/'partition2'
run([a.executable,'-case',a.case/'static.yaml','-prepare',partition,'-parts',2])
for mode in ('static','unload'):
    out=a.work/f'{mode}.vtu'; out2=a.work/f'{mode}2.vtu'; case=a.case/f'{mode}.yaml'
    serial=run([a.executable,'-case',case,'-output',out])
    parallel=run([a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',partition,'-output',out2])
    x,y=values(out,1),values(out2,2)
    assert x.keys()==y.keys()
    assert max(abs(v-w) for node in x for v,w in zip(x[node],y[node]))<2e-10
    if mode=='static':
        assert metric(serial,'displacement_max_error')<1e-11
        assert abs(metric(serial,'reaction_x')+1)<1e-10
        assert abs(metric(serial,'strain_energy')-.005)<1e-11
    else:
        energies=list(map(float,re.findall(r'\btotal_energy=([^\s]+)',serial)))
        assert len(energies)==21
        assert all(b<a for a,b in zip(energies,energies[1:]))
        assert energies[-1]<energies[0]*.8
        assert abs(metric(serial,'tip_displacement')-.01)>.001
    print(mode,serial.strip().splitlines()[-2])
print('solid verification passed')
