"""Circular FSI inlet, curved conforming wall, MPI and restart acceptance."""
import argparse
import copy
import cmath
import csv
import json
import math
import os
from pathlib import Path
import re
import hashlib
import statistics
import subprocess
import tarfile
import time
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


def audit_block_linear_log(log, accepted_steps):
    residuals = [dict(re.findall(r'(\w+)=([^\s]+)',line))
                 for line in log.splitlines() if line.startswith('linear_residual ')]
    reports = [dict(re.findall(r'(\w+)=([^\s]+)',line))
               for line in log.splitlines() if line.startswith('solver_report ')]
    assert residuals and len(reports)==accepted_steps
    assert not any(marker in log for marker in
                   ('linear_residual_unavailable','linear_iteration_limit_residual ','step_retry='))
    assert sum(int(r['linear_completed']) for r in reports)==len(residuals)
    assert all(min(int(r['snes_reason']),int(r['ksp_reason']))>0 for r in reports)
    for row in residuals:
        norm, rhs = float(row['norm']), float(row['rhs_norm'])
        assert math.isfinite(norm) and math.isfinite(rhs) and min(norm,rhs)>=0., row
        assert norm <= 1e-8+1e-7*rhs, row
    return len(residuals)


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
    # Compare the reconstructed node-block Schur/coupled momentum path with
    # the existing two-step direct reference, including the RCR pressure DOF.
    improved_flags = ['-pc_recipe','hybrid','-pc_plan_schur_approx','nodal',
                      '-pc_plan_velocity_solver','coupled',
                      '-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type','lower',
                      '-ksp_rtol','1e-10','-ksp_max_it','1500']
    improved, improved_rows, _ = run.solve('rcr-nodal-coupled',cfg,2,[*improved_flags,'-stop_after',2])
    check_rcr_history(run,'rcr-nodal-coupled',model,improved_rows)
    assert error(improved,ref)<2e-8
    report['nodal_coupled_field_error'] = error(improved,ref)

    # New coupled coarse correction and complete-fluid structural Schur paths
    # must preserve both the field solution and capacitor state on restart.
    for mode, flags in (
        ('added-mass', ['-pc_recipe','added_mass','-pc_plan_schur_approx','nodal']),
        ('twolevel', ['-pc_recipe','hybrid','-pc_plan_schur_approx','nodal',
                      '-pc_plan_velocity_solver','twolevel'])):
        flags += ['-ksp_rtol','1e-10','-ksp_max_it','1500','-linear_report','-solver_report']
        label = 'rcr-'+mode
        full, full_rows, full_log = run.solve(label,cfg,2,[*flags,'-stop_after',2])
        check_rcr_history(run,label,model,full_rows)
        assert error(full,ref)<2e-8, (mode,error(full,ref))
        full_checks = audit_block_linear_log(full_log,len(full_rows))
        saved = run.work/(label+'-checkpoint')
        _, start_rows, start_log = run.solve(label+'-start',cfg,2,
                                             [*flags,'-stop_after',1,'-checkpoint',saved])
        start_checks = audit_block_linear_log(start_log,len(start_rows))
        resumed, resumed_rows, resumed_log = run.solve(label+'-resumed',cfg,2,
                                                      [*flags,'-restart',saved,'-stop_after',2])
        resumed_checks = audit_block_linear_log(resumed_log,len(resumed_rows))
        check_rcr_history(run,label+'-resumed',model,resumed_rows,restart=1)
        assert len(resumed_rows)==1 and error(full,resumed)<2e-8
        for column in ('stage_rcr_flow','endpoint_rcr_pressure','endpoint_capacitor_pressure','stage_capacitor_rate'):
            assert abs(full_rows[-1][column]-resumed_rows[0][column])<2e-9
        report[mode] = dict(field_error=error(full,ref),restart_error=error(full,resumed),
                           true_residual_checks=dict(full=full_checks,start=start_checks,
                                                     resumed=resumed_checks))

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


