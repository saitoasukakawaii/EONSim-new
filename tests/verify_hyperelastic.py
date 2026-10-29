"""Finite-strain independent solid and same monolithic FSI route."""
import argparse, math, re, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh
p=argparse.ArgumentParser(); p.add_argument('--executable',type=Path,required=True); p.add_argument('--mpiexec',required=True)
p.add_argument('--root',type=Path,required=True); p.add_argument('--work',type=Path,required=True)
a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
    if r.returncode: raise RuntimeError(r.stdout)
    return r.stdout
def histories(text): return [{k:float(v) for k,v in re.findall(r'(\w+)=([^\s]+)',l)} for l in text.splitlines() if l.startswith('fsi_step=')]
def field(path,name):
    x=ET.parse(path).find(f'.//PointData/DataArray[@Name="{name}"]'); return list(map(float,x.text.split()))
solid=a.root/'cases/solid/hyperelastic.yaml'; out=a.work/'solid.vtu'
text=run([a.executable,'-case',solid,'-output',out])
assert abs(float(re.search(r'reaction_x=([^\s]+)',text)[1])+20)<1e-8
# Homogeneous uniaxial Piola traction, free transverse faces.
mu=100/2.6; lam=100*.3/(1.3*.4); axial=1.2; lateral=.95
for _ in range(12):
    c=lam*math.log(axial*lateral*lateral)-mu
    r0=mu*axial+c/axial-20; r1=mu*lateral+c/lateral
    A=mu+(lam-c)/(axial*axial); B=2*lam/(axial*lateral)
    C=lam/(axial*lateral); D=mu+(2*lam-c)/(lateral*lateral); det=A*D-B*C
    axial-=(D*r0-B*r1)/det; lateral-=(-C*r0+A*r1)/det
xyz=list(map(float,ET.parse(out).find('.//Points/DataArray').text.split()))
d=field(out,'displacement')
assert max(abs(v-xyz[i]*((axial if i%3==0 else lateral)-1)) for i,v in enumerate(d))<1e-9
unload=a.work/'unload.yaml'
unload.write_text(solid.read_text().replace('../poisson/cube.msh',str((a.root/'cases/poisson/cube.msh').resolve())).replace('mode: static','mode: unload'))
unloaded=run([a.executable,'-case',unload,'-output',a.work/'unload.vtu'])
energies=list(map(float,re.findall(r'\btotal_energy=([^\s]+)',unloaded)))
assert len(energies)==21 and all(b<a for a,b in zip(energies,energies[1:]))
case=a.root/'cases/fsi/hyperelastic.yaml' ; out=a.work/'fsi.vtu'
hs=histories(run([a.executable,'-case',case,'-output',out]))
partition=a.work/'partition2'; run([a.executable,'-case',case,'-prepare',partition,'-parts',2])
hp=histories(run([a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',partition,'-output',a.work/'fsi2.vtu']))
for s,p in zip(hs,hp):
    assert abs(s['body_balance'])<2e-8
    assert abs(s['position']-p['position'])<2e-9
assert .015<max(s['position'] for s in hs)<.1
base=case.read_text().replace('mesh: cube.msh',f'mesh: {(case.parent/"cube.msh").resolve()}')
linear=a.work/'linear.yaml'; linear.write_text(base.replace('material: neo_hookean','material: linear'))
hl=histories(run([a.executable,'-case',linear,'-output',a.work/'linear.vtu']))
assert abs(hs[-1]['position']-hl[-1]['position'])>.001
fine=a.work/'dt.yaml'; fine.write_text(base.replace('dt: 0.02','dt: 0.01').replace('steps: 10','steps: 20'))
ht=histories(run([a.executable,'-case',fine,'-output',a.work/'dt.vtu']))
# BE numerical damping changes transient peaks; require bounded response, report difference.
assert abs(ht[-1]['position']-hs[-1]['position'])<.4*max(s['position'] for s in hs)
mesh=a.work/'cube4.msh'; write_mesh(mesh,4)
hm=histories(run([a.executable,'-case',case,'-mesh',mesh,'-output',a.work/'mesh.vtu']))
assert abs(hm[-1]['position']-hs[-1]['position'])<.03*max(s['position'] for s in hs)
checked=run([a.executable,'-case',case,'-output',a.work/'jacobian.vtu','-snes_test_jacobian'])
ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F = ([\deE+.-]+)',checked)))
assert ratios and max(ratios)<2e-6
print('uniaxial stretches',axial,lateral)
print('FSI final displacements baseline/dt-half/mesh-fine/linear',hs[-1]['position'],ht[-1]['position'],hm[-1]['position'],hl[-1]['position'])
print('hyperelastic verification passed')
