"""Conforming T-shaped elastic duct with an inlet and two independently tagged fixed outlets."""
import argparse
import itertools
import json
from collections import Counter
from pathlib import Path
from generate_tube import write_tet_mesh


def voxel_tets(voxel):
    """Kuhn simplices on the positive half; reflect the negative half through y=0."""
    i,j,k=voxel
    negative=j<0
    start=(i,-j-1 if negative else j,k)
    for axes in itertools.permutations(range(3)):
        point=list(start)
        tet=[tuple(point)]
        for axis in axes:
            point[axis]+=1
            tet.append(tuple(point))
        if negative:
            tet=[(x,-y,z) for x,y,z in tet]
        inversions=sum(a>b for a,b in itertools.combinations(axes,2))
        if bool(inversions%2)!=negative:
            tet[1],tet[2]=tet[2],tet[1]
        yield tuple(tet)


def exterior(cells):
    counts=Counter(tuple(sorted(cell[:j]+cell[j+1:])) for cell in cells for j in range(4))
    if max(counts.values())!=2:
        raise ValueError("Nonmanifold T-junction mesh")
    return {face for face,count in counts.items() if count==1}


def generate(directory, refinement=1):
    """Refinement preserves the square lumen, wall thickness, symmetry and three ports."""
    if not isinstance(refinement,int) or refinement<1:
        raise ValueError("T-junction refinement must be a positive integer")
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    m=refinement
    h=.25/m
    # Trunk length 1.5 m to branch centre, two 1 m daughters, lumen width .5 m.
    trunk={(i,j,k) for i in range(7*m) for j in range(-m,m) for k in range(-m,m)}
    crossbar={(i,j,k) for i in range(5*m,7*m) for j in range(-4*m,4*m) for k in range(-m,m)}
    fluid=trunk|crossbar
    outer_trunk={(i,j,k) for i in range(8*m) for j in range(-2*m,2*m) for k in range(-2*m,2*m)}
    outer_bar={(i,j,k) for i in range(4*m,8*m) for j in range(-4*m,4*m) for k in range(-2*m,2*m)}
    wall=(outer_trunk|outer_bar)-fluid
    pieces=[[tet for voxel in sorted(region) for tet in voxel_tets(voxel)] for region in (fluid,wall)]
    boundary=[exterior(cells) for cells in pieces]
    interface=boundary[0]&boundary[1]
    if not interface:
        raise ValueError("Disjoint FSI pieces")
    for solid,(cells,faces) in enumerate(zip(pieces,boundary)):
        points=sorted({p for cell in cells for p in cell})
        index={p:i for i,p in enumerate(points)}
        surface=[]
        for face in sorted(faces):
            if face in interface:
                tag=14 if solid else 4
            elif all(p[0]==0 for p in face):
                tag=11 if solid else 1
            elif all(p[1]==4*m for p in face):
                tag=12 if solid else 2
            elif all(p[1]==-4*m for p in face):
                tag=13 if solid else 3
            elif solid:
                tag=15
            else:
                raise ValueError("Untagged open fluid face")
            surface.append((tag,tuple(index[p] for p in face)))
        name='solid.msh' if solid else 'fluid.msh'
        write_tet_mesh(directory/name,[tuple(h*v for v in p) for p in points],
                       [tuple(index[p] for p in cell) for cell in cells],surface,20 if solid else 10)
    def clamp(tag):
        return dict(tag=tag,components=[0,1,2])
    def port(tag):
        return dict(tag=tag,proximal_resistance=3.,distal_resistance=8.,compliance=.025,distal_pressure=0.)
    cfg=dict(mesh='fluid.msh',output='junction.vtu',time=dict(scheme='generalized_alpha',rho_infinity=.5),
             solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=40),
             fsi=dict(body='elastic',material='neo_hookean',young=100,poisson=.3,dt=.01,steps=20,pressure=0.,
                      pressure_face_history=True,output_interval=10,stabilization_tau=.01,
                      domains=dict(solid_mesh='solid.msh',fluid_region=10,solid_region=20,
                                   fluid_interface=4,solid_interface=14,pressure_tags=[2,3],fluid_constraints=[],
                                   solid_constraints=[clamp(t) for t in (11,12,13)],mesh_constraints=[clamp(t) for t in (1,2,3)],
                                   rcr_outlets=[port(2),port(3)]),
                      inlet=dict(tag=1,ramp_time=.04,flow_rate=dict(mean=.002,amplitude=.0005,period=.20,axis=0,
                                                                    lower=[0,-.25,-.25],upper=[0,.25,.25]))))
    geometry=dict(refinement=m,interface_area=len(interface)*h*h/2,
                  reference_fluid_volume=len(fluid)*h**3,fluid_tetrahedra=len(pieces[0]),solid_tetrahedra=len(pieces[1]),
                  port_area=(2*m*h)**2)
    (directory/'geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
    path=directory/'case.json'
    path.write_text(json.dumps(cfg,indent=2)+'\n')
    return path


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,default=Path('build/fsi-junction'))
    cli.add_argument('--refinement',type=int,default=1)
    args=cli.parse_args()
    print(generate(args.output,args.refinement))
