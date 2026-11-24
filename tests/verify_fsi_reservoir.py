"""Check moving distal reservoirs in the 3D FSI/RCR residual, restart and manufactured responses."""
import argparse
import cmath
import copy
import json
import math
from pathlib import Path

from verify_fsi_inlet import Runner, check_rcr_history, error
from verify_fsi_moving_port import circular_case, retry
from generate_branched import generate as junction
from generate_tube import generate as tube


def two_frequencies(exe, mpi, work):
    cfg = json.loads(tube(work, sectors=8, axial=1, radial=2, clamped_slab=True).read_text())
    geometry = json.loads((work/'geometry.json').read_text())
    run = Runner(exe, mpi, work, interface_area=geometry['interface_area'], singleton=True)
    f = cfg['fsi']
    f.update(pressure_face_history=True, output_interval=10000, stabilization_tau=.01)
    f['inlet']['ramp_time'] = 0.
    flow = f['inlet']['flow_rate']
    flow.update(mean=0., amplitude=.004, period=.5)
    wave = dict(amplitude=.07, period=1.)
    rp, rd, c, mean = 3., 8., .025, .08
    omega = 2*math.pi
    h_distal = 1/(1+1j*omega*rd*c)
    z_flow = rp + rd/(1+2j*omega*rd*c)
    def exact(t):
        distal = wave['amplitude']*h_distal*cmath.exp(1j*omega*t)
        inlet = flow['amplitude']*z_flow*cmath.exp(2j*omega*t)
        return mean + (distal+inlet).imag
    model = dict(tag=2,proximal_resistance=rp,distal_resistance=rd,compliance=c,distal_pressure=mean,
                 initial_capacitor_pressure=exact(0.),distal_pressure_time=wave)
    f['domains']['rcr_outlet'] = model
    results = {}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time'] = dict(scheme=scheme)
        if scheme=='generalized_alpha':
            cfg['time']['rho_infinity']=.5
        errors = []
        transfer = []
        # The inlet runs at twice the reservoir frequency. Resolve its shortest period with 32–128 steps.
        for n in (64,128,256):
            f.update(steps=n,dt=1/n)
            label = f'{scheme}-{n}'
            _, rows, _ = run.solve(label,cfg)
            residual = check_rcr_history(run,label,model,rows)
            assert len(rows)==n
            flux_error = max(abs(r['endpoint_rcr_flow']-flow['amplitude']*math.sin(2*omega*r['time'])) for r in rows)
            assert flux_error<2e-11, flux_error
            errors.append(max(abs(r['endpoint_rcr_pressure']-exact(r['time'])) for r in rows))
            def response(harmonic):
                return 2j/n*sum((r['endpoint_rcr_pressure']-mean)*cmath.exp(-1j*harmonic*omega*r['time']) for r in rows)
            distal = response(1)/wave['amplitude']
            inlet = response(2)/flow['amplitude']
            transfer.append(dict(steps=n,stage_defect=residual,distal_amplitude=abs(distal),
                                 distal_phase_deg=math.degrees(cmath.phase(distal)),distal_complex_error=abs(distal/h_distal-1),
                                 inlet_complex_error=abs(inlet/z_flow-1)))
        orders = [math.log2(a/b) for a,b in zip(errors,errors[1:])]
        assert min(orders)>(.85 if scheme=='be' else 1.65), (scheme,orders)
        assert transfer[-1]['distal_complex_error'] < (.025 if scheme=='be' else .002), transfer
        assert transfer[-1]['inlet_complex_error'] < (.045 if scheme=='be' else .004), transfer
        results[scheme]=dict(max_pressure_errors=errors,orders=orders,frequency_response=transfer)
    return dict(distal_exact=[h_distal.real,h_distal.imag],inlet_exact=[z_flow.real,z_flow.imag],schemes=results)


