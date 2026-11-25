"""Generate a synthetic curved, circular elastic tube with an oriented inlet and fixed RCR outlet."""
import argparse
import json
import math
from pathlib import Path
import sys
import tempfile

from generate_tube import generate as straight_tube, write_tet_mesh
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from study_rigid_tube import cross, determinant, read_mesh, sub


def normalize(v):
    if len(v)!=3 or not all(map(math.isfinite,v)) or max(map(abs,v))==0:
        raise ValueError('Expected a finite nonzero three-component direction')
    scale=max(map(abs,v))
    scaled=[x/scale for x in v]
    norm=math.hypot(*scaled)
    return tuple(x/norm for x in scaled)


def basis(direction):
    tangent=normalize(direction)
    reference=(0.,1.,0.) if abs(tangent[1])<.9 else (0.,0.,1.)
    binormal=normalize(cross(tangent,reference))
    return tangent,cross(binormal,tangent),binormal


def generate(directory,sectors=12,radial=2,axial=6,radius=.25,thickness=.05,length=1.5,
             bend_degrees=75.,direction=(1.,0.,0.),origin=(0.,0.,0.)):
    if not math.isfinite(bend_degrees) or abs(bend_degrees)>=360 or not math.isfinite(length) or length<=0:
        raise ValueError('Use a finite bend below one full turn and a positive arc length')
    theta=math.radians(bend_degrees)
    curvature=theta/length
    if abs(curvature)*(radius+thickness)>=1 or axial<2 or abs(theta)/axial>=math.pi:
        raise ValueError('Bend inverts the tube or an axial layer')
    if len(origin)!=3 or not all(map(math.isfinite,origin)):
        raise ValueError('Expected a finite inlet centre')
    axes=basis(direction)
    def transform(point):
        x,y,z=point
        angle=curvature*x
        cx=math.sin(angle)/curvature if curvature else x
        cy=2*math.sin(angle/2)**2/curvature if curvature else 0.
        local=(cx-y*math.sin(angle),cy+y*math.cos(angle),z)
        return tuple(origin[j]+sum(t*axis[j] for t,axis in zip(local,axes)) for j in range(3))
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    geometry=dict(sectors=sectors,radial=radial,axial=axial,lumen_radius=radius,wall_thickness=thickness,
                  arc_length=length,bend_degrees=bend_degrees,inlet_center=list(origin),inward_direction=axes[0],
                  outlet_center=transform((length,0.,0.)),outlet_direction=[math.cos(theta)*t+math.sin(theta)*n for t,n in zip(axes[0],axes[1])])
    interfaces=[]
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)
        cfg=json.loads(straight_tube(source,sectors,axial,radial,radius,thickness,length).read_text())
        for domain,tag,region in [('fluid',3,10),('solid',13,20)]:
            points,cells,faces=read_mesh(source/(domain+'.msh'))
            mapped={node:transform(point) for node,point in points.items()}
            volume=[determinant(mapped,t)/6 for t in cells]
            if min(volume)<=0 or len(set(mapped.values()))!=len(mapped):
                raise ValueError('Nonpositive or collapsed curved cell')
            ids=sorted(mapped)
            index={node:i for i,node in enumerate(ids)}
            write_tet_mesh(directory/(domain+'.msh'),[mapped[i] for i in ids],
                           [tuple(index[i] for i in tet) for tet in cells],
                           [(tag_id,tuple(index[i] for i in face)) for tag_id,face in faces],region)
            triangles=[tuple(sorted(mapped[i] for i in face)) for boundary,face in faces if boundary==tag]
            interfaces.append(set(triangles))
            geometry[domain+'_tetrahedra']=len(cells)
            geometry[domain+'_volume']=math.fsum(volume)
            if domain=='fluid':
                geometry['interface_area']=math.fsum(math.hypot(*cross(sub(b,a),sub(c,a)))/2 for a,b,c in triangles)
    if not interfaces[0] or interfaces[0]!=interfaces[1]:
        raise ValueError('The swept interface triangulations differ')
    f=cfg['fsi']
    f.update(young=100.,poisson=.3,dt=.01,steps=20,output_interval=5,pressure_face_history=True)
    f['inlet']['ramp_time']=.04
    q=f['inlet']['flow_rate']
    del q['axis']
    q.update(direction=list(axes[0]),center=list(origin),mean=.002,amplitude=.003,period=.2)
    f['domains']['rcr_outlet']=dict(tag=2,proximal_resistance=3.,distal_resistance=8.,compliance=.025,distal_pressure=0.)
    f['domains']['wall_supports']=[dict(tag=14,stiffness=20.,damping=.5)]
    path=directory/'case.json'
    path.write_text(json.dumps(cfg,indent=2)+'\n')
    (directory/'geometry.json').write_text(json.dumps(geometry,indent=2,allow_nan=False)+'\n')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sectors',type=int,default=12)
    parser.add_argument('--radial',type=int,default=2)
    parser.add_argument('--axial',type=int,default=6)
    parser.add_argument('--radius',type=float,default=.25)
    parser.add_argument('--thickness',type=float,default=.05)
    parser.add_argument('--length',type=float,default=1.5)
    parser.add_argument('--bend-degrees',type=float,default=75.)
    parser.add_argument('--direction',type=float,nargs=3,default=(1.,0.,0.))
    parser.add_argument('--origin',type=float,nargs=3,default=(0.,0.,0.))
    args=parser.parse_args()
    print(generate(args.output,args.sectors,args.radial,args.axial,args.radius,args.thickness,args.length,
                   args.bend_degrees,args.direction,args.origin))
