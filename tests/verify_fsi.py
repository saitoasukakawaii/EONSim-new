"""Monolithic piston: independent added-mass BE reference, balance and MPI fields."""
import argparse
import re
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
p=argparse.ArgumentParser(); p.add_argument('--executable',type=Path,required=True)
p.add_argument('--mpiexec',required=True); p.add_argument('--case',type=Path,required=True)
p.add_argument('--work',type=Path,required=True); a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    if r.returncode: raise RuntimeError(r.stdout)
    return r.stdout
def history(text):
    return [{k:float(v) for k,v in re.findall(r'(\w+)=([^\s]+)',line)} for line in text.splitlines() if line.startswith('fsi_step=')]
def values(path,ranks):
    owned={}; ghosts=[]
    for rank in range(ranks):
        tree=ET.parse(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
        f={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
        for i,node in enumerate(f['mesh_node_id']):
            v=f['velocity'][3*i:3*i+3]+f['mesh_displacement'][3*i:3*i+3]+[f['pressure'][i]]
            if int(f['owner'][i])==rank: assert node not in owned; owned[node]=v
            else: ghosts.append((node,v))
    for node,v in ghosts: assert max(abs(x-y) for x,y in zip(v,owned[node]))<1e-9
    return owned
partition=a.work/'partition2'; run([a.executable,'-case',a.case,'-prepare',partition,'-parts',2])
out=a.work/'rigid.vtu'; out2=a.work/'rigid2.vtu'
serial=run([a.executable,'-case',a.case,'-output',out])
parallel=run([a.mpiexec,'-n',2,a.executable,'-case',a.case,'-partition',partition,'-output',out2])
hs,hp=history(serial),history(parallel)
assert len(hs)==len(hp)==5
q=vn=0.; dt=.02
for s,p in zip(hs,hp):
    v=vn
    # Current-volume plug flow: (m+rho*(1+q))*a+c*v+k*q=P.
    for _ in range(12):
        qtrial=q+dt*v
        r=(2+1+qtrial)*(v-vn)/dt+.3*v+5*qtrial-1
        j=(3+qtrial)/dt+(v-vn)+.3+5*dt
        v-=r/j
    q+=dt*v
    assert abs(s['velocity']-v)<2e-9 and abs(s['position']-q)<2e-10
    assert abs(s['body_balance'])<1e-9
    for key in ('position','velocity','fluid_force'): assert abs(s[key]-p[key])<2e-9
    vn=v
x,y=values(out,1),values(out2,2)
assert x.keys()==y.keys()
assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
assert max(abs(state[0]-vn) for state in x.values())<2e-9
zero=a.work/'zero.yaml'
zero.write_text(a.case.read_text().replace('mesh: cube.msh',f'mesh: {(a.case.parent/"cube.msh").resolve()}').replace('pressure: 1','pressure: 0'))
z=history(run([a.executable,'-case',zero,'-output',a.work/'zero.vtu']))
assert all(abs(s['position'])<1e-14 for s in z)
# Independent full-system differencing also sees affine interface chain coefficients.
checked=run([a.executable,'-case',a.case,'-output',a.work/'jacobian.vtu','-snes_test_jacobian'])
ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F = ([\deE+.-]+)',checked)))
assert ratios and max(ratios)<2e-6
print('FSI passed: added mass, body balance, pressure-driven motion, full Jv and 1/2 rank')
