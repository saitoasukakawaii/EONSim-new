"""Deterministic conforming polygonal tube with an independent solid annulus.

Linear facets approximate a circular cylinder. Sorted cross-section vertices give
identical prism-face diagonals in both independently written domain meshes.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path


def generate(directory, sectors=12, axial=4, radial=2, radius=1., thickness=.2, length=4.):
    if sectors<6 or axial<2 or radial<1 or not all(math.isfinite(x) and x>0 for x in (radius,thickness,length)):
        raise ValueError('Invalid tube dimensions or subdivisions')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    points=[(0.,0.)]
    for layer in range(1,radial+2):
        r=radius*layer/radial if layer<=radial else radius+thickness
        points.extend((r*math.cos(2*math.pi*j/sectors),r*math.sin(2*math.pi*j/sectors)) for j in range(sectors))
    def ring(layer,j):return 1+(layer-1)*sectors+j%sectors
    fluid=[(0,ring(1,j),ring(1,j+1)) for j in range(sectors)]
    solid=[]
    for layer in range(1,radial+1):
        target=fluid if layer<radial else solid
        for j in range(sectors):
            a,b,c,d=ring(layer,j),ring(layer,j+1),ring(layer+1,j),ring(layer+1,j+1)
            target.extend(((a,b,d),(a,d,c)))
    for name,triangles,offset,region in (('fluid',fluid,0,10),('solid',solid,10,20)):
        active=sorted(set(v for tri in triangles for v in tri));lookup={v:i for i,v in enumerate(active)};width=len(active)
        xyz=[(length*k/axial,*points[v]) for k in range(axial+1) for v in active]
        cells=[]
        for k in range(axial):
            for tri in triangles:
                a,b,c=[k*width+lookup[v] for v in sorted(tri)];A,B,C=a+width,b+width,c+width
                cells.extend(((a,b,c,C),(a,b,B,C),(a,A,B,C)))
        # Positive Tet4 orientation, independent of triangle ordering.
        def determinant(t):
            o=xyz[t[0]];u,v,w=[[xyz[i][j]-o[j] for j in range(3)] for i in t[1:]]
            return u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0])
        cells=[t if determinant(t)>0 else (t[1],t[0],t[2],t[3]) for t in cells]
        assert all(determinant(t)>0 for t in cells)
        faces=Counter(tuple(sorted(t[:skip]+t[skip+1:])) for t in cells for skip in range(4))
        assert max(faces.values())==2
        boundary=[]
        for face,count in faces.items():
            if count!=1:continue
            if all(xyz[i][0]==0 for i in face):tag=1+offset
            elif all(xyz[i][0]==length for i in face):tag=2+offset
            elif name=='fluid' or all(abs(math.hypot(*xyz[i][1:])-radius)<1e-12 for i in face):tag=3+offset
            else:tag=14
            boundary.append((tag,face))
        with (directory/(name+'.msh')).open('w') as f:
            f.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n'+str(len(xyz))+'\n')
            for i,x in enumerate(xyz,1):f.write(f'{i} '+ ' '.join(format(v,'.17g') for v in x)+'\n')
            f.write('$EndNodes\n$Elements\n'+str(len(cells)+len(boundary))+'\n')
            for i,(tag,face) in enumerate(boundary,1):f.write(f'{i} 2 2 {tag} {tag} '+' '.join(str(v+1) for v in face)+'\n')
            for i,t in enumerate(cells,len(boundary)+1):f.write(f'{i} 4 2 {region} {region} '+' '.join(str(v+1) for v in t)+'\n')
            f.write('$EndElements\n')
    constraint=lambda tag:dict(tag=tag,components=[0,1,2])
    cfg=dict(mesh='fluid.msh',output='tube.vtu',fsi=dict(body='elastic',material='neo_hookean',
        domains=dict(solid_mesh='solid.msh',fluid_region=10,solid_region=20,fluid_interface=3,solid_interface=13,
                     pressure_tags=[2],fluid_constraints=[],mesh_constraints=[constraint(1),constraint(2)],
                     solid_constraints=[constraint(11),constraint(12)]),
        young=100,poisson=.3,dt=.002,steps=20,pressure=0,output_interval=1,stabilization_tau=.05,
        inlet=dict(tag=1,ramp_time=.01,flow_rate=dict(profile='circle',axis=0,center=[0,0,0],radius=radius,
                                                   mean=.01,amplitude=.005,period=.04))),
        time=dict(scheme='generalized_alpha'),solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30))
    path=directory/'case.json';path.write_text(json.dumps(cfg,indent=2)+'\n')
    (directory/'geometry.json').write_text(json.dumps(dict(sectors=sectors,axial=axial,radial=radial,radius=radius,
        thickness=thickness,length=length,interface_area=2*sectors*radius*math.sin(math.pi/sectors)*length,
        fluid_volume=sectors*radius**2*math.sin(2*math.pi/sectors)*length/2),indent=2)+'\n')
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('build/fsi-tube'))
    p.add_argument('--sectors',type=int,default=12);p.add_argument('--axial',type=int,default=4);p.add_argument('--radial',type=int,default=2)
    a=p.parse_args();print(generate(a.output,a.sectors,a.axial,a.radial))
