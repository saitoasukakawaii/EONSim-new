"""Predict the steady daughter split from a separate differential-pressure Stokes experiment."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests'),str(ROOT/'cases/fsi')]
from generate_branched import generate
from study_rigid_tube import cross, fields, read_mesh, run, sub
from verify_fsi_inlet import Runner, check_rcr_history


def cap_flows(directory, ranks=1):
    nodes,_,faces=read_mesh(directory/'fluid.msh')
    state=fields(directory,ranks)
    if state.keys()!=nodes.keys():
        raise ValueError('Incomplete Stokes velocity field')
    normal={1:(-1,0,0),2:(0,1,0),3:(0,-1,0)}
    flows={tag:[] for tag in normal}
    areas={tag:[] for tag in normal}
    for tag,face in faces:
        if tag not in normal: continue
        a,b,c=(nodes[i] for i in face)
        area_vector=cross(sub(b,a),sub(c,a))
        area=abs(sum(v*n for v,n in zip(area_vector,normal[tag])))/2
        if area==0 or abs(2*area-math.hypot(*area_vector))>1e-12*area:
            raise ValueError('Misaligned triangular port')
        flows[tag].append(area*sum(sum(v*n for v,n in zip(state[i][:3],normal[tag])) for i in face)/3)
        areas[tag].append(area)
    if any(abs(math.fsum(values)-.25)>1e-12 for values in areas.values()):
        raise ValueError('Incomplete three-port cap areas')
    return {tag:math.fsum(pieces) for tag,pieces in flows.items()}


def stokes(exe, root, grid, jump):
    directory=root/('stokes-'+str(jump))
    source=json.loads(generate(directory,grid).read_text())
    boundaries=[dict(tag=t,type='velocity',value=[0.,0.,0.]) for t in (1,4)]
    boundaries.extend(dict(tag=t,type='pressure',value=p) for t,p in ((2,jump/2),(3,-jump/2)))
    cfg=dict(mesh='fluid.msh',output='solution.vtu',solver=source['solver'],
             fluid=dict(mode='stokes',density=1.,viscosity=1.,stabilization_tau=.01,boundaries=boundaries))
    (directory/'stokes.json').write_text(json.dumps(cfg,indent=2)+'\n')
    run([exe,'-case','stokes.json'],directory,'solve.log')
    q=cap_flows(directory)
    if max(abs(q[1]),abs(math.fsum(q.values())))>1e-10*abs(q[2]) or q[2]*jump>=0:
        raise ValueError('Differential pressure failed its sign or net-flux check')
    return dict(pressure_jump_pa=jump,outward_flow=q,differential_resistance=-jump/(q[2]-q[3]),
                mesh_sha256=hashlib.sha256((directory/'fluid.msh').read_bytes()).hexdigest())


def coupled(exe, mpi, root, grid, inlet, resistances, steps, duration):
    directory=root/(f'clamped-q{inlet}-r{resistances[0]}-{resistances[1]}')
    cfg=json.loads(generate(directory,grid).read_text())
    geo=json.loads((directory/'geometry.json').read_text())
    f=cfg['fsi']
    f.update(dt=duration/steps,steps=steps,output_interval=steps)
    f['domains']['solid_constraints'].extend(dict(tag=t,components=[0,1,2]) for t in (14,15))
    f['inlet']['flow_rate'].update(mean=inlet,amplitude=0.)
    models=f['domains']['rcr_outlets']
    for m,resistance in zip(models,resistances):
        factor=resistance/(m['proximal_resistance']+m['distal_resistance'])
        m['proximal_resistance']*=factor
        m['distal_resistance']*=factor
        m['compliance']/=factor
    runner=Runner(exe,str(mpi),directory,interface_area=geo['interface_area'],singleton=True)
    _,rows,_=runner.solve('coupled',cfg)
    closure=max(check_rcr_history(runner,'coupled',m,rows,sole_pressure=False) for m in models)
    last=rows[-1]
    q=[last['endpoint_rcr_flow_'+str(t)] for t in (2,3)]
    p=[last['endpoint_rcr_pressure_'+str(t)] for t in (2,3)]
    drift=max(abs(r['endpoint_rcr_flow_'+str(t)]-v)/inlet for r in rows[-max(2,steps//4):] for t,v in zip((2,3),q))
    terminal_error=max(abs(v-r*flow) for v,r,flow in zip(p,resistances,q))
    movement=max(abs(r['endpoint_volume']-geo['reference_fluid_volume']) for r in rows)
    if (movement>1e-11 or abs(sum(q)/inlet-1)>1e-10 or drift>1e-7 or
            terminal_error>1e-7*max(abs(v) for v in p)):
        raise ValueError(f'Steady clamped control not established: drift={drift}, pressure={terminal_error}, motion={movement}')
    return dict(inlet_flow=inlet,r2=resistances[0],r3=resistances[1],outlet_flows=q,outlet_pressures=p,
                tag2_fraction=q[0]/inlet,last_quarter_flow_drift_inlet=drift,steady_pressure_defect_pa=terminal_error,
                max_volume_change_m3=movement,max_circuit_residual=closure,
                mesh_sha256=hashlib.sha256((directory/'fluid.msh').read_bytes()).hexdigest())


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('executable','mpiexec','work'):
        cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--refinement',type=int,default=1)
    cli.add_argument('--steps',type=int,default=80)
    cli.add_argument('--duration',type=float,default=8.)
    args=cli.parse_args()
    exe=args.executable.resolve()
    receipts=[stokes(exe,args.work,args.refinement,jump) for jump in (.02,-.01)]
    resistance=receipts[0]['differential_resistance']
    if abs(receipts[1]['differential_resistance']/resistance-1)>1e-9:
        raise ValueError('Linear differential resistance depends on the pressure sign or amplitude')
    states=[]
    for q,rs in ((.002,(44.,11.)),(.0002,(44.,11.)),(.002,(11.,44.)),(.002,(11.,11.))):
        state=coupled(exe,args.mpiexec,args.work,args.refinement,q,rs,args.steps,args.duration)
        if state['mesh_sha256']!=receipts[0]['mesh_sha256']:raise ValueError('Different lumen')
        prediction=(resistance+rs[1])/(2*resistance+sum(rs))
        state.update(predicted_tag2_fraction=prediction,prediction_difference=state['tag2_fraction']-prediction)
        states.append(state)
    out=dict(refinement=args.refinement,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
             time_steps=args.steps,duration_s=args.duration,stokes=receipts,coupled=states)
    (args.work/'result.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(resistance,[(v['tag2_fraction'],v['prediction_difference']) for v in states],flush=True)


if __name__=='__main__':main()
