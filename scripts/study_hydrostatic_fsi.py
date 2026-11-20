"""Monolithic ALE/elastic equilibrium under a common pressure at both fluid ends."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import tempfile
from typing import NamedTuple
import xml.etree.ElementTree as ET

import study_lame_wall as wall
import study_rigid_tube as tube


LIMITS = dict(worst_area_relative_error=.03, last_step_area_change_relative=.001,
              final_max_fluid_speed=1e-6, pressure_rms_relative=.01,
              interface_velocity_difference=1e-9,interface_displacement_difference=1e-9)


def case_config(dt, duration, pressure, matched_rho=None):
    if not all(math.isfinite(v) and v>0 for v in (dt,duration,pressure)):
        raise ValueError('Pressure, duration and time step must be finite and positive')
    steps=round(duration/dt)
    if steps<2 or not math.isclose(steps*dt,duration,rel_tol=1e-13):
        raise ValueError('Use at least two equal steps covering the entire duration')
    def rollers(items):
        return [dict(tag=tag,components=[c]) for tag,c in items]
    domains=dict(solid_mesh='solid.msh',fluid_region=10,solid_region=20,fluid_interface=3,
                 solid_interface=13,pressure_tags=[1,2],fluid_constraints=rollers([(5,1),(6,2)]),
                 mesh_constraints=rollers([(1,0),(2,0),(5,1),(6,2)]),
                 solid_constraints=rollers([(11,0),(12,0),(15,1),(16,2)]))
    config=dict(mesh='fluid.msh',output='tube.vtu',time=dict(scheme='be'),
                fsi=dict(body='elastic',material='linear',domains=domains,young=wall.YOUNG,
                         poisson=wall.POISSON,density=1.,viscosity=1.,solid_density=1.,
                         dt=dt,steps=steps,output_interval=1,pressure=pressure,
                         pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.)),
                solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30))
    if matched_rho is not None:
        if not 0<=matched_rho<=1:
            raise ValueError('Generalized-alpha spectral radius must be in [0,1]')
        config['time']=dict(scheme='generalized_alpha',rho_infinity=matched_rho)
        del config['fsi']['pressure_time']
    return config


def solve(directory, executable, mpiexec, ranks, sectors, layers, radial, axial, dt, duration,
          pressure, matched_rho=None):
    if sectors<8 or sectors%4:
        raise ValueError('Full-circle sector count must be divisible by four and at least eight')
    cfg=case_config(dt,duration,pressure,matched_rho)
    directory.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        tube.generate(tmp,sectors=sectors,radial=radial,axial=axial,radius=wall.INNER,
                      thickness=wall.OUTER-wall.INNER,length=wall.LENGTH,wall_layers=layers)
        wall.quarter_mesh(Path(tmp)/'solid.msh',directory/'solid.msh',(15,16),20)
        wall.quarter_mesh(Path(tmp)/'fluid.msh',directory/'fluid.msh',(5,6),10)
    (directory/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (directory/'geometry.json').write_text(json.dumps(dict(sectors=sectors,wall_layers=layers,
                            radial=radial,axial=axial),indent=2)+'\n')
    command=[executable.resolve(),'-case','case.json']
    if ranks>1:
        tube.run([*command,'-prepare','parts','-parts',ranks],directory,'prepare.log')
        command=[mpiexec,'-n',ranks,*command,'-partition','parts']
    tube.run(command,directory,'solve.log')


class PointState(NamedTuple):
    displacement: tuple
    velocity: tuple
    pressure: float


def recovered_state(directory, stem, mesh, solid, ranks):
    nodes,cells,_=mesh
    # The coupled writer contains all local points, including points belonging
    # only to the other region. Match only points referenced by active cells.
    def key(p): return tuple(round(x,11) for x in p)
    reference={key(p):n for n,p in nodes.items()}
    if len(reference)!=len(nodes):
        raise ValueError('Reference coordinates are ambiguous at the matching precision')
    global_cells=Counter()
    state={}
    for rank in range(ranks):
        suffix='' if ranks==1 else f'_rank{rank}'
        piece=ET.parse(directory/(stem+suffix+'.vtu')).find('.//Piece')
        values={v.get('Name'):list(map(float,v.text.split())) for v in piece.findall('PointData/DataArray')}
        positions=list(map(float,piece.find('Points/DataArray').text.split()))
        displacements=values['displacement' if solid else 'mesh_displacement']
        velocity=values['velocity']
        npoints=int(piece.get('NumberOfPoints'))
        if (any(len(v)!=3*npoints for v in (positions,displacements,velocity))
                or (not solid and len(values['pressure'])!=npoints)):
            raise ValueError('Incomplete coupled point fields')
        connectivity=list(map(int,piece.find('Cells/DataArray[@Name="connectivity"]').text.split()))
        types=list(map(int,piece.find('Cells/DataArray[@Name="types"]').text.split()))
        if (not all(t==10 for t in types) or len(connectivity)!=4*len(types)
                or any(i<0 or i>=npoints for i in connectivity)):
            raise ValueError('Expected Tet4 cells in each coupled field')
        mapping={}
        for i in set(connectivity):
            d=tuple(displacements[3*i:3*i+3])
            u=tuple(velocity[3*i:3*i+3])
            p=0. if solid else values['pressure'][i]
            ref=tuple(positions[3*i+j]-d[j] for j in range(3))
            if not all(map(math.isfinite,(*ref,*d,*u,p))) or key(ref) not in reference:
                raise ValueError('Coupled fields do not match a finite reference point')
            n=reference[key(ref)]
            row=PointState(d,u,p)
            if n in state:
                other=state[n]
                if max(abs(a-b) for a,b in zip((*d,*u,p),(*other.displacement,*other.velocity,other.pressure)))>1e-10:
                    raise ValueError('Inconsistent shared coupled node')
            state[n]=row
            mapping[i]=n
        global_cells.update(tuple(sorted(mapping[j] for j in connectivity[i:i+4])) for i in range(0,len(connectivity),4))
    if global_cells!=Counter(tuple(sorted(t)) for t in cells) or state.keys()!=nodes.keys():
        raise ValueError('Active coupled cells do not reproduce their source region')
    return state


def analyze(directory, ranks=1):
    cfg=json.loads((directory/'case.json').read_text())
    f=cfg['fsi']
    n,dt,pressure=f['steps'],f['dt'],f['pressure']
    if cfg!=case_config(dt,n*dt,pressure,cfg['time'].get('rho_infinity')):
        raise ValueError('Unexpected hydrostatic FSI configuration')
    if (directory/'solve.log').read_text().splitlines()[-1:]!=['status=success']:
        raise ValueError('Coupled solve did not finish successfully')
    g=json.loads((directory/'geometry.json').read_text())
    fm,sm=(tube.read_mesh(directory/name) for name in ('fluid.msh','solid.msh'))
    s,m,r,k=(g[name] for name in ('sectors','wall_layers','radial','axial'))
    if (s<8 or s%4 or m<1 or r<1 or k<2
            or len(fm[1])!=3*(s//4)*(2*r-1)*k or len(sm[1])!=6*(s//4)*m*k):
        raise ValueError('Inconsistent coupled mesh resolution')
    with (directory/'tube.csv').open() as file:
        history=[{key:float(value) for key,value in row.items()} for row in csv.DictReader(file)]
    if (len(history)!=n or any(row['step']!=i or not math.isclose(row['time'],i*dt,rel_tol=2e-13)
         or not all(map(math.isfinite,row.values())) for i,row in enumerate(history,1))):
        raise ValueError('Incomplete, nonfinite or mistimed FSI history')
    if not math.isclose(history[-1]['applied_pressure'],pressure,rel_tol=1e-12):
        raise ValueError('The endpoint must be on the target pressure plateau')
    jac=min(row[key] for row in history for key in ('stage_min_fluid_j','stage_min_solid_j',
                                                   'endpoint_min_fluid_j','endpoint_min_solid_j'))
    if jac<=0:
        raise ValueError('Nonpositive geometry in the coupled history')
    exact=2*wall.lame(wall.INNER,pressure)[0]/wall.INNER
    fluid=recovered_state(directory,f'tube_step{n}',fm,False,ranks)
    solid=recovered_state(directory,f'tube_step{n}_solid',sm,True,ranks)
    prior=recovered_state(directory,f'tube_step{n-1}_solid',sm,True,ranks)
    def interface(mesh,tag):
        nodes,_,faces=mesh
        triangles=[face for t,face in faces if t==tag]
        return ({nodes[n]:n for face in triangles for n in face},
                Counter(tuple(sorted(nodes[n] for n in face)) for face in triangles))
    (fi,fluid_faces),(si,solid_faces)=interface(fm,3),interface(sm,13)
    if (fi.keys()!=si.keys() or fluid_faces!=solid_faces or len(fi)!=(s//4+1)*(k+1)
            or len(fluid_faces)!=2*(s//4)*k):
        raise ValueError('Reference interfaces differ')
    jump_u=max(abs(a-b) for x in fi for a,b in zip(fluid[fi[x]].velocity,solid[si[x]].velocity))
    jump_d=max(abs(a-b) for x in fi for a,b in zip(fluid[fi[x]].displacement,solid[si[x]].displacement))
    sections=[]
    disps=[{node:v.displacement for node,v in state.items()} for state in (prior,solid)]
    for x in sorted({p[0] for p in si}):
        ring=[node for p,node in si.items() if p[0]==x]
        if len(ring)!=s//4+1:
            raise ValueError('Incomplete coupled bore ring')
        prev,end=(wall.bore_section(sm[0],d,ring) for d in disps)
        sections.append(dict(x=x,previous_linear_area_strain=prev['linear_area_strain'],**end))
    current={i:tuple(a+b for a,b in zip(p,fluid[i].displacement)) for i,p in fm[0].items()}
    error2=volume=0.
    for tet in fm[1]:
        v=tube.determinant(current,tet)/6
        if v<=0: raise ValueError('Nonpositive final fluid tetrahedron')
        err=[fluid[n].pressure-pressure for n in tet]
        error2+=v*(sum(err)**2+sum(x*x for x in err))/20
        volume+=v
    metrics=dict(worst_area_relative_error=max(abs(row['linear_area_strain']/exact-1) for row in sections),
                 last_step_area_change_relative=max(abs(row['linear_area_strain']-row['previous_linear_area_strain']) for row in sections)/exact,
                 final_max_fluid_speed=max(math.hypot(*v.velocity) for v in fluid.values()),
                 pressure_rms_relative=math.sqrt(error2/volume)/pressure,
                 interface_velocity_difference=jump_u,interface_displacement_difference=jump_d)
    return dict(**g,scheme=cfg['time']['scheme'],ranks=ranks,steps=n,dt=dt,time=n*dt,pressure=pressure,
                fluid_tetrahedra=len(fm[1]),solid_tetrahedra=len(sm[1]),min_jacobian_ratio=jac,
                exact_linear_area_strain=exact,sections=sections,**metrics,
                passed=all(value<LIMITS[name] for name,value in metrics.items()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--executable',type=Path)
    p.add_argument('--mpiexec',default='mpiexec')
    p.add_argument('--ranks',type=int,default=1)
    p.add_argument('--mesh',type=int,nargs=4,metavar=('FULL_SECTORS','WALL_LAYERS','FLUID_RINGS','AXIAL'),default=(48,4,4,6))
    p.add_argument('--dt',type=float,default=.5)
    p.add_argument('--duration',type=float,default=8.)
    p.add_argument('--pressure',type=float,default=wall.PRESSURE)
    p.add_argument('--matched-svfsi-rho',type=float,help='Apply constant pressure and use generalized-alpha with this spectral radius')
    p.add_argument('--analyze-only',action='store_true')
    p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.ranks<1 or (not a.analyze_only and a.executable is None):
        p.error('Supply a positive rank count and a solver for a new run')
    if not a.analyze_only:
        solve(a.work,a.executable,a.mpiexec,a.ranks,*a.mesh,a.dt,a.duration,a.pressure,a.matched_svfsi_rho)
    result=analyze(a.work,a.ranks)
    print(json.dumps(result,indent=2,allow_nan=False))
    if a.check and not result['passed']:
        raise SystemExit('Missed a hydrostatic coupled criterion')


if __name__=='__main__':
    main()
