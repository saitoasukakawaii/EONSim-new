"""Check dimensional similarity separately from a small-amplitude tube with different physical parameters."""
import argparse
import csv
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
from axisymmetric import MeridianTube, StageBalance, TubeParameters
from harmonic_eon import SurfaceAudit, digest, solve
from audit_reflection import measured_ring_strains
from reference import integrate


def problem(name):
    base=TubeParameters()
    if name=='artificial':return base,1.,.02
    if name=='similar':
        length,pressure=.01,4000.
        time=length*math.sqrt(1060./pressure)
        return TubeParameters(radius=length,outer_radius=1.2*length,length=2*length,
                              fluid_density=1060.,solid_density=1060.,viscosity=pressure*time,
                              young=100*pressure,poisson=.3),time,.02*pressure
    if name=='arterial':
        return TubeParameters(radius=.01,outer_radius=.012,length=.12,fluid_density=1060.,solid_density=1100.,
                              viscosity=.004,young=4e5,poisson=.45),1.,80.
    raise ValueError('Unknown physical problem')


def write_mesh(source,target,material):
    lines=source.read_text().splitlines()
    start=lines.index('$Nodes')+2
    end=lines.index('$EndNodes')
    if int(lines[start-1])!=end-start:raise ValueError('Expected Gmsh 2.2 nodes')
    for i in range(start,end):
        node,x,y,z=lines[i].split()
        coords=(float(x)*material.length/2,float(y)*material.radius,float(z)*material.radius)
        lines[i]=node+' '+' '.join(format(v,'.17g') for v in coords)
    target.write_text('\n'.join(lines)+'\n')


def reference(args):
    m,t,p=problem(args.problem)
    if t!=1.:raise ValueError('Use the exactly similar artificial meridian for the short-duration twin')
    result=dict(parameters=asdict(m),duration=t,pressure=p,mesh=args.mesh,corner_levels=args.corner_levels,runs=[])
    tube=MeridianTube(*args.mesh,5,m,args.corner_levels,False,97)
    result.update(unknowns=tube.size,sections=tube.positions,static=tube.hydrostatic_check())
    for n in args.steps:
        observer=StageBalance(tube,p)
        measurement=integrate(tube,n,p,observe=observer,stage_solver='condensed-pair')
        measurement.update(observer.report())
        result['runs'].append(measurement)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(tube.size,result['runs'][-1]['samples'][-1]['section_area_strain'][::48],flush=True)


