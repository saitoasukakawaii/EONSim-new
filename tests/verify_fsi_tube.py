"""Circular FSI inlet, curved conforming wall, MPI and restart acceptance."""
import argparse
import copy
import cmath
import csv
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from verify_fsi_inlet import Runner, check_rcr_history, error
from generate_tube import generate


def verify_wall_support(run, base):
    free = copy.deepcopy(base)
    free['fsi']['steps'] = 6
    free['time'] = dict(scheme='generalized_alpha', rho_infinity=0.5)
    baseline, _, _ = run.solve('support-free', free, 2)
    zero = copy.deepcopy(free)
    zero['fsi']['domains']['wall_supports'] = [dict(tag=14, stiffness=0, damping=0)]
    same, zero_rows, _ = run.solve('support-zero', zero, 2)
    assert error(baseline, same) < 1e-14
    assert all(row['step_support_work'] == 0 for row in zero_rows)
    free_checkpoint = run.work/'support-free-checkpoint'
    run.solve('support-free-part', free, 2, ['-checkpoint', free_checkpoint, '-stop_after', 3])
    zero_resumed, _, _ = run.solve('support-zero-resume', zero, 2, ['-restart', free_checkpoint])
    assert error(baseline, zero_resumed) < 2e-9

    results = {}
    for scheme in ('be', 'bdf2', 'generalized_alpha'):
        cfg = copy.deepcopy(free)
        cfg['time'] = dict(scheme=scheme)
        cfg['fsi']['domains']['wall_supports'] = [dict(tag=14, stiffness=200, damping=15)]
        one, rows, _ = run.solve('support-'+scheme+'-one', cfg)
        two, parallel_rows, _ = run.solve('support-'+scheme+'-two', cfg, 2)
        assert error(one, two) < 2e-9
        peak = max(r['endpoint_support_spring_energy'] for r in rows)
        assert peak > 1e-12 and max(r['stage_support_dissipation'] for r in rows) > 1e-9
        previous = 0.
        for row, pair in zip(rows, parallel_rows):
            assert min(row['stage_support_spring_energy'], row['stage_support_dissipation']) >= 0
            energy = row['endpoint_support_spring_energy']
            assert abs(row['step_support_work'] + energy - previous
                       + row['accepted_dt']*row['stage_support_dissipation']) < 1e-12*peak
            for key in ('stage_support_spring_energy','stage_support_power','stage_support_dissipation',
                        'endpoint_support_spring_energy','step_support_work'):
                assert math.isclose(row[key],pair[key],rel_tol=1e-7,abs_tol=1e-14)
            previous = energy
        results[scheme] = dict(peak_energy=peak, mpi_error=error(one, two))
    assert error(baseline, two) > 1e-8
    checkpoint = run.work/'support-checkpoint'
    run.solve('support-part', cfg, 2, ['-checkpoint', checkpoint, '-stop_after', 3])
    resumed, tail, _ = run.solve('support-resume', cfg, 2, ['-restart', checkpoint])
    assert error(resumed, two) < 2e-9 and len(tail) == 3
    for row, full in zip(tail, parallel_rows[3:]):
        assert math.isclose(row['step_support_work'], full['step_support_work'], rel_tol=1e-7, abs_tol=1e-14)
    four, _, log = run.solve('support-four', cfg, 4, ['-snes_test_jacobian'])
    ratios = [float(v) for v in re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)', log)]
    assert ratios and max(ratios) < 1e-6 and error(four, two) < 2e-9
    cfg['fsi']['domains']['wall_supports'][0]['damping'] = 16
    run.solve('support-restart-change', cfg, 2, ['-restart', checkpoint], fail='Checkpoint mesh/partition/physics mismatch')
    cfg['fsi']['domains']['wall_supports'] = [dict(tag=14, damping=15)]
    _, damped, _ = run.solve('support-pure-damper', cfg, 2)
    assert all(row['endpoint_support_spring_energy']==0 and
               math.isclose(row['stage_support_power'], -row['stage_support_dissipation'], rel_tol=2e-13)
               for row in damped)
    for label, supports, message in (
        ('tag', [dict(tag=2, stiffness=5)], 'solid exterior tag'),
        ('interface', [dict(tag=13, stiffness=5)], 'Invalid FSI wall support'),
        ('negative', [dict(tag=14, damping=-1)], 'finite and nonnegative'),
        ('nonfinite', [dict(tag=14, stiffness='.inf')], 'finite and nonnegative'),
        ('duplicate', [dict(tag=14, damping=1),dict(tag=14, stiffness=1)], 'Duplicate FSI wall support')):
        cfg['fsi']['domains']['wall_supports'] = supports
        run.solve('invalid-wall-support-'+label, cfg, 2, fail=message)
    return results