def two_reservoirs(exe, mpi, work):
    cfg = json.loads(junction(work).read_text())
    geometry = json.loads((work/'geometry.json').read_text())
    run = Runner(exe,mpi,work,interface_area=geometry['interface_area'],singleton=True)
    f=cfg['fsi']
    f.update(dt=.012,steps=9,output_interval=9,pressure_face_history=True)
    cfg['time']=dict(scheme='generalized_alpha',rho_infinity=.5)
    cfg['time_control']=dict(step_sizes=[.012,.009,.015,.008,.013,.01,.011,.009,.012])
    dom=f['domains']
    left,right=dom['rcr_outlets']
    left.update(distal_pressure=.12,distal_pressure_time=dict(amplitude=.08,period=.09,ramp_time=.05),moving_plane_axis=1)
    left.pop('initial_capacitor_pressure',None)
    for key,tag in [('mesh_constraints',left['tag']),('solid_constraints',12)]:
        next(b for b in dom[key] if b['tag']==tag)['components']=[1]
    right.update(distal_pressure=-.02,initial_capacitor_pressure=.04,
                 distal_pressure_time=dict(amplitude=-.035,period=.15))
    serial, _, _ = run.solve('one',cfg)
    parallel, rows, _ = run.solve('two',cfg,2)
    worst = max(check_rcr_history(run,'two',m,rows,sole_pressure=False) for m in (left,right))
    checkpoint = work/'checkpoint'
    silent = copy.deepcopy(cfg)
    silent['fsi'].update(output_interval=0,pressure_face_history=False)
    run.solve('before-restart',silent,2,['-stop_after',3,'-checkpoint',checkpoint])
    resumed, tail, _ = run.solve('resumed',cfg,2,['-restart',checkpoint])
    for m in (left,right):
        check_rcr_history(run,'resumed',m,tail,restart=3,sole_pressure=False)
    # Changing input order preserves circuit identity across a mid-ramp checkpoint.
    reordered=copy.deepcopy(cfg)
    reordered['fsi']['domains']['rcr_outlets'].reverse()
    reordered_fields, swapped, _ = run.solve('reordered',reordered,2,['-restart',checkpoint])
    assert len(tail)==len(swapped)==len(rows)-3
    keys=[k for k in rows[0] if 'rcr_' in k or 'capacitor_' in k or 'distal_pressure' in k]
    tail_error=max(abs(full[k]-part[k]) for full,part in zip(rows[3:],tail) for k in keys)
    changed=copy.deepcopy(cfg)
    changed['fsi']['domains']['rcr_outlets'][0]['distal_pressure_time']['period']*=1.1
    run.solve('different-wave',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    explicit=copy.deepcopy(cfg)
    explicit['fsi']['domains']['rcr_outlets'][0]['initial_capacitor_pressure']=0.
    initial, _, _ = run.solve('explicit-zero',explicit,2)
    invalid=copy.deepcopy(cfg)
    invalid['fsi']['domains']['rcr_outlets'][1]['distal_pressure_time']['period']=0.
    run.solve('invalid-period',invalid,2,fail='Invalid RCR distal_pressure_time')
    changes=dict(mpi=error(serial,parallel),restart=error(resumed,parallel),port_order=error(reordered_fields,resumed),
                 implicit_initial_pressure=error(initial,parallel),restart_history=tail_error,stage_defect=worst)
    assert max(changes.values())<2e-9, changes
    return changes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',required=True)
    p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True)
    args=p.parse_args()
    work=args.work.resolve()
    report=dict(manufactured=two_frequencies(args.executable,args.mpiexec,work/'manufactured'),
                junction=two_reservoirs(args.executable,args.mpiexec,work/'junction'))
    directory=work/'retry'
    cfg,geometry=circular_case(directory,(1.,0.,0.),(0.,0.,0.))
    cfg['fsi']['domains']['rcr_outlet']['distal_pressure_time']=dict(amplitude=.01,period=.08,ramp_time=.035)
    runner=Runner(args.executable,args.mpiexec,directory,interface_area=geometry['interface_area'],singleton=True)
    report['adaptive_retry']=retry(runner,cfg)
    (work/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report)


if __name__=='__main__':
    main()
