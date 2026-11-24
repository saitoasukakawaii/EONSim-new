"""Reintegrate periodic tube fields on fixed and expanding outlet planes and compare circular-meridian modes."""
import argparse
import cmath
import csv
from dataclasses import asdict
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys

import numpy as np
from harmonic_eon import SurfaceAudit, digest
from perfused_eon import history, periodic_modes
from perfused_svfsi import deck, native_waveform, observed_loads, read_native_fields
from perfused_tube import AMPLITUDE, C, RD, RP
from scaled_tube import problem
from audit_reflection import measured_ring_strains
from compare_harmonic import cpair, positions
from svfsi_history import check_convergence


def check_inputs(path, report, solver):
    m = problem('arterial')[0]
    n, cycles, hz = (report[k] for k in ('steps_per_cycle', 'cycles', 'frequency_hz'))
    total = n*cycles
    warm = total-2*n
    peak = report['full_amplitude']
    mean = report.get('full_mean', 0.)
    moving = report.get('outlet_tangential_motion',False)
    if (report['parameters'] != asdict(m) or report['full_rcr_si'] != [RP,RD,C]
            or report['quarter_fraction'] != .25 or not peak > 0):
        raise ValueError('Changed tube or terminal parameters')
    for name, sha in report['files'].items():
        if digest(path/name) != sha:
            raise ValueError(f'Input or history changed at {path/name}')
    if solver == 'EONSim':
        full = json.loads((path/'measure.json').read_text())
        first = json.loads((path/'warm.json').read_text())
        first['fsi']['output_interval'] = full['fsi']['output_interval']
        f = full['fsi']
        if full != first or f['dt'] != 1/hz/n or f['steps'] != total:
            raise ValueError('Changed FSI integration or restart deck')
        if f['inlet']['flow_rate'] != dict(profile='circle', axis=0, center=[0,0,0], radius=m.radius,
                mean=mean/4, amplitude=peak/4, period=1/hz):
            raise ValueError('Different imposed inlet')
        expected = dict(tag=2,proximal_resistance=4*RP,distal_resistance=4*RD,compliance=C/4,
                        distal_pressure=0.,initial_capacitor_pressure=0.)
        if moving:
            expected['moving_plane_axis']=0
        domains = f['domains']
        if (domains['rcr_outlet'] != expected or f['stabilization_model'] != report['model']
                or domains['pressure_tags'] != [2]
                or any(f[key] != v for key,v in dict(young=m.young,poisson=m.poisson,density=m.fluid_density,
                                                       solid_density=m.solid_density,viscosity=m.viscosity).items())):
            raise ValueError('Different material or RCR')
        fixed = {entry['tag'] for entry in domains['solid_constraints'] if set(entry['components']) == {0,1,2}}
        fixed_ends={11} if moving else {11,12}
        if fixed != (fixed_ends | ({13,14} if report['rigid'] else set())):
            raise ValueError('Different elastic end constraint')
        for label,steps in [('warm',range(1,warm+1)),('measure',range(warm+1,total+1))]:
            log=(path/(label+'.log')).read_text()
            if [int(i) for i in re.findall(r'^fsi_step=(\d+) ',log,re.M)]!=list(steps) or log.count('status=success')!=1:
                raise ValueError('Incomplete accepted EONSim steps')
        table = history(path/f'tube_restart{warm}.csv')
        if [r['step'] for r in table] != list(range(warm+1,total+1)):
            raise ValueError('Missing measured RCR step')
        for r in table:
            pc = r['stage_capacitor_pressure']
            q = r['stage_rcr_flow']
            if max(abs(C*r['stage_capacitor_rate']/4-q+pc/(4*RD))/(peak/4),
                   abs(pc+4*RP*q-r['stage_rcr_pressure'])/(peak*(RP+RD))) > 2e-6:
                raise ValueError('Stage capacitor or port residual too large')
        return table
    import compare_svfsi_wall
    eqs = ('NS',) if report['rigid'] else ('FS','MS')
    if (deck(compare_svfsi_wall,m,total,1/hz/n,1 if moving else n//report['samples_per_cycle'],report['rigid'],moving) != (path/'svFSI.inp').read_text()
            or native_waveform(1/hz,mean,peak) != (path/'flow.fcs').read_text()):
        raise ValueError('Native deck disagrees with experiment')
    log=(path/'1-procs/histor.dat').read_text()
    for eq in eqs:
        if list(check_convergence(log,total,eq)) != report['convergence'][eq]:
            raise ValueError('Incomplete native solve')
    table = np.loadtxt(path/'1-procs/RCR.dat').tolist()
    if len(table)!=total:
        raise ValueError('Incomplete native port history')
    loads = observed_loads((path/'solve.log').read_text(),table,report['model'],1/hz,n,peak*(RP+RD),report.get('previous_port_pressures_pa'))
    if loads != report.get('applied_load'):
        raise ValueError('Applied native pressure differs from receipt')
    return table


def verify_native_circuit(path, report, mesh, audit, rows):
    """Rebuild the piecewise-linear-in-flow capacitor evolution and both geometry time levels."""
    dt = 1/(report['frequency_hz']*report['steps_per_cycle'])
    decay = -math.expm1(-dt/(RD*C))
    peak = report['full_amplitude']
    pressure_scale = peak*(RP+RD)
    moving = report.get('outlet_tangential_motion', False)
    previous_area = None
    previous_flow = previous_pc = integrated_pc = 0.
    max_circuit = max_flow = max_load = max_lag = 0.
    snapshots = hashlib.sha256()
    for step, (t,pc,pb,q) in enumerate(rows, 1):
        if abs(t-step*dt)>6e-7*max(1.,abs(t)):
            raise ValueError('Mismatched native capacitor time')
        old = previous_flow
        if moving:
            vtu = path/f'1-procs/result_{step:03d}.vtu'
            snapshots.update(bytes.fromhex(digest(vtu)))
            state = audit.array(read_native_fields(vtu,mesh,report['rigid'])[0])
            face = audit.ports[2][:,:3]
            coordinates = (audit.reference+state[:,:3])[face]
            edges = coordinates[:,1:]-coordinates[:,:1]
            areas = .5*np.abs(np.cross(edges[:,0],edges[:,1])[:,0])
            if previous_area is None:
                initial = audit.reference[face]
                previous_area = .5*np.abs(np.cross(initial[:,1]-initial[:,0],initial[:,2]-initial[:,0])[:,0])
            if min(areas)<=0 or np.ptp(coordinates[:,:,0])>1e-13:
                raise ValueError('Invalid physical outlet face during independent circuit replay')
            normal_velocity = np.mean(state[face,3],axis=1)
            native_q = previous_area@normal_velocity
            previous_flow = areas@normal_velocity
            max_flow=max(max_flow,4*abs(native_q-q)/peak)
            max_lag=max(max_lag,4*abs(native_q-previous_flow)/peak)
            previous_area=areas
            old_pressure=previous_pc+4*RP*old
            max_load=max(max_load,abs(old_pressure-report['previous_port_pressures_pa'][step-1])/pressure_scale)
        else:
            previous_flow=q
        integrated_pc=(1-decay)*integrated_pc+4*RD*(decay*old+(1-RD*C*decay/dt)*(q-old))
        max_circuit=max(max_circuit,abs(integrated_pc-pc)/pressure_scale,abs(pc+4*RP*q-pb)/pressure_scale)
        previous_pc=pc
    if (max(max_circuit,max_flow,max_load)>2e-6 or
            (moving and abs(max_lag-report['maximum_geometry_flux_change_over_inlet'])>2e-10)):
        raise ValueError('Independent native circuit, lagged cap flux or prior pressure disagrees')
    return dict(recurrence_or_ohm_defect_over_RQ=max_circuit,lagged_flow_defect_over_inlet=max_flow,
                prior_load_defect_over_RQ=max_load,maximum_geometry_effect_over_inlet=max_lag,
                all_step_vtu_hash_digest=snapshots.hexdigest() if moving else None)


def verify_raw(path, report, solver):
    from study_hydrostatic_fsi import recovered_state
    from study_rigid_tube import read_mesh
    history_rows=check_inputs(path, report, solver)
    meshes=[read_mesh(path/name) for name in ('fluid.msh','solid.msh')]
    audit=SurfaceAudit(meshes[0],(1,2,3))
    m=problem('arterial')[0]
    n=report['steps_per_cycle']
    warm=(report['cycles']-2)*n
    peak=report['full_amplitude']
    pressure_scale=peak*(RP+RD)
    worst=dict(flux_over_inlet=0., pressure_over_RQ=0., area_over_static=0., volume_relative=0.)
    cap_stresses = []
    for s in report['observations']:
        step=s['step']
        if solver=='EONSim':
            stem=f'tube_restart{warm}_step{step}'
            state=[]
            for k,(suffix,mesh) in enumerate(zip(('','_solid'),meshes)):
                if digest(path/(stem+suffix+'.vtu'))!=s['file_sha256'][suffix]:
                    raise ValueError('Changed EONSim snapshot')
                state.append(recovered_state(path,stem+suffix,mesh,bool(k),1))
            row=history_rows[step-warm-1]
            pc,pb=row['endpoint_capacitor_pressure'],row['endpoint_rcr_pressure']
        else:
            snapshot=path/f'1-procs/result_{step:03d}.vtu'
            if digest(snapshot)!=s['file_sha256']:
                raise ValueError('Changed native snapshot')
            state=read_native_fields(snapshot,meshes,report['rigid'])
            _,pc,pb,_=history_rows[step-1]
        field=audit.array(state[0])
        faces=audit.observe(field,pb,m.viscosity)
        cap_stresses.append(-faces[2]['mean_normal_traction'])
        xs,area=measured_ring_strains(meshes[1],state[1])
        if xs!=report['sections']:
            raise ValueError('Different axial observation coordinates')
        for name,k,sign in [('full_inlet',1,-1),('full_outlet',2,1),('full_wall_flux',3,1)]:
            worst['flux_over_inlet']=max(worst['flux_over_inlet'],abs(4*sign*faces[k]['outward_flow']-s[name])/peak)
        for x,y in [(pc,s['capacitor_pressure']),(pb,s['circuit_pressure']),
                    (faces[1]['mean_pressure'],s['inlet_mean_pressure']),(faces[2]['mean_pressure'],s['outlet_mean_pressure'])]:
            worst['pressure_over_RQ']=max(worst['pressure_over_RQ'],abs(x-y)/pressure_scale)
        worst['area_over_static']=max(worst['area_over_static'],
            max(abs(a-b) for a,b in zip(area,s['area_strain']))/m.lame_area_strain(pressure_scale))
        worst['volume_relative']=max(worst['volume_relative'],abs(4*audit.volume(field)/s['full_volume']-1))
    if max(worst.values())>1e-8:
        raise ValueError(f'Raw fields differ from reported measurements in {path}: {worst}')
    terminal = []
    for step, row in enumerate(history_rows[-2*n:], warm+1):
        if solver == 'EONSim':
            pc, pb, q = [row[k] for k in ('endpoint_capacitor_pressure','endpoint_rcr_pressure','endpoint_rcr_flow')]
        else:
            _, pc, pb, q = row
        terminal.append([step, pc, pb, 4*q])
    native_trace = verify_native_circuit(path,report,meshes,audit,history_rows) if solver=='svFSI' else None
    return worst, cap_stresses, terminal, native_trace


def pack(root, reference_scripts, native_binary):
    sys.path.append(str(reference_scripts.resolve()))
    groups=[('perfused-eon','EONSim',root/'regular-tet-eonsim'),
            ('perfused-plane-eon','EONSim',root/'moving-plane-eonsim'),
            ('perfused-sv','svFSI',native_binary),
            ('perfused-endpoint','svFSI',root/'svfsi-observer-build/bin/svFSI'),
            ('perfused-plane-sv','svFSI',native_binary),
            ('perfused-plane-stage','svFSI',root/'sv-rcr-stage-build/bin/svFSI'),
            ('perfused-stage','svFSI',root/'sv-rcr-stage-build/bin/svFSI'),
            ('perfused-forward-eon','EONSim',root/'moving-plane-eonsim'),
            ('perfused-forward-sv','svFSI',native_binary),
            ('perfused-forward-stage','svFSI',root/'sv-rcr-stage-build/bin/svFSI')]
    data=dict(meridians=[],steady_meridians=[],runs=[])
    for group,solver,exe in groups:
        for path in sorted((root/group).glob('s*/result.json')):
            d=json.loads(path.read_text())
            if digest(exe)!=d['executable_sha256']:
                raise ValueError('Changed solver binary')
            defects, stresses, terminal, native_trace = verify_raw(path.parent, d, solver)
            data['runs'].append(dict(group=group,case=path.parent.name,solver=solver,report=d,
                                      raw_defect=defects,outlet_normal_stress_pressure_pa=stresses,
                                      endpoint_port_steps_pc_pb_full_q=terminal,native_trace=native_trace))
    sources=[*(root/'perfused-meridian').glob('x*.json'),*(root/'perfused-plane-meridian').glob('x*.json'),
             *(root/'perfused-forward-meridian').glob('x*.json')]
    for f in sorted(sources):
        r=json.loads(f.read_text())
        steady = f.parent.name == 'perfused-forward-meridian'
        expected = [0.] if steady else [.5,1.,2.]
        if [v['frequency_hz'] for v in r['runs']] != expected or not (r['parameters']==asdict(problem('arterial')[0]) and
                r['full_rcr_si']==[RP,RD,C] and r['amplitude_m3_s']==AMPLITUDE and len(r['sections'])==97):
            raise ValueError('Incomplete reference or different physical system')
        data['steady_meridians' if steady else 'meridians'].append(dict(case=f.stem,sha256=digest(f),report=r))
    return data


def references(data):
    grids={}
    for item in data['meridians']:
        r=item['report']
        for s in r['runs']:
            errors=[s[k] for k in ('relative_complex_power','relative_flux_balance','relative_terminal_power',
                                   'relative_circuit_pressure','kinematic_error','max_free_row_residual')]
            if not np.isfinite(errors).all() or max(errors)>3e-8:
                raise ValueError('Unbalanced harmonic reference')
            grids.setdefault((r['rigid'],r.get('outlet_tangential_motion',False),s['frequency_hz']),[]).append((r,s))
    rows=[]
    for key, levels in sorted(grids.items()):
        levels.sort(key=lambda pair:pair[0]['unknowns'])
        if len(levels)<2:raise ValueError('At least two spatial grids required')
        for ix,(grid,s) in enumerate(levels):
            peak=grid['amplitude_m3_s'];p0=peak*(RP+RD)
            area0=problem('arterial')[0].lame_area_strain(p0)
            previous=levels[ix-1][1] if ix else None
            qout=cpair(s['outlet_phasor_m3_s']);pin=cpair(s['inlet_mean_pressure_pa']);a=cpair(s['area_strain'][48])
            rows.append(dict(rigid=key[0],moving_plane=key[1],hz=key[2],unknowns=grid['unknowns'],outlet_gain=abs(qout)/peak,
                        outlet_phase_deg=math.degrees(cmath.phase(qout)),inlet_pressure_amplitude_pa=abs(pin),
                        inlet_pressure_phase_deg=math.degrees(cmath.phase(pin)),mid_area_amplitude_pct=100*abs(a),
                        previous_q_change_pct_inlet=None if not previous else 100*abs(qout-cpair(previous['outlet_phasor_m3_s']))/peak,
                        previous_pin_change_pct_RQ=None if not previous else 100*abs(pin-cpair(previous['inlet_mean_pressure_pa']))/p0,
                        previous_area_change_pct_static=None if not previous else 100*max(abs(cpair(a)-cpair(b))
                            for a,b in zip(s['area_strain'],previous['area_strain']))/area0,
                        mass_defect=s['relative_flux_balance'],complex_power_defect=s['relative_complex_power']))
    return grids,rows


def tables(data):
    grids,meridian=references(data)
    results=[]
    for run in data['runs']:
        r=run['report']
        samples=r['observations']
        hz, peak, n, nobs=(r[k] for k in ('frequency_hz','full_amplitude','steps_per_cycle','samples_per_cycle'))
        moving=r.get('outlet_tangential_motion',False)
        grid,reference=grids[r['rigid'],moving,hz][-1]
        fixed_ends=(0,) if moving else (0,-1)
        p0=peak*(RP+RD)
        area0=problem('arterial')[0].lame_area_strain(p0)
        if nobs<8 or len(samples)!=2*nobs or max(r['checks'].values())>2e-6:
            raise ValueError('Incomplete measured periods or rejected raw control')
        warm=(r['cycles']-2)*n
        for i,s in enumerate(samples,1):
            if (s['step']!=warm+i*n//nobs or abs(s['time']-s['step']/(n*hz))>1e-11/hz
                    or abs(s['full_inlet']-r.get('full_mean',0.)-peak*math.sin(2*np.pi*hz*s['time']))>2e-6*peak
                    or max(abs(s['area_strain'][j]) for j in fixed_ends)>1e-10 or len(s['area_strain'])!=len(r['sections'])):
                raise ValueError('Noncoincident time, axial stations or boundary')
        phasors,period_change=periodic_modes(samples,hz,peak,p0,area0)
        if max(abs(v-r['last_cycle_change'][k]) for k,v in period_change.items())>1e-11:
            raise ValueError('Changed periodicity result')
        passed=max(period_change.values())<1e-3
        if r['periodic_pass']!=passed:
            raise ValueError('Inconsistent periodic acceptance')
        for k,v in phasors.items():
            if not np.allclose(v,r['phasors'][k],atol=1e-21,rtol=3e-11):
                raise ValueError('Stored Fourier mode differs from time series')
        waveform_change=0.
        for earlier,later in zip(samples[:nobs],samples[nobs:]):
            for name in ('full_inlet','full_outlet','full_wall_flux','inlet_mean_pressure','outlet_mean_pressure','circuit_pressure','capacitor_pressure','area_strain'):
                denom=area0 if name=='area_strain' else (peak if name.startswith('full_') else p0)
                delta=np.asarray(earlier[name])-np.asarray(later[name])
                waveform_change=max(waveform_change,float(np.max(abs(delta)))/denom)
        passed=passed and waveform_change<1e-3
        scale=peak/grid['amplitude_m3_s']
        qi,qo,qw,pi,po,pc=(cpair(phasors[k]) for k in ('full_inlet','full_outlet','full_wall_flux','inlet_mean_pressure','outlet_mean_pressure','circuit_pressure'))
        exact_z=RP+RD/(1+2j*np.pi*hz*RD*C)
        ids=positions(grid['sections'],r['sections'])
        mid=positions(r['sections'],[r['parameters']['length']/2])[0]
        a=[cpair(v) for v in phasors['area_strain']]
        aref=[scale*cpair(reference['area_strain'][i]) for i in ids]
        pin_ref=scale*cpair(reference['inlet_mean_pressure_pa'])
        qo_ref=scale*cpair(reference['outlet_phasor_m3_s'])
        residual=100*max(abs(s['full_inlet']-s['full_outlet']-s['full_wall_flux']) for s in samples)/peak
        # The constant lumen volume can be much larger than its oscillatory part.
        # Remove its mean before reconstructing the fundamental geometric storage rate.
        cycle=samples[-nobs:]
        theta=np.exp(-2j*np.pi*hz*np.array([a['time'] for a in cycle]))
        rotation=peak/(2*(theta@np.array([a['full_inlet'] for a in cycle]))/nobs)
        volume=np.array([a['full_volume'] for a in cycle])
        volume_mode=rotation*2*(theta@(volume-volume.mean()))/nobs
        storage_rate=2j*np.pi*hz*volume_mode
        stresses = np.asarray(run['outlet_normal_stress_pressure_pa'])
        if stresses.shape != (2*nobs,) or not np.isfinite(stresses).all():
            raise ValueError('Incomplete recovered normal traction on the outlet')
        stress_mode = rotation*2*(theta@stresses[-nobs:])/nobs
        capacitor=cpair(phasors['capacitor_pressure'])
        complex_power=pc*qo.conjugate()/2
        resistance_power=(RP*abs(qo)**2+abs(capacitor)**2/RD)/2
        reactive_power=-2*np.pi*hz*C*abs(capacitor)**2/2
        factor=2/3+(1/3)*cmath.exp(-2j*np.pi/n)
        def degrees(z):return math.degrees(cmath.phase(z))
        results.append(dict(group=run['group'],solver=run['solver'],model=r['model'],case=run['case'],rigid=r['rigid'],moving_plane=moving,hz=hz,
                    steps_per_cycle=n,cycles=r['cycles'],samples_per_cycle=nobs,peak_full_m3_s=peak,mean_full_m3_s=r.get('full_mean',0.),periodic_pass=passed,meridian_unknowns=grid['unknowns'],
                    cycle_change_pct_scale=100*max(period_change.values()),waveform_change_pct_scale=100*waveform_change,outlet_gain=abs(qo/qi),outlet_phase_deg=degrees(qo/qi),
                    ref_outlet_gain=abs(qo_ref)/peak,outlet_complex_gap_pct_inlet=100*abs(qo-qo_ref)/peak,
                    wall_flux_gain=abs(qw/qi),inlet_mean_pressure_pa=abs(pi),inlet_pressure_phase_deg=degrees(pi/qi),
                    ref_inlet_mean_pressure_pa=abs(pin_ref),inlet_pressure_gap_pct_RQ=100*abs(pi-pin_ref)/p0,
                    circuit_pressure_pa=abs(pc),outlet_mean_pressure_pa=abs(po),circuit_pressure_phase_deg=degrees(pc/qi),
                    circuit_impedance_complex_gap_pct=100*abs(pc/qo-exact_z)/abs(exact_z),
                    outlet_mean_minus_circuit_pct_RQ=100*abs(po-pc)/p0,
                    stage_outlet_mean_minus_endpoint_circuit_pct_RQ=100*abs(factor*po-pc)/p0,
                    fluid_to_circuit_pressure_ratio_real=(po/pc).real,fluid_to_circuit_pressure_ratio_imag=(po/pc).imag,
                    endpoint_load_prediction_real=(1/factor).real,endpoint_load_prediction_imag=(1/factor).imag,
                    normal_stress_minus_circuit_pct_RQ=100*abs(stress_mode-pc)/p0,
                    stage_normal_stress_minus_endpoint_circuit_pct_RQ=100*abs(factor*stress_mode-pc)/p0,
                    mid_area_amplitude_pct=100*abs(a[mid]),mid_area_phase_deg=None if r['rigid'] else degrees(a[mid]/qi),
                    ref_mid_area_amplitude_pct=100*abs(aref[mid]),outlet_area_amplitude_pct=100*abs(a[-1]),ref_outlet_area_amplitude_pct=100*abs(aref[-1]),max_complex_area_gap_pct_static=100*max(abs(v-w) for v,w in zip(a,aref))/area0,
                    storage_rate_gap_pct_inlet=100*abs(storage_rate-qw)/peak,
                    real_terminal_power_W=complex_power.real,reactive_terminal_power_W=complex_power.imag,
                    harmonic_power_identity_gap_pct=100*abs(complex_power-complex(resistance_power,reactive_power))/(.5*p0*peak),
                    sampled_mass_defect_pct_inlet=residual,fundamental_mass_defect_pct_inlet=100*abs(qi-qo-qw)/peak))
    return meridian,results


def direct_pairs(data, accepted):
    """Compare measured complex modes on identical tetrahedra and independent flow/pressure scales."""
    grouped={}
    for item in data['runs']:
        r=item['report']
        if (item['group'],item['case']) not in accepted:
            continue
        mesh=tuple(r['files'][k] for k in ('fluid.msh','solid.msh'))
        key=(mesh,r['rigid'],r['frequency_hz'],r['steps_per_cycle'],r['full_amplitude'],r.get('full_mean',0.),r['samples_per_cycle'])
        grouped.setdefault(key,[]).append(item)
    pairs=[]
    for (_,rigid,hz,n,peak,mean,nobs),items in grouped.items():
        p0=peak*(RP+RD)
        area_scale=problem('arterial')[0].lame_area_strain(p0)
        for i,first in enumerate(items):
            for second in items[i+1:]:
                x,y=first['report'],second['report']
                moving_x=x.get('outlet_tangential_motion',False)
                moving_y=y.get('outlet_tangential_motion',False)
                if moving_x!=moving_y:
                    if (x['executable_sha256']!=y['executable_sha256'] or x['model']!=y['model']
                            or first['solver']!=second['solver']):
                        continue
                    kind='outlet end constraint'
                elif first['solver']!=second['solver']:
                    kind='intercode'
                elif x['model']==y['model']:
                    if x['executable_sha256']==y['executable_sha256']:
                        continue
                    kind='build control'
                elif first['solver']=='svFSI':
                    for inp in ('svFSI.inp','flow.fcs','profile.dat'):
                        if x['files'][inp]!=y['files'][inp]:
                            raise ValueError('Native intervention changed the input '+inp)
                    kind='native traction or observer'
                else:
                    kind='EONSim stabilization'
                if x['sections']!=y['sections']:
                    raise ValueError('Different axial stations on identical physical grid')
                def z(r,key):return cpair(r['phasors'][key])
                qx,qy=z(x,'full_outlet'),z(y,'full_outlet')
                px,py=z(x,'inlet_mean_pressure'),z(y,'inlet_mean_pressure')
                ca,cb=[cpair(v) for v in x['phasors']['area_strain']],[cpair(v) for v in y['phasors']['area_strain']]
                errors=[100*abs(b-a)/area_scale for a,b in zip(ca,cb)]
                worst=max(range(len(errors)),key=errors.__getitem__)
                pairs.append(dict(comparison=kind,first_group=first['group'],first_case=first['case'],first_model=x['model'],
                                  second_group=second['group'],second_case=second['case'],second_model=y['model'],
                                  rigid=rigid,first_moving=moving_x,second_moving=moving_y,hz=hz,steps=n,samples_per_cycle=nobs,inlet_peak_m3_s=peak,inlet_mean_m3_s=mean,
                                  outlet_complex_difference_pct_inlet=100*abs(qy-qx)/peak,
                                  outlet_gain_difference_percentage_points=100*(abs(qy)-abs(qx))/peak,
                                  outlet_phase_difference_deg=math.degrees(cmath.phase(qy/qx)),
                                  inlet_mean_pressure_difference_pct_RQ=100*abs(py-px)/p0,
                                  circuit_difference_pct_RQ=100*abs(z(y,'circuit_pressure')-z(x,'circuit_pressure'))/p0,
                                  max_complex_section_difference_pct_static=errors[worst],worst_station_m=x['sections'][worst]))
    return pairs


def forward_flow(data, accepted):
    """Compare the cycle mean with a separate steady Stokes–elastic–resistance solve."""
    refs = {}
    for item in data.get('steady_meridians', []):
        grid = item['report']
        row, = grid['runs']
        mean = grid['amplitude_m3_s']
        pressure = (RP + RD)*mean
        checks = [row[k] for k in ('relative_complex_power','relative_flux_balance','relative_terminal_power',
                                   'relative_circuit_pressure','kinematic_error','max_free_row_residual')]
        if (row['frequency_hz'] != 0 or not np.isfinite(checks).all() or max(checks)>3e-8
                or abs(cpair(row['outlet_phasor_m3_s'])/mean - 1)>1e-8
                or abs(cpair(row['outlet_load_pa'])/pressure - 1)>1e-8):
            raise ValueError('Unbalanced steady meridian')
        key = grid['rigid'], grid['outlet_tangential_motion']
        refs.setdefault(key, []).append((grid, row))
    results = []
    for item in data['runs']:
        r = item['report']
        mean = r.get('full_mean', 0.)
        if mean <= 0. or (item['group'],item['case']) not in accepted:
            continue
        key = r['rigid'], r['outlet_tangential_motion']
        levels = sorted(refs[key], key=lambda g:g[0]['unknowns'])
        if len(levels)<2:
            raise ValueError('Forward flow requires two independent steady reference grids')
        grid, ref = levels[-1]
        coarse_grid, old = levels[-2]
        if grid['sections'] != coarse_grid['sections']:
            raise ValueError('Steady meridian observation coordinates differ')
        n, nobs = r['steps_per_cycle'], r['samples_per_cycle']
        cycle = r['observations'][-nobs:]
        flow = np.asarray([s['full_outlet'] for s in cycle])
        area = np.mean([s['area_strain'] for s in cycle],axis=0)
        pressure = (RP+RD)*mean
        target_area = problem('arterial')[0].lame_area_strain(pressure)
        scale = mean/grid['amplitude_m3_s']
        ids = positions(grid['sections'],r['sections'])
        exact = scale*np.array([cpair(v).real for v in ref['area_strain']])
        previous = scale*np.array([cpair(v).real for v in old['area_strain']])
        old_pin = cpair(old['inlet_mean_pressure_pa']).real*scale
        pin = np.mean([s['inlet_mean_pressure'] for s in cycle])
        target_pin = cpair(ref['inlet_mean_pressure_pa']).real*scale
        terminal = np.array(item['endpoint_port_steps_pc_pb_full_q'])
        last = n*r['cycles']
        if (terminal.shape != (2*n,4) or not np.isfinite(terminal).all()
                or not np.array_equal(terminal[:,0],np.arange(last-2*n+1,last+1))):
            raise ValueError('Incomplete dense terminal history')
        _, pc, pb, q = terminal[-n:].T
        mid = len(r['sections'])//2
        inlet = np.array([s['full_inlet'] for s in cycle])
        peak = r['full_amplitude']
        # At equispaced full-period endpoints, the prescribed sine sets the phase without interpolation.
        phase = 2j*np.exp(-2j*np.pi*np.arange(1,n+1)/n)/n
        results.append(dict(group=item['group'],case=item['case'],solver=item['solver'],model=r['model'],
                            rigid=key[0],moving_plane=key[1],steps=n,samples=nobs,mean_m3_s=mean,amplitude_m3_s=peak,
                            min_sampled_inlet_m3_s=min(inlet),min_dense_terminal_flow_m3_s=min(q),
                            mean_outlet_over_mean_inlet=flow.mean()/mean,mean_dense_terminal_over_mean_inlet=q.mean()/mean,
                            mean_outlet_wall_flux_over_inlet=np.mean([s['full_wall_flux'] for s in cycle])/mean,
                            mean_terminal_pressure_pa=pb.mean(),mean_capacitor_pressure_pa=pc.mean(),target_RQ_pa=pressure,
                            mean_terminal_gap_pct_RQ=100*abs(pb.mean()-pressure)/pressure,
                            mean_capacitor_gap_pct_RdQ=100*abs(pc.mean()-RD*mean)/(RD*mean),
                            mean_inlet_pressure_pa=pin,ref_steady_inlet_pressure_pa=target_pin,
                            mean_inlet_gap_pct_RQ=100*abs(pin-target_pin)/pressure,
                            mean_mid_area_pct=100*area[mid],ref_steady_mid_area_pct=100*exact[ids[mid]],
                            mean_max_section_gap_pct_static=100*np.max(abs(area-exact[ids]))/target_area,
                            current_field_to_dense_port_ac_gap_pct_peak=100*abs(cpair(r['phasors']['full_outlet'])-phase@q)/peak,
                            ref_steady_unknowns=grid['unknowns'],ref_previous_unknowns=coarse_grid['unknowns'],
                            ref_steady_grid_pressure_change_pct_RQ=100*abs(target_pin-old_pin)/pressure,
                            ref_steady_grid_area_change_pct_static=100*np.max(abs(exact-previous))/target_area))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    src=p.add_mutually_exclusive_group(required=True)
    src.add_argument('--runs',type=Path)
    src.add_argument('--archive',type=Path)
    p.add_argument('--reference-scripts',type=Path)
    p.add_argument('--native-executable',type=Path)
    p.add_argument('--write-archive',type=Path)
    p.add_argument('--meridian-csv',type=Path,required=True)
    p.add_argument('--solver-csv',type=Path,required=True)
    p.add_argument('--pairs-csv',type=Path)
    p.add_argument('--forward-csv',type=Path)
    args=p.parse_args()
    if args.runs and not (args.reference_scripts and args.native_executable):
        p.error('Raw validation requires the pinned field readers and native solver')
    data=pack(args.runs,args.reference_scripts,args.native_executable) if args.runs else json.loads(lzma.decompress(args.archive.read_bytes()))
    meridian,results=tables(data)
    outputs=[(meridian,args.meridian_csv),(results,args.solver_csv)]
    accepted={(r['group'],r['case']) for r in results if r['periodic_pass']}
    if args.pairs_csv:
        outputs.append((direct_pairs(data,accepted),args.pairs_csv))
    if args.forward_csv:
        outputs.append((forward_flow(data,accepted),args.forward_csv))
    for rows,path in outputs:
        if not rows:raise ValueError('No validated observations')
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
            w.writeheader()
            w.writerows(rows)
    if args.write_archive:
        tmp=args.write_archive.with_suffix('.partial')
        tmp.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
        tmp.replace(args.write_archive)
    print(len(meridian),'grid/frequency combinations;',len(results),'3D runs;',sum(r['periodic_pass'] for r in results),'periodic')


if __name__=='__main__':
    main()
