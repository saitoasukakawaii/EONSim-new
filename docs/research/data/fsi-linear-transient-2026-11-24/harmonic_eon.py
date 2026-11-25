"""Measure complex section compliance after startup from two complete cycles of a nonlinear 3D solve."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np

PARENT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PARENT/'fsi-pressure-faces-2026-11-24'),str(PARENT/'fsi-smooth-load-2026-11-24')]
from audit import SurfaceAudit
from audit_reflection import ring_geometry


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solve(executable, env, directory, label, cfg, extra, expected_steps):
    (directory/(label+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
    logfile=directory/(label+'.log')
    with logfile.open('w') as stream:
        subprocess.run([executable,'-case',label+'.json',*extra],cwd=directory,env=env,
                       stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=18000)
    log=logfile.read_text()
    history=re.findall(r'^fsi_step=(\d+) .*? residual=([\deE.+-]+) ',log,re.M)
    if [int(a) for a,_ in history]!=list(expected_steps) or log.count('status=success')!=1:
        raise ValueError('Unexpected accepted step history in '+label)
    return max(float(b) for _,b in history)


def phasor(times, values, frequency):
    phase=np.exp(-2j*np.pi*frequency*np.array(times))
    return 2*np.tensordot(phase,np.asarray(values),axes=(0,0))/len(times)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for s in ('work','case','reference-scripts','executable','libs','reference'):
        p.add_argument('--'+s,type=Path,required=True)
    p.add_argument('--frequency',type=float,required=True)
    p.add_argument('--steps-per-cycle',type=int,default=64)
    p.add_argument('--samples-per-cycle',type=int,default=16)
    p.add_argument('--cycles',type=int,default=12)
    p.add_argument('--pressure',type=float,default=.0002)
    p.add_argument('--support',type=float,nargs=2,default=(0.,0.))
    p.add_argument('--stabilization-time-scale',type=float,help='Fix the time in the cellwise PSPG coefficient, in seconds')
    p.add_argument('--discard-snapshots',action='store_true',help='Remove only the temporary VTUs from this freshly created run after writing their hashes and observations')
    args=p.parse_args()
    n,cycles,samples=args.steps_per_cycle,args.cycles,args.samples_per_cycle
    if samples<8 or n<samples or n%samples or cycles<3 or not np.isfinite([args.frequency,args.pressure,*args.support]).all() or min(args.frequency,args.pressure)<=0 or min(args.support)<0:
        p.error('Require multiple full cycles with equally spaced endpoint samples')
    if args.stabilization_time_scale is not None and not (np.isfinite(args.stabilization_time_scale) and args.stabilization_time_scale>0):
        p.error('The stabilization time must be finite and positive')
    work=args.work.resolve()
    work.mkdir(parents=True,exist_ok=False)
    sys.path.append(str(args.reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    from study_rigid_tube import read_mesh
    mesh=[read_mesh(args.case/name) for name in ('fluid.msh','solid.msh')]
    for name in ('fluid.msh','solid.msh'):shutil.copyfile(args.case/name,work/name)
    nodes,_,faces=mesh[1]
    ring_nodes={i for tag,tri in faces if tag==13 for i in tri}
    locations=sorted({nodes[i][0] for i in ring_nodes})
    sectors=(sum(nodes[i][0]==locations[0] for i in ring_nodes)-1)*4
    sections,rings=ring_geometry(mesh[1],(sectors,0,0,len(locations)-1))
    surface=SurfaceAudit(mesh[0])
    reference=json.loads(args.reference.read_text())
    expected=next(r for r in reference['frequencies'] if r['frequency_hz']==args.frequency)
    if list(args.support)!=[reference['parameters']['support_stiffness'],reference['parameters']['support_damping']]:
        raise ValueError('Mismatched outer-wall support controls')
    pos=[]
    for x in sections:
        ix=np.flatnonzero(np.abs(np.array(reference['sections'])-x)<1e-11)
        if len(ix)!=1:raise ValueError('Reference lacks an exact station')
        pos.append(ix[0])
    href=np.array([complex(*expected['area_strain_per_pa'][j]) for j in pos])
    flux_ref=complex(*expected['inward_flux_per_radian_per_pa'])*(np.pi/2 if reference['full_length'] else np.pi)
    period=1/args.frequency
    warm=(cycles-2)*n;total=cycles*n
    cfg=json.loads((args.case/'case.json').read_text())
    cfg['output']='tube.vtu'
    cfg['fsi'].update(dt=period/n,steps=total,output_interval=total,checkpoint_interval=total,
                      pressure=0.,pressure_face_history=True,pressure_time=dict(amplitude=args.pressure,period=period,ramp_time=period))
    if args.stabilization_time_scale is not None:cfg['fsi']['stabilization_time_scale']=args.stabilization_time_scale
    if any(args.support):cfg['fsi']['domains']['wall_supports']=[dict(tag=14,stiffness=args.support[0],damping=args.support[1])]
    cfg['solver']['absolute_tolerance']=1e-13*args.pressure/.02
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
             OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp')
    exe=str(args.executable.resolve())
    checkpoint=work/'warm-state'
    residuals=[solve(exe,env,work,'warm',cfg,['-checkpoint',str(checkpoint),'-stop_after',str(warm)],range(1,warm+1))]
    cfg['fsi']['output_interval']=n//samples
    residuals.append(solve(exe,env,work,'measure',cfg,['-restart',str(checkpoint)],range(warm+1,total+1)))
    stem='tube_restart'+str(warm)
    with (work/(stem+'_pressure_faces.csv')).open() as f:
        faces={(int(r['step']),int(r['tag'])):{k:float(x) for k,x in r.items()} for r in csv.DictReader(f)}
    if len(faces)!=4*n:raise ValueError('Missing pressure/flux histories in the final two cycles')
    tags=(1,2)
    pvd=ET.parse(work/(stem+'_solid.pvd')).findall('.//DataSet')
    if len(pvd)!=2*samples:raise ValueError('Incomplete VTU time series')
    strain=[];flow=[];press=[];times=[];source_hashes={};flux_errors=[];stage_pressure_errors=[]
    for j,dataset in enumerate(pvd,1):
        step=warm+j*n//samples
        t=step*period/n
        path=f'{stem}_step{step}'
        if dataset.get('file')!=path+'_solid.vtu' or abs(float(dataset.get('timestep'))-t)>1e-9*max(1,t):
            raise ValueError('Snapshot path or time differs from the prescribed sampling lattice')
        original=[recovered_state(work,path+suffix,separate,bool(i),1) for i,(separate,suffix) in enumerate(zip(mesh,('','_solid')))]
        for suffix in ('','_solid'):
            name=path+suffix+'.vtu';source_hashes[name]=digest(work/name)
        strain.append([float(np.sum(gradient*[original[1][i].displacement[1:] for i in ids])) for ids,gradient in rings])
        prescribed=args.pressure*math.sin(2*math.pi*args.frequency*t)
        seen=surface.observe(surface.array(original[0]),prescribed)
        flow.append(-sum(seen[tag]['outward_flow'] for tag in tags))
        for tag in tags:
            row=faces[step,tag]
            if abs(row['time']-t)>1e-11*max(1,t) or abs(row['endpoint_prescribed_pressure']-prescribed)>1e-11*args.pressure:
                raise ValueError('Wrong endpoint pressure at a cap')
            flux_errors.append(abs(row['endpoint_outward_flow']-seen[tag]['outward_flow']))
            stage_p=args.pressure*math.sin(2*math.pi*args.frequency*row['evaluation_time'])
            stage_pressure_errors.append(abs(stage_p-row['stage_prescribed_pressure']))
        times.append(t);press.append(prescribed)
    if max(flux_errors)>1e-12*max(1.,max(map(abs,flow))) or max(stage_pressure_errors)>1e-10*args.pressure:
        raise ValueError(f'Inconsistent field or applied stage history: {max(flux_errors)}, {max(stage_pressure_errors)}')
    last=slice(samples,None)
    input_mode=phasor(times[last],press[last],args.frequency)
    compliance=phasor(times[last],strain[last],args.frequency)/input_mode
    admittance=phasor(times[last],flow[last],args.frequency)/input_mode
    static=reference['static_area_strain_per_pa']
    last_change=float(np.max(abs(np.array(strain[last])-strain[:samples]))/(args.pressure*static))
    leaf=lambda c:[float(c.real),float(c.imag)]
    result=dict(frequency_hz=args.frequency,cycles=cycles,steps_per_cycle=n,stations=sections.tolist(),samples_per_cycle=samples,
                pressure_amplitude=args.pressure,support=args.support,mesh_sha256=[digest(work/name) for name in ('fluid.msh','solid.msh')],
                executable_sha256=digest(args.executable),reference_sha256=digest(args.reference),accepted_residuals=residuals,
                snapshot_sha256=source_hashes,max_cap_flux_reconstruction_error=max(flux_errors),
                max_applied_stage_pressure_error=max(stage_pressure_errors),max_previous_cycle_area_change_over_static=last_change,
                previous_cycle_flux_change_over_peak=max(abs(x-y) for x,y in zip(flow[last],flow))/max(map(abs,flow[last])),
                area_strain_per_pa=[leaf(z) for z in compliance],reference_area_strain_per_pa=[leaf(z) for z in href],
                max_section_complex_error_over_static=float(np.max(abs(compliance-href))/static),
                section_phase_error_degrees=np.angle(compliance/href,deg=True).tolist(),
                influx_admittance=leaf(admittance),reference_influx_admittance=leaf(flux_ref),
                relative_complex_influx_error=float(abs(admittance-flux_ref)/abs(flux_ref)),
                samples=[dict(time=t,pressure=p,influx=q,strains=a) for t,p,q,a in zip(times,press,flow,strain)])
    if args.stabilization_time_scale is not None:result['stabilization_time_scale']=args.stabilization_time_scale
    (work/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    if args.discard_snapshots:
        for record in pvd:
            solid=record.get('file')
            root=solid.removesuffix('_solid.vtu')
            for suffix in ('.vtu','_boundary.vtu','_solid.vtu','_solid_boundary.vtu'):
                (work/(root+suffix)).unlink()
    print(args.frequency,cycles,n,last_change,result['max_section_complex_error_over_static'],flush=True)


if __name__=='__main__':main()
