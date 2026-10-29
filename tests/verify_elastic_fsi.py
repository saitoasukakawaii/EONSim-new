"""Elastic FSI: shared interface kinematics, action/reaction, body load and MPI."""
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
def nodes(path,ranks):
    owned={}; ghosts=[]
    for rank in range(ranks):
        tree=ET.parse(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
        f={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
        xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
        disp='mesh_displacement' if 'mesh_displacement' in f else 'displacement'
        for i,node in enumerate(f['mesh_node_id']):
            v=xyz[3*i:3*i+3]+f['velocity'][3*i:3*i+3]+f[disp][3*i:3*i+3]
            if int(f['owner'][i])==rank: assert node not in owned; owned[node]=v
            else: ghosts.append((node,v))
    for node,v in ghosts: assert max(abs(x-y) for x,y in zip(v,owned[node]))<1e-9
    return owned
partition=a.work/'partition2'; run([a.executable,'-case',a.case,'-prepare',partition,'-parts',2])
out=a.work/'elastic.vtu'; out2=a.work/'elastic2.vtu'
hs=history(run([a.executable,'-case',a.case,'-output',out]))
hp=history(run([a.mpiexec,'-n',2,a.executable,'-case',a.case,'-partition',partition,'-output',out2]))
assert len(hs)==len(hp)==10
assert hs[-1]['position']>1e-4
# Independent two-element 1D solid with constrained lateral strain and fluid added mass.
# This is an approximate dynamic reference: 3D Tet4 permits transverse/interface
# variation absent from the 1D subspace; compare at 1% of the characteristic response.
h=.125; dt=.02; modulus=100*(1-.3)/((1+.3)*(1-2*.3))
M=[[h/3,h/6],[h/6,2*h/3]]; K=[[modulus/h,-modulus/h],[-modulus/h,2*modulus/h]]
d=[0.,0.]; old=[0.,0.]
for state in hs:
    v=old.copy()
    for _ in range(12):
        trial=[d[i]+dt*v[i] for i in range(2)]
        r=[sum(M[i][j]*(v[j]-old[j])/dt+K[i][j]*trial[j] for j in range(2)) for i in range(2)]
        r[0]+=(1+trial[0])*(v[0]-old[0])/dt-1
        J=[[M[i][j]/dt+dt*K[i][j] for j in range(2)] for i in range(2)]
        J[0][0]+=(1+trial[0])/dt+v[0]-old[0]
        det=J[0][0]*J[1][1]-J[0][1]*J[1][0]
        v[0]-=(J[1][1]*r[0]-J[0][1]*r[1])/det
        v[1]-=(-J[1][0]*r[0]+J[0][0]*r[1])/det
    d=[d[i]+dt*v[i] for i in range(2)]; old=v
    assert abs(state['position']-d[0])<.01*(.25/modulus)
    assert abs(state['velocity']-v[0])<.01*.03
for s,p in zip(hs,hp):
    assert abs(s['body_balance'])<1e-9
    for key in ('position','velocity','fluid_force'): assert abs(s[key]-p[key])<2e-9
for suffix in ('','_solid'):
    x,y=nodes(out.with_stem(out.stem+suffix),1),nodes(out2.with_stem(out2.stem+suffix),2)
    assert x.keys()==y.keys()
    assert max(abs(v-w) for n in x for v,w in zip(x[n],y[n]))<2e-9
fluid=nodes(out,1); solid=nodes(out.with_stem(out.stem+'_solid'),1)
for n,f in fluid.items():
    if abs(f[0]-f[6]-1)<1e-12:
        assert max(abs(v-w) for v,w in zip(f,solid[n]))<1e-10
zero=a.work/'zero.yaml'
zero.write_text(a.case.read_text().replace('mesh: cube.msh',f'mesh: {(a.case.parent/"cube.msh").resolve()}').replace('pressure: 1','pressure: 0'))
z=history(run([a.executable,'-case',zero,'-output',a.work/'zero.vtu']))
assert all(abs(s['position'])<1e-14 for s in z)
settled=a.work/'settled.yaml'
settled.write_text(a.case.read_text().replace('mesh: cube.msh',f'mesh: {(a.case.parent/"cube.msh").resolve()}').replace('steps: 10','steps: 200'))
final=history(run([a.executable,'-case',settled,'-output',a.work/'settled.vtu']))[-1]
assert abs(final['position']-.25/modulus)<1e-8
assert abs(final['velocity'])<1e-7
text=run([a.executable,'-case',a.case,'-output',a.work/'jacobian.vtu','-snes_test_jacobian'])
ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F = ([\deE+.-]+)',text)))
assert ratios and max(ratios)<2e-6
print('elastic FSI passed: common interface geometry/velocity, force balance, load response, full Jacobian, MPI')