def verify_rcr(run, base):
    model = dict(tag=2,proximal_resistance=4.,distal_resistance=16.,compliance=.005,
                 distal_pressure=.03,initial_capacitor_pressure=.06)
    cfg = copy.deepcopy(base)
    cfg['fsi'].update(steps=7, pressure_face_history=True, output_interval=7)
    cfg['fsi']['domains']['rcr_outlet'] = model
    cfg['time_control'] = dict(step_sizes=[.002,.002,.0015,.0025,.002,.0015,.0025])
    report = {}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time'] = dict(scheme=scheme)
        prefix = 'rcr-'+scheme
        one, rows, _ = run.solve(prefix+'-one', cfg)
        two, parallel, _ = run.solve(prefix+'-two', cfg, 2)
        assert min(r['stage_rcr_flow'] for r in rows) < -1e-5
        residual = check_rcr_history(run, prefix+'-two', model, parallel)
        checkpoint = run.work/(prefix+'-checkpoint')
        run.solve(prefix+'-start', cfg, 2, ['-stop_after',3,'-checkpoint',checkpoint])
        resumed, tail, _ = run.solve(prefix+'-resumed', cfg, 2, ['-restart',checkpoint])
        check_rcr_history(run, prefix+'-resumed', model, tail, restart=3)
        assert len(tail) == len(parallel)-3
        assert error(one,two)<2e-9 and error(resumed,two)<2e-9
        for full, restarted in zip(parallel[3:],tail):
            for column in ('stage_rcr_flow','endpoint_rcr_pressure','endpoint_capacitor_pressure','stage_capacitor_rate'):
                assert abs(full[column]-restarted[column])<2e-9
        report[scheme] = dict(mpi=error(one,two),restart=error(resumed,two),circuit_residual=residual)
    four, _, log = run.solve('rcr-four-fd', cfg, 4, ['-snes_test_jacobian','-stop_after',2])
    ref, _, _ = run.solve('rcr-direct-two', cfg, 2, ['-stop_after',2])
    ratios = [float(v) for v in re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)]
    assert ratios and max(ratios)<1e-6 and error(four,ref)<2e-9
    iterative, hybrid_rows, _ = run.solve('rcr-hybrid',cfg,2,['-pc_recipe','hybrid','-stop_after',2])
    check_rcr_history(run,'rcr-hybrid',model,hybrid_rows)
    assert error(iterative,ref)<2e-8
    report['jacobian_relative_error'] = max(ratios)
    report['hybrid_field_error'] = error(iterative,ref)
    changed=copy.deepcopy(cfg)
    changed['fsi']['domains']['rcr_outlet']['compliance']*=1.2
    run.solve('rcr-changed',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    for key,value,why in [('tag',14,'declared pressure tag'),('distal_resistance',0,'finite and positive'),
                          ('compliance',-1,'finite and positive'),('proximal_resistance','.inf','finite and positive'),
                          ('distal_pressure','.nan','pressures must be finite')]:
        bad=copy.deepcopy(cfg)
        bad['fsi']['domains']['rcr_outlet'][key]=value
        run.solve('rcr-invalid-'+key,bad,2,fail=why)
    moving=copy.deepcopy(cfg)
    moving['fsi']['domains']['mesh_constraints']=[dict(tag=1,components=[0,1,2])]
    run.solve('rcr-moving',moving,2,fail='stationary fluid exterior')
    mixed=copy.deepcopy(cfg)
    del mixed['fsi']['inlet']
    mixed['fsi']['pressure']=.08
    mixed['fsi']['domains']['pressure_tags']=[1,2]
    _, rows, _ = run.solve('rcr-and-prescribed',mixed,2,['-stop_after',3])
    check_rcr_history(run,'rcr-and-prescribed',model,rows,sole_pressure=False)
    with (run.work/'rcr-and-prescribed_pressure_faces.csv').open() as stream:
        common=[r for r in csv.DictReader(stream) if int(r['tag'])==1]
    assert len(common)==len(rows) and all(float(r['stage_prescribed_pressure'])==.08 for r in common)
    assert all(r['applied_pressure']==.08 for r in rows)
    return report


def verify_rcr_retry(exe,mpi,work):
    cfg=json.loads(generate(work,sectors=8,axial=2).read_text())
    area=json.loads((work/'geometry.json').read_text())['interface_area']
    run=Runner(exe,mpi,work,interface_area=area)
    cfg['fsi'].update(steps=5,dt=.004,pressure_face_history=True,output_interval=5)
    cfg['fsi']['inlet']['flow_rate'].update(mean=1.,amplitude=.1)
    model=dict(tag=2,proximal_resistance=1.,distal_resistance=8.,compliance=.03,distal_pressure=.02)
    cfg['fsi']['domains']['rcr_outlet']=model
    report={}
    for scheme in ('bdf2','generalized_alpha'):
        cfg['time']=dict(scheme=scheme)
        cfg.pop('time_control',None)
        checkpoint=work/('checkpoint-'+scheme)
        run.solve('start-'+scheme,cfg,2,['-checkpoint',checkpoint,'-stop_after',2])
        cfg['time_control']=dict(max_retries=16,minimum_dt=1e-10,reduction=.5)
        actual,rows,log=run.solve('retry-'+scheme,cfg,2,['-restart',checkpoint,'-snes_max_it',2,'-stop_after',3])
        assert 'step_retry=' in log and len(rows)==1 and rows[0]['accepted_dt']<.004
        check_rcr_history(run,'retry-'+scheme,model,rows,restart=2)
        cfg['time_control']['step_sizes']=[.004,.004,rows[0]['accepted_dt']]
        replay,other,_=run.solve('replay-'+scheme,cfg,2,['-stop_after',3])
        assert error(actual,replay)<2e-9
        for key in ('stage_rcr_flow','stage_capacitor_rate','endpoint_rcr_pressure','endpoint_capacitor_pressure'):
            assert abs(rows[0][key]-other[-1][key])<2e-9
        report[scheme]=dict(retries=log.count('step_retry='),accepted_dt=rows[0]['accepted_dt'],
                            replay_field_error=error(actual,replay))
    return report


def verify_rcr_harmonic(exe, mpi, work):
    # All solid nodes of one axial slab lie on clamped ends. Continuity makes Qout=Qin.
    # The complete 3D saddle point problem still determines the outlet traction.
    cfg = json.loads(generate(work,sectors=8,axial=1,radial=2,clamped_slab=True).read_text())
    geometry = json.loads((work/'geometry.json').read_text())
    run = Runner(exe,mpi,work,interface_area=geometry['interface_area'])
    cfg['fsi'].update(pressure_face_history=True,output_interval=10000,stabilization_tau=.01)
    cfg['fsi']['inlet']['ramp_time'] = 0.
    cfg['fsi']['inlet']['flow_rate'].update(mean=0.,amplitude=.01,period=1.)
    omega, tau = 2*math.pi, .2
    def exact(t):
        s, c = math.sin(omega*t), math.cos(omega*t)
        pc = .03+.08*(s-omega*tau*c)/(1+(omega*tau)**2)
        return pc+.03*s
    model = dict(tag=2,proximal_resistance=3.,distal_resistance=8.,compliance=.025,
                 distal_pressure=.03,initial_capacitor_pressure=exact(0.))
    cfg['fsi']['domains']['rcr_outlet'] = model
    report = {}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time'] = dict(scheme=scheme)
        errors, impedance = [], []
        exact_z = 3+8/(1+1j*omega*tau)
        for n in (32,64,128):
            cfg['fsi'].update(steps=n,dt=1/n)
            label=f'harmonic-{scheme}-{n}'
            _,rows,_ = run.solve(label,cfg)
            check_rcr_history(run,label,model,rows)
            flux_error=max(abs(r['endpoint_rcr_flow']-.01*math.sin(omega*r['time'])) for r in rows)
            assert flux_error<5e-13
            errors.append(max(abs(r['endpoint_rcr_pressure']-exact(r['time'])) for r in rows))
            def harmonic(column):
                return sum(r[column]*cmath.exp(-1j*omega*r['time']) for r in rows)
            z=harmonic('endpoint_rcr_pressure')/harmonic('endpoint_rcr_flow')
            ratio=z/exact_z
            impedance.append(dict(real=z.real,imag=z.imag,amplitude_error_fraction=abs(ratio)-1,
                                  phase_error_degrees=math.degrees(cmath.phase(ratio))))
        orders=[math.log2(a/b) for a,b in zip(errors,errors[1:])]
        assert min(orders)>(.9 if scheme=='be' else 1.55), (scheme,orders)
        assert abs(impedance[-1]['amplitude_error_fraction']) < (.01 if scheme=='be' else .0005)
        assert abs(impedance[-1]['phase_error_degrees']) < (.6 if scheme=='be' else .01)
        report[scheme]=dict(max_pressure_errors=errors,observed_orders=orders,impedance=impedance)
    cfg['time'] = dict(scheme='be')
    cfg['fsi'].update(steps=32,dt=1/32)
    cfg['fsi']['inlet']['flow_rate'].update(mean=.01,amplitude=0.)
    del model['initial_capacitor_pressure']   # The default is the distal reservoir pressure.
    _,rows,_=run.solve('rcr-constant-flow',cfg)
    q=.01
    for j,row in enumerate(rows,1):
        pc=model['distal_pressure']+model['distal_resistance']*q*(1-(1+1/(32*tau))**(-j))
        assert abs(row['endpoint_rcr_flow']-q) < 5e-13
        assert abs(row['endpoint_capacitor_pressure']-pc) < 2e-12
        assert abs(row['endpoint_rcr_pressure']-pc-model['proximal_resistance']*q) < 2e-12
    report['constant_flow_be']=dict(steps=len(rows),endpoint_pressure=rows[-1]['endpoint_rcr_pressure'])
    return report


def verify_tube(run, base, work):
    report = {}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg=copy.deepcopy(base);cfg['time']=dict(scheme=scheme)
        one,rows,_=run.solve(scheme+'-one',cfg)
        two,_,_=run.solve(scheme+'-two',cfg,2)
        assert error(one,two)<2e-9
        maximum_radial=0
        for row in rows:
            t=row['time'];x=min(1,t/.01)
            target=x**3*(10-15*x+6*x*x)*(.01+.005*math.sin(2*math.pi*t/.04))
            assert abs(row['endpoint_inlet_flow']-target)<1e-12
            assert abs(row['stage_mass_residual'])<1e-9
            assert abs(row['stage_mass_residual']+row['stage_divergence'])<1e-12
            tree=ET.parse(work/f'{scheme}-one_step{int(row["step"])}.vtu')
            xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
            arrays={n.attrib['Name']:list(map(float,n.text.split())) for n in tree.findall('.//PointData/DataArray')}
            solid=ET.parse(work/f'{scheme}-one_step{int(row["step"])}_solid.vtu')
            sv=list(map(float,solid.find('.//PointData/DataArray[@Name="velocity"]').text.split()))
            sd=list(map(float,solid.find('.//PointData/DataArray[@Name="displacement"]').text.split()))
            used=set(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            for i in used:
                displacement=arrays['mesh_displacement'][3*i:3*i+3]
                ref=[xyz[3*i+c]-displacement[c] for c in range(3)]
                if abs(math.hypot(ref[1],ref[2])-1)<1e-12:
                    assert max(abs(arrays['velocity'][3*i+c]-sv[3*i+c]) for c in range(3))<1e-12
                    assert max(abs(displacement[c]-sd[3*i+c]) for c in range(3))<1e-12
                    maximum_radial=max(maximum_radial,abs(displacement[1]*ref[1]+displacement[2]*ref[2]))
                if abs(ref[0])<1e-12:
                    assert max(abs(v) for v in displacement)<1e-12
                    assert max(abs(v) for v in arrays['velocity'][3*i+1:3*i+3])<1e-12
        assert maximum_radial>1e-8,maximum_radial
        checkpoint=work/(scheme+'-checkpoint')
        run.solve(scheme+'-part',cfg,2,['-checkpoint',checkpoint,'-stop_after',7])
        resumed,tail,_=run.solve(scheme+'-resume',cfg,2,['-restart',checkpoint])
        assert len(tail)==13 and error(two,resumed)<2e-9
        report[scheme]=dict(mpi_error=error(one,two),restart_error=error(two,resumed),
            maximum_radial_displacement=maximum_radial,maximum_mass_residual=max(abs(r['stage_mass_residual']) for r in rows))
    profile=work/'alpha-four-events.csv'
    four,four_rows,_=run.solve('alpha-four',cfg,4,['-log_view',f':{profile}:ascii_csv'])
    wanted={'FSIFluidRes','FSIFluidAleJac','FSISolidRes','FSISolidJac','FSIInsert','FSIForceReplay'}
    with profile.open() as stream:
        observed=[r for r in csv.DictReader(stream) if r['Stage Name']=='Main Stage' and r['Event Name'] in wanted]
    assert {(r['Event Name'],int(r['Rank'])) for r in observed}=={(e,i) for e in wanted for i in range(4)}
    for name in wanted:
        entries=[r for r in observed if r['Event Name']==name]
        assert len(entries)==4 and sum(int(r['Count']) for r in entries)>0
        assert all(math.isfinite(float(r['Time'])) and float(r['Time'])>=0 for r in entries)
        if name=='FSIForceReplay':
            assert all(int(r['Count'])==len(four_rows) for r in entries)
    assert error(one,four)<2e-9
    report['four_rank_error']=error(one,four)
    with (work/'alpha-four_pressure_faces.csv').open() as stream:
        faces=list(csv.DictReader(stream))
    assert len(faces)==len(four_rows)
    for face,row in zip(faces,four_rows):
        assert int(face['tag'])==cfg['fsi']['domains']['pressure_tags'][0]
        for sample in ('stage','endpoint'):
            assert abs(float(face[sample+'_outward_flow'])-row[sample+'_outlet_flow'])<1e-12
    _,_,log=run.solve('jacobian',cfg,2,['-stop_after',3,'-snes_test_jacobian'])
    ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)))
    assert ratios and max(ratios)<1e-6,ratios
    report['jacobian_relative_error']=max(ratios)
    changed=copy.deepcopy(cfg);changed['fsi']['inlet']['flow_rate']['mean']=.02
    run.solve('changed-waveform',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    for label,change,message in (
        ('radius',dict(radius=0),'Invalid FSI flow_rate radius'),
        ('oversize',dict(radius=1.1),'conflicts with homogeneous/interface'),
        ('outside',dict(radius=.9),'outside circle'),
        ('plane',dict(center=[.1,0,0]),'outside circle plane'),
        ('mixed',dict(lower=[0,-1,-1]),'excludes rectangle bounds'),
        ('profile',dict(profile='unknown'),'Invalid FSI flow_rate profile')):
        bad=copy.deepcopy(base);bad['fsi']['inlet']['flow_rate'].update(change)
        run.solve('invalid-'+label,bad,2,fail=message)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--group', choices=('all', 'tube', 'tube_wall_support', 'tube_rcr', 'tube_rcr_response'),
                        default='all', help='Run an independent fixture, or all fixtures in the original CLI')
    args = parser.parse_args()
    work = args.work.resolve()
    base = json.loads(generate(work).read_text())
    geometry = json.loads((work/'geometry.json').read_text())
    base['fsi']['pressure_face_history'] = True
    run = Runner(args.executable, args.mpiexec, work, interface_area=geometry['interface_area'])
    report = {}
    if args.group in ('all', 'tube_wall_support'):
        report['wall_support'] = verify_wall_support(run, base)
    if args.group in ('all', 'tube_rcr'):
        report['rcr'] = verify_rcr(run, base)
    if args.group in ('all', 'tube_rcr_response'):
        report['rcr_harmonic'] = verify_rcr_harmonic(args.executable, args.mpiexec, work/'rcr-harmonic')
        report['rcr_retry'] = verify_rcr_retry(args.executable, args.mpiexec, work/'rcr-retry')
    if args.group in ('all', 'tube'):
        report.update(verify_tube(run, base, work))
    (work/'metrics.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
