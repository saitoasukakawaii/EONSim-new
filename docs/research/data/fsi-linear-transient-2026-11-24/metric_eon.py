"""Measure nonlinear EONSim regular-Tet4 stabilization against an independent, same-mesh linear DAE."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import sys

import numpy as np
from axisymmetric import TubeParameters
from harmonic_eon import SurfaceAudit, digest, ring_geometry, solve


def measured(args):
    ref=json.loads(args.reference.read_text())
    if ref['metric_basis']!='regular-simplex':raise ValueError('Independent regular-Tet4 metric required')
    n=args.steps
    source=args.coefficient_steps or n
    matches=[r for r in ref['runs'] if r['source_steps']==source and r['mode']=='native']
    if len(matches)!=1:raise ValueError('Missing independently assembled coefficient for the requested time')
    op=matches[0]
    if op['manufactured_error']>1e-8 or op['static']['max_residual']>1e-11:raise ValueError('Failed independent linear DAE')
    stages=sorted(op['time_study'],key=lambda x:x['steps'])
    if len(stages)<2:
        raise ValueError('Incomplete refined reference')
    for r in stages:
        if r['stage_residual_max']>1e-8:raise ValueError('Radau stage residual failed')
    for k,wanted in ref['input_sha256'].items():
        if wanted!=digest(args.case/k):raise ValueError('Input differs from the independently assembled mesh: '+k)
    work=args.work.resolve()
    work.mkdir(parents=True,exist_ok=False)
    for k in ('fluid.msh','solid.msh'):shutil.copyfile(args.case/k,work/k)
    sys.path.append(str(args.reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    from study_rigid_tube import read_mesh
    meshes=[read_mesh(work/k) for k in ('fluid.msh','solid.msh')]
    sm=meshes[1]
    wall_nodes={i for tag,tri in sm[2] if tag==13 for i in tri}
    positions=sorted({sm[0][i][0] for i in wall_nodes})
    nsectors=(sum(sm[0][i][0]==positions[0] for i in wall_nodes)-1)*4
    xs,rings=ring_geometry(sm,(nsectors,0,0,len(positions)-1))
    if list(xs)!=ref['sections']:raise ValueError('Different axial stations')
    cfg=json.loads((args.case/'case.json').read_text())
    f=cfg['fsi']
    f.update(dt=1/n,steps=n,output_interval=n//2,pressure=args.pressure,pressure_face_history=True,
             pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.),stabilization_model='regular_tet')
    if args.coefficient_steps is not None:f['stabilization_time_scale']=1/source
    cfg['solver']['absolute_tolerance']*=args.pressure/ref['pressure']
    peak=args.pressure
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    residual=solve(str(args.executable.resolve()),env,work,'case',cfg,[],range(1,n+1))
    if residual>max(cfg['solver']['absolute_tolerance']*1.5,peak*1e-9):raise ValueError('Unexpected nonlinear residual')
    with (work/'tube_pressure_faces.csv').open() as fobj:
        face={(int(r['step']),int(r['tag'])):{k:float(v) for k,v in r.items()} for r in csv.DictReader(fobj)}
    if set(face)!={(i,t) for i in range(1,n+1) for t in (1,2)}:raise ValueError('Missing port history')
    def pressure(t):return peak*t**3*(10+t*(-15+6*t))
    loading=0.
    for (i,_),row in face.items():
        te=(i-1+(1 if i==1 else 2/3))/n
        if abs(row['time']-i/n)>5e-13 or abs(row['evaluation_time']-te)>5e-13:raise ValueError('Incorrect physical time')
        loading=max(loading,abs(row['stage_prescribed_pressure']-pressure(te)),abs(row['endpoint_prescribed_pressure']-pressure(i/n)))
    if loading>1e-12*peak:raise ValueError('Incorrect applied pressure')
    surface=SurfaceAudit(meshes[0])
    static=TubeParameters().lame_area_strain(peak)
    samples=[]
    for base,previous in zip(stages[-1]['samples'],stages[-2]['samples']):
        t=base['time'];step=round(t*n)
        states=[recovered_state(work,f'tube_step{step}'+suffix,m,bool(k),1) for k,(suffix,m) in enumerate(zip(('','_solid'),meshes))]
        strains=np.array([np.sum(gradient*[states[1][i].displacement[1:] for i in ids]) for ids,gradient in rings])
        obs=surface.observe(surface.array(states[0]),pressure(t))
        flux=max(abs(obs[tag]['outward_flow']-face[step,tag]['endpoint_outward_flow']) for tag in (1,2))
        if flux>1e-10*peak:raise ValueError('Reconstructed cap flux differs from the actual field')
        truth=np.asarray(base['section_area_strain'])*peak/ref['pressure']
        old=np.asarray(previous['section_area_strain'])*peak/ref['pressure']
        delta=100*(strains-truth)/static
        if not np.isfinite(delta).all():raise ValueError('Invalid section difference')
        samples.append(dict(time=t,measured_strains=strains.tolist(),linear_strains=truth.tolist(),differences_pct_static=delta.tolist(),
                       max_abs_difference_pct_static=float(np.max(abs(delta))),radau_change_pct_static=float(100*max(abs(truth-old))/static),
                       cap_flow_reconstruction_error=flux,files_sha256={suffix:digest(work/f'tube_step{step}{suffix}.vtu') for suffix in ('','_solid')}))
    record=dict(mesh_sha256=ref['input_sha256'],executable_sha256=digest(args.executable),dae_sha256=digest(args.reference),
                case_sha256=digest(work/'case.json'),log_sha256=digest(work/'case.log'),pressure_history_sha256=digest(work/'tube_pressure_faces.csv'),
                model=cfg['fsi']['stabilization_model'],steps=n,coefficient_steps=source,fixed=args.coefficient_steps is not None,
                pressure_pa=peak,sections=list(xs),max_accepted_residual=residual,max_load_error=loading,samples=samples)
    (work/'result.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(n,source,peak,100*samples[-1]['measured_strains'][0],samples[-1]['max_abs_difference_pct_static'],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','case','executable','libs','reference','reference-scripts'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--steps',type=int,required=True)
    parser.add_argument('--coefficient-steps',type=int,help='Hold the temporal term at 1/N seconds during integration')
    parser.add_argument('--pressure',type=float,default=.02)
    a=parser.parse_args()
    if a.steps<2 or a.steps%2 or not math.isfinite(a.pressure) or a.pressure<=0:parser.error('Invalid pressure or steps')
    if a.coefficient_steps is not None and a.coefficient_steps<=0:parser.error('Positive coefficient resolution required')
    measured(a)


if __name__=='__main__':main()
