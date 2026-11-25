"""Measure multi-outlet transient flux, wall storage, circuit power and periodic convergence."""
import argparse
import csv
import hashlib
import json
import lzma
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'cases/fsi')]
from verify_fsi_inlet import Runner, check_rcr_history
from generate_branched import generate


def analyse(rows, models, period, dt, periodic, reference_volume):
    # A constant-flow transient has no imposed Fourier component. Average its final second.
    if not periodic:
        period = max(1.0, period)
    import cmath
    n=round(period/dt)
    if n<4 or abs(period/dt-n)>1e-8 or len(rows)<2*n:
        raise ValueError("The histories must contain two complete, equally sampled terminal cycles")
    if any(r['step']!=i or abs(r['time']-i*dt)>2e-10*max(1,i*dt) or abs(r['accepted_dt']-dt)>1e-11*dt
           for i,r in enumerate(rows,1)):
        raise ValueError("Unexpected step number, time or accepted step size")
    omega=2*math.pi/period
    recent,previous=rows[-n:],rows[-2*n:-n]
    stats={}
    peak_inflow=max(abs(r['endpoint_inlet_flow']) for r in rows)
    def phasor(col):
        return 2*sum(r[col]*cmath.exp(-1j*omega*r['time']) for r in recent)/n
    for model in models:
        suffix='_'+str(model['tag'])
        rp,rd,cap,pd=(model[k] for k in ('proximal_resistance','distal_resistance','compliance','distal_pressure'))
        dissipation=[]
        balance=[]
        for r in rows:
            q,pc,pb,rate=(r[k+suffix] for k in ('stage_rcr_flow','stage_capacitor_pressure','stage_rcr_pressure','stage_capacitor_rate'))
            dissipation.append(rp*q*q+(pc-pd)**2/rd)
            balance.append((pb-pd)*q-dissipation[-1]-cap*(pc-pd)*rate)
        power_error=max(abs(v) for v in balance)
        if not all(map(math.isfinite,balance)) or min(dissipation)<0 or power_error>1e-8*max(dissipation+[1e-12]):
            raise ValueError(f"RCR power identity failed for tag {model['tag']}")
        col='endpoint_rcr_flow'+suffix
        pressure='endpoint_rcr_pressure'+suffix
        mean_q=sum(r[col] for r in recent)/n
        mean_p=sum(r[pressure] for r in recent)/n
        flow_mode=phasor(col)
        change=max(abs(a[col]-b[col]) for a,b in zip(recent,previous))/peak_inflow
        pressure_mode=phasor(pressure)
        z=pressure_mode/flow_mode if periodic and abs(flow_mode)>1e-6*peak_inflow else None
        mode_change=change*peak_inflow/abs(flow_mode) if z is not None else None
        target=rp+rd/(1+1j*omega*rd*cap)
        stats[model['tag']]=dict(mean_flow=mean_q,mean_pressure=mean_p,peak_to_peak_flow=max(r[col] for r in recent)-min(r[col] for r in recent),
                      terminal_steady_pressure_defect_pa=mean_p-pd-(rp+rd)*mean_q,
                      previous_cycle_max_flow_change_over_inlet_peak=change,
                      previous_cycle_flow_change_over_port_harmonic=mode_change,
                      port_harmonic_settled=mode_change<1e-3 if mode_change is not None else None,
                      flow_harmonic=[flow_mode.real,flow_mode.imag] if periodic else None,
                      pressure_harmonic=[pressure_mode.real,pressure_mode.imag] if periodic else None,
                      maximum_stage_circuit_power_error_watts=power_error,
                      maximum_dissipated_power_watts=max(dissipation),
                      impedance_modulus_error_fraction=abs(z/target)-1 if z is not None else None,
                      impedance_phase_error_degrees=math.degrees(cmath.phase(z/target)) if z is not None else None)
    port_sum=lambda r:sum(r['endpoint_rcr_flow_'+str(m['tag'])] for m in models)
    max_mass=max(abs(r['stage_mass_residual']) for r in rows)
    max_ports=max(abs(r['endpoint_outlet_flow']-port_sum(r)) for r in rows)
    if max_mass>1e-8*peak_inflow or max_ports>1e-9*peak_inflow:
        raise ValueError(f"Branched mass or endpoint port flux failed: {max_mass}, {max_ports}")
    # End caps are fixed, the initial flow is zero. Compare tracked cavity volume
    # against an independent endpoint trapezoid, including the startup interval.
    def integral(key):
        return dt*(math.fsum(r[key] for r in rows)-.5*rows[-1][key])
    net_influx=integral('endpoint_inlet_flow')-integral('endpoint_outlet_flow')
    gain=rows[-1]['endpoint_volume']-reference_volume
    return dict(ports=stats,terminal_window_s=period,end_time=rows[-1]['time'],peak_inlet_flow=peak_inflow,
                maximum_instantaneous_mass_defect=max_mass,maximum_port_sum_defect=max_ports,
                volume_gain_cubic_m=gain,time_integrated_net_influx_cubic_m=net_influx,
                endpoint_trapezoid_minus_volume_gain_cubic_m=net_influx-gain,
                last_cycle_mean_inlet=sum(r['endpoint_inlet_flow'] for r in recent)/n,
                last_cycle_mean_total_outlet=sum(port_sum(r) for r in recent)/n,
                last_cycle_mean_wall_flux=sum(r['endpoint_wall_flux'] for r in recent)/n,
                min_endpoint_fluid_j=min(r['endpoint_min_fluid_j'] for r in rows),
                min_endpoint_solid_j=min(r['endpoint_min_solid_j'] for r in rows))


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('work','executable','mpiexec'):
        cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--refinement',type=int,default=1)
    cli.add_argument('--ranks',type=int,default=1)
    cli.add_argument('--steps',type=int,required=True)
    cli.add_argument('--dt',type=float,required=True)
    cli.add_argument('--waveform',choices=['constant','periodic'],required=True)
    cli.add_argument('--unequal',action='store_true')
    cli.add_argument('--mpi-one',action='store_true',help='Use mpiexec for one rank as well as distributed runs')
    cli.add_argument('--audit-only',action='store_true')
    args=cli.parse_args()
    os.environ.setdefault('OMPI_MCA_pml','ob1')
    os.environ.setdefault('OMPI_MCA_btl','self,sm,tcp')
    work=args.work.resolve()
    if args.audit_only:
        with tempfile.TemporaryDirectory() as temp:
            expected=Path(temp)
            cfg=json.loads(generate(expected,args.refinement).read_text())
            for name in ('fluid.msh','solid.msh','geometry.json'):
                if (expected/name).read_bytes()!=(work/name).read_bytes():
                    raise ValueError('Saved T-junction mesh differs from regenerated mesh')
    else:
        cfg=json.loads(generate(work,args.refinement).read_text())
    geo=json.loads((work/'geometry.json').read_text())
    cfg['fsi'].update(steps=args.steps,dt=args.dt,output_interval=args.steps)
    models=cfg['fsi']['domains']['rcr_outlets']
    if args.unequal:
        models[0].update(proximal_resistance=12.,distal_resistance=32.,compliance=.00625)
    inlet=cfg['fsi']['inlet']['flow_rate']
    if args.waveform=='constant':
        inlet['amplitude']=0.
    run=Runner(args.executable,str(args.mpiexec),work,timeout=14400,interface_area=geo['interface_area'],singleton=not args.mpi_one)
    digests={name:hashlib.sha256((work/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')}
    digests['executable']=hashlib.sha256(args.executable.read_bytes()).hexdigest()
    if args.audit_only:
        previous=json.loads((work/'report.json').read_text())
        if previous['sha256']!=digests or previous['ranks']!=args.ranks:
            raise ValueError("Archived executable, mesh or MPI rank count differs")
        saved=json.loads((work/'branched.json').read_text())
        if any(saved[k]!=v for k,v in cfg.items() if k!='output'):
            raise ValueError("Archived case differs from requested controls")
        with (work/'branched.csv').open() as f: rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
    else:
        _,rows,_=run.solve('branched',cfg,args.ranks)
    if len(rows)!=args.steps:raise ValueError("Incomplete accepted history")
    for model in models:check_rcr_history(run,'branched',model,rows,sole_pressure=False)
    result=dict(geometry=geo,sha256=digests,ranks=args.ranks,dt=args.dt,steps=args.steps,models=models,waveform=args.waveform,
                terminal=analyse(rows,models,inlet['period'],args.dt,args.waveform=='periodic',geo['reference_fluid_volume']))
    result['milestones']=[]
    terminal_period=result['terminal']['terminal_window_s']
    for target in (.4,1.,2.,4.,8.,16.,32.,64.,128.):
        idx=round(target/args.dt)
        if idx>len(rows) or target<2*terminal_period or abs(idx*args.dt-target)>1e-11:
            continue
        measurement=analyse(rows[:idx],models,inlet['period'],args.dt,args.waveform=='periodic',geo['reference_fluid_volume'])
        result['milestones'].append(dict(time=target,mean_inlet=measurement['last_cycle_mean_inlet'],
             mean_outlet=measurement['last_cycle_mean_total_outlet'],mean_wall_flux=measurement['last_cycle_mean_wall_flux'],
             volume_gain=measurement['volume_gain_cubic_m'],
             mean_port_flow={k:v['mean_flow'] for k,v in measurement['ports'].items()}))
    result['launch_mode']=(previous.get('launch_mode','mpiexec') if args.audit_only else
                           'singleton' if args.ranks==1 and not args.mpi_one else 'mpiexec')
    result['history_sha256']={}
    for name in ('branched.csv','branched_pressure_faces.csv'):
        raw=(work/name).read_bytes()
        archive=work/(name+'.xz')
        result['history_sha256'][name]=hashlib.sha256(raw).hexdigest()
        if args.audit_only and archive.exists():
            if lzma.decompress(archive.read_bytes())!=raw:
                raise ValueError('Saved and compressed histories disagree: '+name)
        else:
            archive.write_bytes(lzma.compress(raw))
    if args.audit_only and previous.get('history_sha256',result['history_sha256'])!=result['history_sha256']:
        raise ValueError('Archived history hashes differ')
    temp=work/'report.tmp'
    temp.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    temp.replace(work/'report.json')
    print(json.dumps(result['terminal']),flush=True)


if __name__=='__main__':
    main()