def eon(args):
    from study_hydrostatic_fsi import recovered_state
    from study_rigid_tube import read_mesh
    m,duration,peak=problem(args.problem)
    n=args.steps
    if n<8 or n%8:raise ValueError('Need eight equally spaced observations')
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    for name in ('fluid.msh','solid.msh'):
        write_mesh(args.case/name,work/name,m)
    cfg=json.loads((args.case/'case.json').read_text())
    f=cfg['fsi']
    f.update(dt=duration/n,steps=n,output_interval=n//8,pressure=peak,pressure_face_history=True,
             pressure_time=dict(amplitude=0.,period=duration,ramp_time=duration),density=m.fluid_density,
             solid_density=m.solid_density,viscosity=m.viscosity,young=m.young,poisson=m.poisson,stabilization_model=args.model)
    # Momentum, continuity and harmonic mesh rows carry different SI units. Use a tight absolute
    # tolerance scaled by the smallest of their dimensional row transformations for the similar pair.
    length=m.radius;stress=peak/.02
    atol=1e-13*min(1.,stress*length**2,length**3/duration,length**2)
    if args.problem=='arterial':
        # The nonsimilar case has its own dimensional force scale. Report the measured numerical floor.
        atol=args.absolute_tolerance
    cfg['solver'].update(absolute_tolerance=atol,relative_tolerance=1e-11)
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    residual=solve(str(args.executable.resolve()),env,work,'case',cfg,[],range(1,n+1))
    meshes=[read_mesh(work/name) for name in ('fluid.msh','solid.msh')]
    audit=SurfaceAudit(meshes[0])
    with (work/'tube_pressure_faces.csv').open() as src:
        faces={(int(r['step']),int(r['tag'])):{k:float(v) for k,v in r.items()} for r in csv.DictReader(src)}
    if set(faces)!={(i,j) for i in range(1,n+1) for j in (1,2)}:raise ValueError('Missing pressure step or tag')
    def p(t):
        phase=min(1.,t/duration)
        return peak*phase**3*(10+phase*(-15+6*phase))
    load_error=0.
    for (i,_),r in faces.items():
        stage=(i-1+(1 if i==1 else 2/3))*duration/n
        if abs(r['time']-i*duration/n)>1e-12*duration or abs(r['evaluation_time']-stage)>1e-12*duration:
            raise ValueError('Incorrect load time')
        load_error=max(load_error,abs(r['stage_prescribed_pressure']-p(stage)),abs(r['endpoint_prescribed_pressure']-p(i*duration/n)))
    if load_error>2e-12*peak:raise ValueError('Applied pressure differs from analytic load')
    initial=math.fsum(abs(np.linalg.det(np.array([meshes[0][0][j] for j in tet])[1:]-meshes[0][0][tet[0]]))/6 for tet in meshes[0][1])
    rows=[]
    for step in range(n//8,n+1,n//8):
        stem=f'tube_step{step}'
        state=[recovered_state(work,stem+s,mesh,bool(j),1) for j,(s,mesh) in enumerate(zip(('','_solid'),meshes))]
        positions,strain=measured_ring_strains(meshes[1],state[1])
        measured=audit.array(state[0])
        ports=audit.observe(measured,p(duration*step/n),m.viscosity)
        outward=[ports[tag]['outward_flow'] for tag in (1,2)]
        discrepancy=max(abs(v-faces[step,k]['endpoint_outward_flow']) for k,v in zip((1,2),outward))
        if discrepancy>1e-11*max(1e-12,*map(abs,outward)):raise ValueError('Independent cap flux differs from actual field')
        rows.append(dict(phase=step/n,time=duration*step/n,strains=strain,outward_flow=outward,
                         relative_volume_change=audit.volume(measured)/initial-1,cap_flux_check=discrepancy,
                         vtu_sha256={s:digest(work/(stem+s+'.vtu')) for s in ('','_solid')}))
    result=dict(problem=args.problem,model=args.model,steps=n,parameters=asdict(m),pressure=peak,duration=duration,
                static_area_strain=m.lame_area_strain(peak),xs=positions,log_residual=residual,load_error=load_error,
                absolute_tolerance=atol,executable_sha256=digest(args.executable),input_sha256={k:digest(work/k) for k in ('case.json','fluid.msh','solid.msh')},
                history_sha256=digest(work/'tube_pressure_faces.csv'),samples=rows)
    (work/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(args.problem,args.model,n,100*rows[-1]['strains'][0],100*result['static_area_strain'],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    jobs=parser.add_subparsers(dest='job',required=True)
    mer=jobs.add_parser('meridian')
    mer.add_argument('--problem',choices=('artificial','arterial'),required=True)
    mer.add_argument('--mesh',type=int,nargs=3,required=True);mer.add_argument('--corner-levels',type=int,default=4)
    mer.add_argument('--steps',type=int,nargs='+',default=[128,256]);mer.add_argument('--output',type=Path,required=True)
    actual=jobs.add_parser('eon')
    actual.add_argument('--problem',choices=('artificial','similar','arterial'),required=True)
    actual.add_argument('--model',choices=('volume','regular_tet'),default='volume')
    actual.add_argument('--steps',type=int,required=True)
    actual.add_argument('--absolute-tolerance',type=float,default=1e-14,help='Dimensional SNES tolerance for the independent arterial-parameter case')
    for k in ('case','work','executable','libs','reference-scripts'):actual.add_argument('--'+k,type=Path,required=True)
    args=parser.parse_args()
    if args.job=='meridian':reference(args)
    else:
        sys.path.append(str(args.reference_scripts.resolve()))
        eon(args)


if __name__=='__main__':main()
