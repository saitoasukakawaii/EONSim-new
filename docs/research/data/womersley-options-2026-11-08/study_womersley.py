"""Checkpoint-based rigid-tube study; fresh evidence and explicit continuation.

Run solves in the locked PETSc environment. Postprocess accepted samples with
analyze_womersley.py (NumPy/SciPy/h5py). No qualification is inferred from solver
success alone. Warmup saves one state per cycle; subsequent cycles save phases.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

import study_rigid_tube as tube


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint(work):
    pointer=work/'checkpoint/current'
    if not pointer.exists():
        return None,0
    marker,generation=pointer.read_text().split()
    if marker!='EONSim_checkpoint_v3' or Path(generation).name!=generation:
        raise ValueError('Invalid checkpoint pointer')
    path=work/'checkpoint'/generation
    manifest=(path/'manifest').read_text().split()
    if len(manifest)!=5 or manifest[0]!=marker:
        raise ValueError('Incomplete checkpoint')
    return path,int(manifest[2])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--seed',type=int,nargs=3,default=(48,4,8),metavar=('SECTORS','RADIAL','AXIAL'))
    parser.add_argument('--level',type=int,default=0)
    parser.add_argument('--alpha',type=float,choices=(1.,2.),default=1.)
    parser.add_argument('--steps-per-cycle',type=int,default=100)
    parser.add_argument('--phases',type=int,default=100)
    parser.add_argument('--warmup',type=int,default=2)
    parser.add_argument('--cycles',type=int,default=5)
    parser.add_argument('--ranks',type=int,choices=(1,2,4),default=1)
    parser.add_argument('--mpiexec',default='mpiexec')
    parser.add_argument('--schur',action='store_true')
    parser.add_argument('--fluid-coo',action='store_true',help='Use the existing COO assembly; frozen into the study definition')
    parser.add_argument('--chord',action='store_true',help='With Schur only, build the first Newton Jacobian and reuse it within each step; requires independent field validation')
    parser.add_argument('--tau',type=float,help='Optional fixed tau, reported separately from default stabilization')
    parser.add_argument('--tau-time-scale',type=float,help='Optional effective integration time in tau only; not a fixed tau or default qualification')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--timeout',type=float,default=21600)
    args=parser.parse_args()
    sectors,radial,axial=args.seed
    if sectors<6 or radial<1 or axial<2 or not 0<=args.level<=3:
        parser.error('Invalid tube mesh')
    if args.warmup<1 or args.cycles<args.warmup+3 or args.phases<4 or args.steps_per_cycle%args.phases:
        parser.error('Need warmup >=1, at least three sampled cycles and a phase-aligned step count')
    if args.steps_per_cycle<args.phases or not 0<args.timeout<=86400:
        parser.error('Invalid step count/timeout')
    if args.tau is not None and (not math.isfinite(args.tau) or args.tau<=0):
        parser.error('Fixed tau must be finite and positive')
    if args.tau_time_scale is not None and (args.tau is not None or not math.isfinite(args.tau_time_scale) or args.tau_time_scale<=0):
        parser.error('Tau time scale must be finite and positive, and excludes fixed tau')
    if args.chord and not args.schur:
        parser.error('--chord requires the audited Schur path')
    solver_options=[]
    if args.fluid_coo:
        solver_options.append('-fluid_coo')
    if args.chord:
        # PETSc accepts -2 through the options database: rebuild once, then
        # reuse. -1 is an API-only policy and is rejected by SNESSetFromOptions.
        # EONSim creates a fresh SNES per accepted-step solve, so this does not
        # reuse a Jacobian across physical time steps.
        solver_options.extend(('-snes_lag_jacobian','-2'))
    work=args.work.resolve()
    period=2*math.pi/args.alpha**2
    definition=dict(schema=1,seed=list(args.seed),level=args.level,alpha=args.alpha,period=period,
                    radius=tube.RADIUS,length=tube.LENGTH,density=tube.DENSITY,viscosity=tube.VISCOSITY,
                    pressure_amplitude=tube.DROP,steps_per_cycle=args.steps_per_cycle,phases=args.phases,
                    warmup=args.warmup,ranks=args.ranks,schur=args.schur,tau=args.tau,
                    executable_sha256=sha(args.executable))
    if args.tau_time_scale is not None:
        definition['tau_time_scale']=args.tau_time_scale
    # Preserve existing default definitions byte-for-value. An execution-policy
    # change needs a new study with explicit checkpoint provenance, not an
    # implicit change to an old study during --resume.
    if solver_options:
        definition['solver_options']=solver_options
    definition_path=work/'definition.json'
    if args.resume:
        if json.loads(definition_path.read_text())!=definition:
            raise ValueError('Study definition changed during continuation')
        if sha(work/'eonsim')!=definition['executable_sha256']:
            raise ValueError('Frozen executable changed')
    else:
        work.mkdir(parents=True,exist_ok=True)
        if any(work.iterdir()):
            raise ValueError('Fresh study requires an empty work directory')
        shutil.copy2(args.executable,work/'eonsim')
        tube.generate(work/'base',sectors=sectors,radial=radial,axial=axial,radius=tube.RADIUS,length=tube.LENGTH)
        mesh=tube.read_mesh(work/'base/fluid.msh')
        for _ in range(args.level):
            mesh=tube.refine(*mesh)
        tube.write_mesh(work/'fluid.msh',*mesh)
        definition_path.write_text(json.dumps(definition,indent=2)+'\n')
        (work/'mesh-sha256.txt').write_text(sha(work/'fluid.msh')+'\n')
    if sha(work/'fluid.msh')!=(work/'mesh-sha256.txt').read_text().strip():
        raise ValueError('Study mesh changed')
    cfg=tube.case_config()
    cfg['mesh']='../fluid.msh'  # Each immutable case is stored in its attempt directory.
    cfg['fluid'].update(mode='transient',dt=period/args.steps_per_cycle,steps=args.cycles*args.steps_per_cycle)
    cfg['fluid']['boundaries'][1].update(value=0.,pressure_time=dict(amplitude=tube.DROP,period=period))
    if args.tau is not None:
        cfg['fluid']['stabilization_tau']=args.tau
    if args.tau_time_scale is not None:
        cfg['fluid']['stabilization_time_scale']=args.tau_time_scale
    cfg['time']=dict(scheme='bdf2')
    for target,cadence in ((args.warmup*args.steps_per_cycle,args.steps_per_cycle),
                           (args.cycles*args.steps_per_cycle,args.steps_per_cycle//args.phases)):
        source,step=checkpoint(work)
        if step>=target:
            continue
        if source is not None:
            manifest=(source/'manifest').read_text().split()
            if int(manifest[1])!=args.ranks or abs(float(manifest[3])-step*cfg['fluid']['dt'])>1e-10*max(1.,float(manifest[3])):
                raise ValueError('Checkpoint rank/time mismatch')
        attempt=len(list(work.glob('attempt-*')))+1
        directory=work/f'attempt-{attempt:03d}'
        directory.mkdir()
        cfg['output']='solution.vtu'
        cfg['fluid']['checkpoint_interval']=cadence
        case=directory/'case.json'
        case.write_text(json.dumps(cfg,indent=2)+'\n')
        command=[work/'eonsim','-case',case.relative_to(work)]
        if args.ranks>1:
            if not (work/'parts').exists():
                tube.run(command+['-prepare','parts','-parts',args.ranks],work,str(directory.relative_to(work)/'prepare.log'),args.timeout)
            command=[args.mpiexec,'-n',args.ranks]+command+['-partition','parts']
        command+=['-checkpoint','checkpoint','-stop_after',target]
        if source is not None:
            command+=['-restart',source.relative_to(work)]
        if args.schur:
            command+=['-schur_pc','-ksp_gmres_restart',120,'-ksp_max_it',2000]
        command+=solver_options
        (directory/'command.json').write_text(json.dumps(list(map(str,command)),indent=2)+'\n')
        tube.run(command,work,str(directory.relative_to(work)/'solve.log'),args.timeout)
        generation,step=checkpoint(work)
        if step!=target:
            raise ValueError('Successful solve did not reach requested accepted step')
        receipt=dict(step=step,checkpoint_generation=generation.name,output=str(directory.relative_to(work)/cfg['output']),
                     attempt=directory.name,definition=definition,qualification='not evaluated')
        (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        temporary=work/'receipt.tmp'
        temporary.write_text(json.dumps(receipt,indent=2)+'\n')
        temporary.replace(work/'receipt.json')
        print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    main()