# Dimensioned 20 mm tube campaign. The input tarball is the immutable fixture
# already used by the historical arterial study; no regenerated geometry,
# changed physics, or historical timing receipts enter the new comparison.
def verify_arterial_block(executable, mpiexec, work):
    root = Path(__file__).resolve().parents[1]
    archive = root/'docs/research/data/fsi-linear-transient-2026-11-24/arterial-inputs.tar.xz'
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    exe, mpi = str(Path(executable).resolve()), str(Path(mpiexec).resolve())
    summary = dict(input_sha256=digest(archive), executable_sha256=digest(exe),
                   target='max(1e-23, 1e-10*rhs_norm)', tolerance_margin=1.00001,
                   field_relative_peak_limit=2e-6, cases=[], failures=[])

    def launch(command, cwd, log, timeout=130):
        t0 = time.monotonic()
        with log.open('w') as out:
            proc = subprocess.run(list(map(str,command)), cwd=cwd, env=env,
                                  stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
        return proc.returncode, time.monotonic()-t0

    def options(mode, ordering):
        if mode == 'direct':
            return ['-ksp_type','preonly','-pc_type','lu','-pc_factor_mat_solver_type','mumps']
        # Same physical acceptance and independently recomputed target for all
        # candidates. Internal stopping margin is tighter, not a relaxed gate.
        outer = ['-ksp_pc_side','right','-ksp_norm_type','unpreconditioned',
                 '-ksp_rtol','5e-11','-ksp_atol','5e-24','-ksp_max_it','3000',
                 '-ksp_gmres_restart','100','-ksp_gmres_modifiedgramschmidt']
        if mode == 'physics_lower':
            outer += ['-pc_recipe','physics','-fieldsplit_fluid_pc_fieldsplit_schur_fact_type','lower']
            for prefix, limit in [('fieldsplit_fluid_fieldsplit_velocity',10),('fieldsplit_solid',12)]:
                outer += ['-'+prefix+'_ksp_type','gmres','-'+prefix+'_ksp_rtol','1e-4',
                          '-'+prefix+'_ksp_max_it',str(limit)]
            return outer
        if mode == 'added_mass':
            return outer + ['-pc_recipe','added_mass','-pc_plan_schur_approx','nodal',
                            '-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type','lower']
        approx = mode.split('_')[-1]
        velocity_solver = 'twolevel' if mode.startswith('twolevel_') else 'coupled'
        ordering_prefix = ('-fieldsplit_dynamics_fieldsplit_velocity_' +
                           ('mg_levels_' if velocity_solver == 'twolevel' else ''))
        return outer + ['-pc_recipe','hybrid','-pc_plan_schur_approx',approx,
                        '-pc_plan_velocity_solver',velocity_solver,
                        '-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type','lower',
                        ordering_prefix+'sub_pc_factor_mat_ordering_type',ordering]

    def read_fields(directory, stem, ranks, names):
        fields = {name:{} for name in names}
        for rank in range(ranks):
            path = directory/(stem+(f'_rank{rank}' if ranks>1 else '')+'.vtu')
            arrays = {a.attrib['Name']: (a.text or '').split()
                      for a in ET.parse(path).findall('.//PointData/DataArray')}
            ids = [int(v) for v in arrays['mesh_node_id']]
            owners = [int(v) for v in arrays['owner']]
            assert ids and len(ids)==len(owners), path
            for name in names:
                values = [float(v) for v in arrays[name]]
                components, remainder = divmod(len(values),len(ids))
                assert components in (1,3) and remainder==0, (path,name)
                for i,node in enumerate(ids):
                    if owners[i]==rank:
                        assert node not in fields[name], (path,name,node)
                        v = values[i*components:(i+1)*components]
                        assert all(math.isfinite(x) for x in v), (path,name,node)
                        fields[name][node] = v
        return fields

    def compare_fields(reference, actual, ranks, steps):
        peaks = {}
        for step in range(4,steps+1,4):
            for suffix,names in [('',('velocity','pressure','mesh_displacement')),
                                 ('_solid',('velocity','displacement'))]:
                stem = f'tube_step{step}{suffix}'
                first = read_fields(reference,stem,ranks,names)
                second = read_fields(actual,stem,ranks,names)
                for name in names:
                    assert first[name] and first[name].keys()==second[name].keys(), (stem,name)
                    key = ('wall_' if suffix else 'fluid_')+name
                    row = peaks.setdefault(key,dict(peak=0.,difference=0.))
                    for node,v in first[name].items():
                        w = second[name][node]
                        assert len(v)==len(w), (stem,name,node)
                        row['peak'] = max(row['peak'],*(abs(i) for i in v))
                        row['difference'] = max(row['difference'],*(abs(i-j) for i,j in zip(v,w)))
        ratios = {k:v['difference']/v['peak'] if v['peak'] else
                  (0. if v['difference']==0. else float('inf')) for k,v in peaks.items()}
        return ratios

    def audit(log, steps, dofs):
        norms, reports, accepted, field_counts = [], [], [], {}
        for line in log.read_text().splitlines():
            row = dict(re.findall(r'(\w+)=([^\s]+)',line))
            if line.startswith('linear_residual '):
                n,b = float(row['norm']),float(row['rhs_norm'])
                assert math.isfinite(n) and math.isfinite(b) and min(n,b)>=0., row
                assert int(row['solve'])==1+sum(v['step']==len(accepted)+1 for v in norms), row
                norms.append(dict(step=len(accepted)+1,norm=n,rhs=b,
                                  ratio=n/max(1e-23,1e-10*b),fields={}))
            elif line.startswith('linear_field_residual '):
                assert norms and row['name'] not in norms[-1]['fields'], row
                assert float(row['constraint_max'])==0. and float(row['residual_scale'])==1., row
                v = float(row['rms'])
                assert math.isfinite(v) and v>=0., row
                norms[-1]['fields'][row['name']]=v
            elif line.startswith('field_residual '):
                n = int(row['equation_rows'])
                assert n>0 and int(row['constraint_rows'])==0, row
                assert field_counts.setdefault(row['name'],n)==n, row
            elif line.startswith('solver_report '):
                assert int(row['dofs'])==dofs and min(int(row['snes_reason']),int(row['ksp_reason']))>0, row
                assert int(row['domain_rejections'])==0, row
                reports.append(row)
            elif line.startswith('fsi_step='):
                step = len(accepted)+1
                stage = (step-1+(1. if step==1 else 2/3))/32
                pressure = 80*stage**3*(10+stage*(-15+6*stage))
                assert int(row['fsi_step'])==step and abs(float(row['time'])-step/32)<1e-14, row
                assert abs(float(row['evaluation_time'])-stage)<1e-14, row
                assert abs(float(row['applied_pressure'])-pressure)<1e-11, row
                accepted.append(row)
            elif line.startswith(('linear_residual_unavailable','linear_iteration_limit_residual ',
                                  'step_retry=','error=','EONSim rank 0:')):
                raise ValueError(line)
        assert len(accepted)==len(reports)==steps, (len(accepted),len(reports),steps)
        assert len(norms)>0 and sum(int(r['linear_completed']) for r in reports)==len(norms)
        for i,r in enumerate(reports,1):
            assert sum(n['step']==i for n in norms)==int(r['linear_completed']), r
        assert set(field_counts)=={'velocity','pressure','structure','mesh'} and sum(field_counts.values())==dofs
        for n in norms:
            assert n['fields'].keys()==field_counts.keys(), n
            reconstructed = math.sqrt(sum(field_counts[k]*v*v for k,v in n['fields'].items()))
            assert math.isclose(reconstructed,n['norm'],rel_tol=2e-12,abs_tol=1e-300), n
        linear_seconds = sum(float(r['linear_seconds']) for r in reports)
        assert math.isfinite(linear_seconds) and linear_seconds>=0.
        return dict(steps=steps,corrections=len(norms),worst_ratio=max(n['ratio'] for n in norms),
                    within_target=sum(n['ratio']<=1.00001 for n in norms),
                    outer_iterations=sum(int(r['linear_iterations']) for r in reports),
                    linear_seconds=linear_seconds, correction_history=norms)

    modes = ('direct','physics_lower','coupled_diagonal','coupled_nodal','twolevel_nodal','added_mass')
    for grid,ranks,dofs,ordering in [('s24-r3-w2-a6',1,1027,'natural'),
                                    ('s48-r4-w4-a6',2,3024,'rcm')]:
        case = work/grid/'input'
        case.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive,'r:xz') as bundle:
            # Copy only the three named regular files; never extract arbitrary paths.
            for filename in ('case.json','fluid.msh','solid.msh'):
                candidates = [m for m in bundle.getmembers() if m.isfile() and
                              Path(m.name).name==filename and any(
                                  part==grid or part.startswith(grid+'-') for part in Path(m.name).parts[:-1])]
                assert len(candidates)==1, (grid,filename,[m.name for m in candidates])
                (case/filename).write_bytes(bundle.extractfile(candidates[0]).read())
        config = json.loads((case/'case.json').read_text())
        expected = dict(pressure=80.,dt=1/32,steps=32,young=400000.,poisson=.45,
                        density=1060.,solid_density=1100.,viscosity=.004,
                        output_interval=4,stabilization_model='volume')
        assert all(config['fsi'].get(k)==v for k,v in expected.items()), config['fsi']
        assert config['time']==dict(scheme='generalized_alpha',rho_infinity=.5)
        part = work/grid/'partition'
        code,_ = launch([exe,'-case',case/'case.json','-prepare',part,'-parts',ranks],
                        case,work/grid/'prepare.log')
        assert code==0, (grid,'partition')
        result = dict(grid=grid,ranks=ranks,dofs=dofs,ordering=ordering,
                      input_hashes={f:digest(case/f) for f in ('case.json','fluid.msh','solid.msh')},
                      runs=[])
        summary['cases'].append(result)
        reference = work/grid/'full-direct'

        def run(mode, steps, label):
            out = work/grid/label
            out.mkdir(exist_ok=True)
            log = out/'solve.log'
            flags = options(mode,ordering)
            # Complete-fluid Schur performs nested fluid solves at every
            # structural iteration. Keep all 32 steps and accuracy gates;
            # account for its measured work instead of reducing that coverage.
            timeout = 600 if mode=='added_mass' and steps==32 else 130
            rec = dict(mode=mode,label=label,flags=flags,steps_requested=steps,
                       execution_budget_seconds=timeout)
            result['runs'].append(rec)
            started = time.monotonic()
            try:
                command = [mpi,'--map-by','core','--bind-to','core','-n',str(ranks),
                           exe,'-case',case/'case.json','-partition',part,'-output',out/'tube.vtu',
                           '-solver_report','-linear_report','-stop_after',steps,*flags]
                code,elapsed = launch(command,out,log,timeout=timeout)
                rec.update(exit_code=code,wall_seconds=elapsed,log_sha256=digest(log))
                assert code==0, ('nonzero launcher exit',code)
                assert log.read_text().splitlines().count('status=success')==1, 'missing solver success'
                rec.update(audit(log,steps,dofs))
                assert rec['within_target']==rec['corrections'], ('true residual gate',rec['worst_ratio'])
                if mode!='direct' or out!=reference:
                    ratios=compare_fields(reference,out,ranks,steps)
                    rec['field_relative_peaks']=ratios
                    assert all(v<=2e-6 for v in ratios.values()), ('field gate',ratios)
                rec['status']='passed'
            except (AssertionError,ValueError,KeyError,IndexError,OSError,subprocess.TimeoutExpired) as exc:
                rec.update(status='failed',error=str(exc),timeout=isinstance(exc,subprocess.TimeoutExpired))
                rec.setdefault('wall_seconds',time.monotonic()-started)
                if log.exists(): rec.setdefault('log_sha256',digest(log))
                summary['failures'].append(dict(grid=grid,label=label,error=str(exc)))
            # Keep detailed per-correction evidence in JSON; emit compact lines
            # in the CTest log for remote review even if a later case fails.
            print('arterial_block_run '+json.dumps(dict(grid=grid,**{k:v for k,v in rec.items()
                  if k not in ('correction_history','flags')}),allow_nan=False),flush=True)
            (work/'results.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
            return rec

        passed = []
        for mode in modes:
            rec=run(mode,32,'full-'+mode)
            if rec['status']=='passed': passed.append(mode)
        # One warmup and three interleaved four-step samples, same diagnostics
        # and output for each configuration. No speed threshold in CI.
        if 'direct' not in passed:
            continue
        for mode in passed:
            run(mode,4,'warmup-'+mode)
        for repeat in range(3):
            sequence=passed[repeat%len(passed):]+passed[:repeat%len(passed)]
            for mode in sequence:
                run(mode,4,f'timing-{repeat+1}-{mode}')
        result['medians']={}
        for mode in passed:
            rows=[r for r in result['runs'] if r['mode']==mode and
                  r['label'].startswith('timing-') and r['status']=='passed']
            if len(rows)==3:
                result['medians'][mode]=dict(samples=3,
                    wall_seconds=statistics.median(r['wall_seconds'] for r in rows),
                    linear_seconds=statistics.median(r['linear_seconds'] for r in rows),
                    outer_iterations=statistics.median(r['outer_iterations'] for r in rows))
        print('arterial_block_medians '+json.dumps(dict(grid=grid,ranks=ranks,
              medians=result['medians']),allow_nan=False),flush=True)
    (work/'results.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    assert not summary['failures'], summary['failures']
    return dict(cases=[dict(grid=c['grid'],ranks=c['ranks'],medians=c.get('medians',{}))
                       for c in summary['cases']])


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
        report['arterial_block'] = verify_arterial_block(args.executable,args.mpiexec,work/'arterial-block')
    (work/'metrics.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
