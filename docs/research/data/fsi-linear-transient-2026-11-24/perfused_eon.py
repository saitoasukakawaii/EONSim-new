"""Measure a periodic inlet, fixed RCR, wall expansion and pressure in an idealized perfused SI tube."""
import argparse
import csv
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from harmonic_eon import SurfaceAudit, digest, phasor, solve
from perfused_tube import AMPLITUDE, C, RD, RP, pair
from scaled_tube import problem, write_mesh
from audit_reflection import measured_ring_strains


def history(path):
    with path.open() as stream:
        return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]


def periodic_modes(samples,hz,peak,pscale,area_scale):
    half=len(samples)//2
    cycles=[samples[:half],samples[half:]]
    obs=[]
    for cycle in cycles:
        times=[s['time'] for s in cycle]
        rawin=phasor(times,[s['full_inlet'] for s in cycle],hz)
        if abs(rawin+1j*peak)/peak>1e-6:raise ValueError('Inlet Fourier mode differs from imposed sine')
        rotation=peak/rawin
        entry={}
        for key in ('full_inlet','full_outlet','full_wall_flux','inlet_mean_pressure','outlet_mean_pressure','circuit_pressure','capacitor_pressure','area_strain'):
            entry[key]=rotation*phasor(times,[s[key] for s in cycle],hz)
        obs.append(entry)
    # Use prescribed full inlet and terminal pressure as references, including where a local mode vanishes.
    change=dict(flow_over_inlet=float(abs(obs[1]['full_outlet']-obs[0]['full_outlet'])/peak),
                area_over_static=float(max(abs(obs[1]['area_strain']-obs[0]['area_strain']))/area_scale),
                inlet_pressure_over_RQ=float(abs(obs[1]['inlet_mean_pressure']-obs[0]['inlet_mean_pressure'])/pscale))
    mode={k:([pair(i) for i in z] if k=='area_strain' else pair(z)) for k,z in obs[-1].items()}
    return mode,change


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('case','work','reference-scripts','executable','libs'):
        p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--hz',type=float,default=1.)
    p.add_argument('--steps-per-cycle',type=int,default=32)
    p.add_argument('--cycles',type=int,default=9)
    p.add_argument('--samples',type=int,default=8)
    p.add_argument('--model',choices=('volume','regular_tet'),default='volume')
    p.add_argument('--rigid',action='store_true')
    p.add_argument('--moving-outlet',action='store_true',help='Apply the terminal on a radially expanding fixed axial plane')
    p.add_argument('--amplitude',type=float,default=AMPLITUDE,help='Full-circle inlet peak in m³/s')
    p.add_argument('--mean',type=float,default=0.,help='Cycle-mean full-circle inlet flow in m³/s')
    args=p.parse_args()
    n, hz, peak = args.steps_per_cycle, args.hz, args.amplitude
    if not np.isfinite([hz,peak,args.mean]).all() or min(n,hz,peak)<=0 or args.cycles<4 or args.samples<8 or n%args.samples:
        p.error('Expected full cycles with at least eight evenly spaced samples')
    sys.path.append(str(args.reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    from study_rigid_tube import read_mesh

    work=args.work.resolve()
    work.mkdir(parents=True,exist_ok=False)
    material=problem('arterial')[0]
    for name in ('fluid.msh','solid.msh'):
        write_mesh(args.case/name,work/name,material)
    meshes=[read_mesh(work/name) for name in ('fluid.msh','solid.msh')]
    surface=SurfaceAudit(meshes[0],(1,2,3))
    cfg=json.loads((args.case/'case.json').read_text())
    period=1/hz
    total=args.cycles*n
    warm=total-2*n
    cfg['output']='tube.vtu'
    f=cfg['fsi']
    f.update(dt=period/n,steps=total,output_interval=total,checkpoint_interval=total,
             pressure=0.,pressure_face_history=True,young=material.young,poisson=material.poisson,
             viscosity=material.viscosity,density=material.fluid_density,solid_density=material.solid_density,
             stabilization_model=args.model)
    fraction=.25
    f['inlet']=dict(tag=1,ramp_time=period,flow_rate=dict(profile='circle',axis=0,center=[0,0,0],
                    radius=material.radius,mean=fraction*args.mean,amplitude=fraction*peak,period=period))
    f.pop('pressure_time',None)
    domains=f['domains']
    domains['pressure_tags']=[2]
    # Each symmetric quarter sees one fourth of the full-circle net flow at the same pressure.
    model=dict(tag=2,proximal_resistance=RP/fraction,distal_resistance=RD/fraction,
               compliance=C*fraction,distal_pressure=0.,initial_capacitor_pressure=0.)
    if args.moving_outlet:
        model['moving_plane_axis']=0
    domains['rcr_outlet']=model
    for constraints,tags in (('mesh_constraints',(1,2)),('solid_constraints',(11,12))):
        for bc in domains[constraints]:
            if bc['tag'] in tags:
                bc['components']=[0] if args.moving_outlet and bc['tag']==tags[-1] else [0,1,2]
    if args.rigid:
        domains['solid_constraints'].extend(dict(tag=t,components=[0,1,2]) for t in (13,14))
    cfg['solver'].update(absolute_tolerance=1e-14,relative_tolerance=1e-11)
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    executable=str(args.executable.resolve())
    checkpoint=work/'warm-state'
    norms=[solve(executable,env,work,'warm',cfg,['-checkpoint',str(checkpoint),'-stop_after',str(warm)],range(1,warm+1))]
    f['output_interval']=n//args.samples
    norms.append(solve(executable,env,work,'measure',cfg,['-restart',str(checkpoint)],range(warm+1,total+1)))
    stem='tube_restart'+str(warm)
    rows=history(work/(stem+'.csv'))
    faces=history(work/(stem+'_pressure_faces.csv'))
    steps=list(range(warm+1,total+1))
    if [r['step'] for r in rows]!=steps or [(r['step'],r['tag']) for r in faces]!=[(v,2) for v in steps]:
        raise ValueError('Incomplete accepted steps or outlet boundary observations')
    checks={'stage_rcr_flux_relative':0.,'face_pressure_relative':0.,'face_flux_relative':0.,
            'prescribed_inlet_relative':0.,'vtu_flux_relative':0.,'vtu_wall_flux_relative':0.,'vtu_mean_pressure_absolute':0.}
    pscale=peak*(RP+RD)
    for r,face in zip(rows,faces):
        time=r['step']*period/n
        if abs(time-r['time'])>3e-11*period or abs(face['time']-time)>3e-11*period:raise ValueError('Incorrect sampled time')
        for phase in ('stage','endpoint'):
            q=r[phase+'_rcr_flow']
            pc=r[phase+'_capacitor_pressure']
            pb=r[phase+'_rcr_pressure']
            checks['face_pressure_relative']=max(checks['face_pressure_relative'],
                abs(face[phase+'_prescribed_pressure']-pb)/pscale,abs(pb-pc-model['proximal_resistance']*q)/pscale)
            checks['face_flux_relative']=max(checks['face_flux_relative'],abs(face[phase+'_outward_flow']-q)/(fraction*peak))
        defect=model['compliance']*r['stage_capacitor_rate']-r['stage_rcr_flow']+r['stage_capacitor_pressure']/model['distal_resistance']
        checks['stage_rcr_flux_relative']=max(checks['stage_rcr_flux_relative'],abs(defect)/(fraction*peak))

    samples=[]
    pvd=ET.parse(work/(stem+'_solid.pvd')).findall('.//DataSet')
    if len(pvd)!=2*args.samples:raise ValueError('Incomplete sampled cycles')
    for j,dataset in enumerate(pvd,1):
        step=warm+j*n//args.samples
        t=step*period/n
        path=f'{stem}_step{step}'
        if dataset.get('file')!=path+'_solid.vtu' or abs(float(dataset.get('timestep'))-t)>3e-11*period:
            raise ValueError('Output time or physical file changed')
        state=[recovered_state(work,path+suffix,region,bool(k),1) for k,(region,suffix) in enumerate(zip(meshes,('','_solid')))]
        fields=surface.observe(surface.array(state[0]),0.,material.viscosity)
        r,face=rows[step-warm-1],faces[step-warm-1]
        positions,area=measured_ring_strains(meshes[1],state[1])
        qin=-fields[1]['outward_flow']/fraction
        qout=fields[2]['outward_flow']/fraction
        checks['prescribed_inlet_relative']=max(checks['prescribed_inlet_relative'],abs((qin-args.mean)/peak-math.sin(2*np.pi*hz*t)))
        checks['vtu_flux_relative']=max(checks['vtu_flux_relative'],abs(qout-r['endpoint_rcr_flow']/fraction)/peak,
                                        abs(qin-r['endpoint_inlet_flow']/fraction)/peak)
        checks['vtu_wall_flux_relative']=max(checks['vtu_wall_flux_relative'],
            abs(fields[3]['outward_flow']-r['endpoint_wall_flux'])/(fraction*peak))
        checks['vtu_mean_pressure_absolute']=max(checks['vtu_mean_pressure_absolute'],abs(fields[2]['mean_pressure']-face['endpoint_mean_pressure']))
        samples.append(dict(step=step,time=t,full_inlet=qin,full_outlet=qout,
                            full_wall_flux=r['endpoint_wall_flux']/fraction,full_volume=r['endpoint_volume']/fraction,
                            inlet_mean_pressure=fields[1]['mean_pressure'],outlet_mean_pressure=fields[2]['mean_pressure'],
                            circuit_pressure=r['endpoint_rcr_pressure'],capacitor_pressure=r['endpoint_capacitor_pressure'],area_strain=area,
                            file_sha256={suffix:digest(work/(path+suffix+'.vtu')) for suffix in ('','_solid')}))
    fixed_ends=(0,) if args.moving_outlet else (0,-1)
    if (max(checks.values())>2e-6 or max(abs(s['area_strain'][i]) for s in samples for i in fixed_ends)>1e-10):
        raise ValueError('Applied inlet, terminal equation, raw fields or clamped ends differ: '+str(checks))
    mode,change=periodic_modes(samples,hz,peak,pscale,material.lame_area_strain(pscale))
    result=dict(parameters=asdict(material),frequency_hz=hz,steps_per_cycle=n,cycles=args.cycles,samples_per_cycle=args.samples,
                rigid=args.rigid,outlet_tangential_motion=args.moving_outlet,model=args.model,full_amplitude=peak,full_mean=args.mean,full_rcr_si=[RP,RD,C],quarter_fraction=fraction,
                sections=positions,observations=samples,phasors=mode,checks=checks,last_cycle_change=change,
                periodic_pass=max(change.values())<1e-3,residuals=norms,executable_sha256=digest(args.executable),
                files={k:digest(work/k) for k in ('fluid.msh','solid.msh','warm.json','measure.json','warm.log','measure.log',stem+'.csv',stem+'_pressure_faces.csv')})
    (work/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(hz,n,args.model,args.rigid,change,mode['circuit_pressure'],flush=True)


if __name__=='__main__':
    main()
