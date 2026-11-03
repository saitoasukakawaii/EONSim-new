"""Conforming elastic top-wall channel with fixed affine velocity inlet."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'poisson'))
from generate_mesh import write_mesh


def generate(directory,n=2,nonlinear=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    write_mesh(directory/'fluid.msh',n);write_mesh(directory/'solid.msh',n)
    path=directory/'solid.msh';lines=path.read_text().splitlines()
    for i in range(lines.index('$Nodes')+2,lines.index('$EndNodes')):
        r=lines[i].split();x,y,z=map(float,r[1:]);lines[i]=f'{r[0]} {x:.17g} {1+.25*y:.17g} {z:.17g}'
    for i in range(lines.index('$PhysicalNames')+2,lines.index('$EndPhysicalNames')):
        r=lines[i].split();r[1]=str(int(r[1])+10);lines[i]=' '.join(r)
    for i in range(lines.index('$Elements')+2,lines.index('$EndElements')):
        r=lines[i].split();r[3]=str(int(r[3])+10);lines[i]=' '.join(r)
    path.write_text('\n'.join(lines)+'\n')
    constraint=lambda tag,components:dict(tag=tag,components=components)
    domains=dict(solid_mesh='solid.msh',fluid_region=10,solid_region=20,fluid_interface=4,solid_interface=13,
        pressure_tags=[2],fluid_constraints=[constraint(3,[1]),constraint(5,[2]),constraint(6,[2])],
        mesh_constraints=[constraint(1,[0,1,2]),constraint(2,[0,1,2]),constraint(3,[0,1,2]),constraint(5,[2]),constraint(6,[2])],
        solid_constraints=[constraint(11,[0,1,2]),constraint(12,[0,1,2]),constraint(15,[2]),constraint(16,[2])])
    case=dict(mesh='fluid.msh',output='solution.vtu',fsi=dict(body='elastic',domains=domains,young=100,poisson=.3,
        material='neo_hookean' if nonlinear else 'linear',dt=.002,steps=50,pressure=0,output_interval=10,
        inlet=dict(tag=1,value=[.1,0,0],gradient=[[0,-.1,0],[0,0,0],[0,0,0]],ramp_time=.02)),
        time=dict(scheme='generalized_alpha',rho_infinity=.5),
        solver=dict(relative_tolerance=1e-10,absolute_tolerance=1e-12,maximum_iterations=30))
    path=directory/'case.json';path.write_text(json.dumps(case,indent=2)+'\n');return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('build/fsi-wall'))
    p.add_argument('--subdivisions',type=int,default=2);p.add_argument('--nonlinear',action='store_true');a=p.parse_args()
    print(generate(a.output,a.subdivisions,a.nonlinear))
