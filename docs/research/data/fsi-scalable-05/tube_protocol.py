"""Frozen tube protocol, original-equation receipts and trajectory comparisons.

Policy selection has no PETSc or postprocessing dependencies. The numerical
checks import the existing mesh and history readers only when needed.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BLOCKS = {'velocity', 'pressure', 'mesh', 'structure'}


def select(protocol_id='CALIBRATED-v2', profile='fixed-1e-8'):
    if protocol_id not in ('STRICT-v1', 'CALIBRATED-v2'):
        raise ValueError(f'Unknown tube protocol {protocol_id}')
    document = json.loads((HERE / (protocol_id + '.json')).read_text())
    settings = document['profiles'][profile]
    declaration = dict(document=document, profile=profile)
    canonical = json.dumps(declaration, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return dict(**settings, protocol_id=protocol_id, profile=profile, document=document,
                hash=hashlib.sha256(canonical.encode()).hexdigest())


def solver_options(policy, diagnostics=True):
    common = ['-linear_protocol_hash', policy['hash'], '-linear_report', '-solver_report',
              '-linear_componentwise_error', 'true' if diagnostics else 'false']
    if policy['mode'] == 'lu':
        return common + ['-ksp_type', 'preonly', '-pc_type', 'lu', '-pc_factor_mat_solver_type', 'superlu_dist',
                         '-linear_lu_refinement_steps', str(policy['refinements']),
                         '-linear_lu_refinement_rtol', str(policy['rtol']),
                         '-linear_lu_refinement_atol', str(policy['atol'])]
    opts = common + ['-ksp_type', 'fgmres', '-ksp_norm_type', 'unpreconditioned', '-ksp_pc_side', 'right',
                     '-ksp_rtol', str(policy['rtol']), '-ksp_atol', str(policy['atol']),
                     '-nonlinear_true_residual', 'true',
                     '-nonlinear_inexact_newton', 'true' if policy['mode'] == 'inexact' else 'false']
    if policy['mode'] == 'inexact':
        for key in ('initial', 'max', 'gamma', 'alpha'):
            opts += ['-nonlinear_forcing_' + key, str(policy['document']['forcing'][key])]
    return opts


def finite(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f'Nonfinite {key}')
    return value


def records(lines, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in lines if line.startswith(prefix)]


def audit_row(row, policy, previous=None):
    eta, atol = finite(row, 'requested_rtol'), finite(row, 'requested_atol')
    rhs, norm = finite(row, 'rhs_norm'), finite(row, 'norm')
    inexact = policy['mode'] == 'inexact'
    if (row['protocol_hash'] != policy['hash'] or finite(row, 'roundoff_slack') != 0
            or int(row['forcing']) != int(inexact) or int(row['ksp_reason']) <= 0
            or int(row['ksp_iterations']) < 0 or finite(row, 'linear_seconds') < 0
            or int(row['nonzero_guess']) not in (0, 1) or min(rhs, norm) < 0
            or atol != policy['atol'] or finite(row, 'base_rtol') != policy['rtol']):
        raise ValueError('Effective linear settings or correction outcome disagree with protocol')
    if inexact:
        f = policy['document']['forcing']
        for key in ('initial', 'max', 'gamma', 'alpha'):
            if finite(row, 'eta_' + key) != f[key]:
                raise ValueError('Forcing policy differs from declaration')
        expected = f['initial']
        if previous is not None and float(previous['rhs_norm']) > 0:
            expected = f['gamma'] * (rhs / float(previous['rhs_norm'])) ** f['alpha']
            safeguard = f['gamma'] * float(previous['requested_rtol']) ** f['alpha']
            if safeguard > f['safeguard']:
                expected = max(expected, safeguard)
        expected = min(f['max'], max(policy['rtol'], expected))
        # Only the redundant Python/libm recomputation may differ by rounding.
        # The residual inequality below has exactly zero multiplicative slack.
        if not (policy['rtol'] <= eta <= f['max'] and math.isclose(eta, expected, rel_tol=8e-15, abs_tol=0)):
            raise ValueError(f'Actual eta {eta} disagrees with forcing recurrence {expected}')
    elif eta != policy['rtol']:
        raise ValueError('Fixed effective relative tolerance differs from declaration')
    threshold = max(atol, eta * rhs)
    if finite(row, 'limit') != threshold:
        raise ValueError('Reported threshold differs from max(atol, eta * rhs_norm)')
    if norm > threshold:
        raise ValueError(f'Original residual {norm} exceeds {threshold}')
    return norm / threshold if threshold else 0.


def audit_corrections(folder, steps, ranks, policy):
    """Audit actual settings against the independently supplied, pre-run selection."""
    if select(policy['protocol_id'], policy['profile']) != policy:
        raise ValueError('Declaration differs from frozen protocol')
    lines = (folder / 'solve.log').read_text().splitlines()
    reports, states = records(lines, 'solver_report '), records(lines, 'fsi_step=')
    rows = records(lines, 'linear_residual ')
    fields = records(lines, 'linear_field_residual ')
    finals = records(lines, 'field_residual ')
    if (len(reports) != steps or len(states) != steps or len(fields) != 4*len(rows)
            or len(finals) != 4*steps or 'status=success' not in lines
            or any(line.startswith(('linear_iteration_limit', 'linear_residual_unavailable')) for line in lines)):
        raise ValueError('Incomplete trajectory, failed correction or missing nonlinear acceptance')
    case = json.loads((folder / 'case.json').read_text())
    ratios, corrections, offset = [], [], 0
    for step, (s, report) in enumerate(zip(states, reports), 1):
        count = int(s['snes_iterations'])
        if (int(s['fsi_step']) != step or int(report['step']) != step or int(report['attempt']) != 1
                or report['protocol_hash'] != policy['hash'] or finite(s, 'residual') < 0 or int(report['ranks']) != ranks
                or int(report['linear_started']) != count or int(report['linear_completed']) != count
                or int(report['snes_reason']) <= 0 or (count and int(report['ksp_reason']) <= 0)
                or ((report['ksp'], report['pc']) != ('preonly', 'lu') if policy['mode'] == 'lu'
                    else report['ksp'] not in ('fgmres', 'pipefgmres'))):
            raise ValueError(f'Invalid solver report at step {step}')
        cfg = case['solver']
        for reported, configured, default in [('snes_atol','absolute_tolerance',1e-12),
                ('snes_rtol','relative_tolerance',1e-10), ('snes_max_it','maximum_iterations',1000)]:
            if finite(report, reported) != cfg.get(configured, default):
                raise ValueError(f'{reported} differs from frozen case at step {step}')
        if finite(report,'snes_stol') != 0:
            raise ValueError('Unexpected SNES step tolerance')
        final = finals[(step-1)*4:step*4]
        if {f['name'] for f in final} != BLOCKS or any(int(f['accepted']) != 1 for f in final):
            raise ValueError(f'Unaccepted nonlinear field or constraint at step {step}')
        for f in final:
            spec = cfg.get('fields',{}).get(f['name'],{})
            absolute = cfg.get('absolute_tolerance',1e-12)
            relative = cfg.get('relative_tolerance',1e-10)
            expected = spec.get('absolute_tolerance',absolute) + spec.get('relative_tolerance',relative)*finite(f,'initial_rms')
            # The legacy nonlinear field report prints 16 significant digits.
            if (not math.isclose(finite(f,'limit'),expected,rel_tol=3e-15,abs_tol=0)
                    or not math.isclose(finite(f,'constraint_limit'),spec.get('constraint_tolerance',absolute),rel_tol=1e-15)
                    or not math.isclose(finite(f,'residual_scale'),spec.get('residual_scale',1.),rel_tol=1e-15)
                    or not math.isclose(finite(f,'constraint_scale'),spec.get('constraint_scale',1.),rel_tol=1e-15)):
                raise ValueError(f'Nonlinear field settings differ from the case at step {step}')
            for key in ('rms','constraint_max','limit','constraint_limit'):
                if finite(f,key) < 0:
                    raise ValueError('Invalid nonlinear field')
            if float(f['rms']) > float(f['limit']) or float(f['constraint_max']) > float(f['constraint_limit']):
                raise ValueError(f'Nonlinear threshold failed at step {step}')
        step_rows = rows[offset:offset+count]
        if len(step_rows) != count:
            raise ValueError('Missing correction')
        previous = None
        for i,row in enumerate(step_rows,1):
            if (int(row['step']),int(row['newton']),int(row['solve']),int(row['attempt']),int(row['pc_attempt'])) != (step,i,i,1,1):
                raise ValueError(f'Unexpected, retried or incomplete correction at step {step}/{i}')
            ratios.append(audit_row(row,policy,previous))
            blocks = fields[4*(offset+i-1):4*(offset+i)]
            if {f['name'] for f in blocks} != BLOCKS:
                raise ValueError(f'Incomplete original residual blocks at step {step}/{i}')
            for field in blocks:
                for key in ('step','newton','solve','attempt','pc_attempt','protocol_hash'):
                    if field[key] != row[key]:
                        raise ValueError(f'Misaligned field {key}')
                if any(finite(field,key) < 0 for key in ('rms','constraint_max','residual_scale','constraint_scale')):
                    raise ValueError('Invalid linear field')
                n_eq, n_bc = int(field['equation_rows']), int(field['constraint_rows'])
                if n_eq < 0 or n_bc < 0 or n_eq + n_bc <= 0:
                    raise ValueError('Invalid global field coverage')
                field['equation_l2'] = finite(field,'rms') * finite(field,'residual_scale') * math.sqrt(n_eq)
                field['constraint_physical_max'] = finite(field,'constraint_max') * finite(field,'constraint_scale')
            for k in ('wide_norm','backward_error'):
                if k in row and finite(row,k)<0:
                    raise ValueError(f'Invalid {k}')
            corrections.append(dict(**row, fields=blocks))
            previous = row
        offset += count
    if len(rows) != offset or not corrections:
        raise ValueError('Unexpected correction count')
    return dict(protocol_id=policy['protocol_id'], profile=policy['profile'], protocol_hash=policy['hash'],
                corrections=len(rows), max_ratio=max(ratios), dofs=int(reports[0]['dofs']),
                ksp_iterations=sum(int(r['linear_iterations']) for r in reports),
                ksp=reports[0]['ksp'], pc=reports[0]['pc'], rows=corrections,
                accepted_steps=states, solver_reports=reports, nonlinear_fields=finals)

def history_quantity(key):
    if key in ('step','time','evaluation_time','accepted_dt','time_order','rcr_tag','reference_interface_area'):
        return 'exact'
    if key in ('snes_iterations','residual'):
        return 'diagnostic'
    if 'pressure' in key:
        return 'pressure'
    if key == 'stage_capacitor_rate':
        return 'pressure_rate'
    if key == 'current_interface_area':
        return 'area'
    if 'displacement' in key or key == 'endpoint_position':
        return 'displacement'
    if 'velocity' in key:
        return 'wall_velocity'
    if 'force' in key or key == 'evaluation_body_balance':
        return 'force'
    if 'power' in key:
        return 'power'
    if key.endswith('_volume'):
        return 'volume'
    if key.endswith(('_flow','_flux','_divergence','_mass_residual')) or key == 'volume_secant_rate':
        return 'flow'
    if 'min_' in key and key.endswith('_j'):
        return 'jacobian'
    raise ValueError(f'No frozen budget for history column {key}')


def budget(policy, quantity):
    b = policy['document']['field_budgets'][quantity]
    return b['absolute'] + b['relative'] * b['scale']


def pressure_face_history(folder, accepted, tags):
    with (folder/'tube_pressure_faces.csv').open() as stream:
        rows = [{k:finite(r,k) for k in r} for r in csv.DictReader(stream)]
    index = {(r['step'],r['tag']):r for r in rows}
    expected = {(r['step'],tag) for r in accepted for tag in tags}
    if len(rows)!=len(index) or set(index)!=expected:
        raise ValueError('Incomplete pressure face history')
    for row in accepted:
        for tag in tags:
            face = index[row['step'],tag]
            if any(row[k]!=face[k] for k in ('time','accepted_dt','evaluation_time')):
                raise ValueError('Pressure face time grid mismatch')
    return index


def compare_face_history(candidate, reference, histories, policy):
    case = json.loads((candidate/'case.json').read_text())['fsi']
    if not case.get('pressure_face_history',False):
        return {}
    tags = case['domains']['pressure_tags']
    groups = [pressure_face_history(d,h,tags) for d,h in zip((candidate,reference),histories)]
    maximum = {}
    for key in groups[0]:
        x,y = (g[key] for g in groups)
        for phase in ('stage','endpoint'):
            for column,quantity in [('area','area'),('mean_pressure','pressure'),('mean_normal_traction','pressure'),
                                    ('outward_flow','flow'),('prescribed_pressure','pressure'),('pressure_power','power')]:
                name = phase+'_'+column
                delta = abs(x[name]-y[name])
                maximum[name] = max(maximum.get(name,0),delta)
                limit = budget(policy,quantity) if policy['protocol_id']=='CALIBRATED-v2' else 2e-9
                if delta > limit:
                    raise ValueError(f'Pressure face {key}, {name}: {delta} > {limit}')
    return maximum


def compare_trajectories(candidate, reference, steps, meshes, ranks, policy):
    """Complete physical comparison; correction audits and algorithm independence are separate prerequisites."""
    import sys
    sys.path.insert(0,str(HERE.parent/'fsi-scalable-02'))
    from paired_tube import compare, digest, physical, DT
    from internal_tube import compare_states
    import benchmark_fsi_assembly as assembly
    from study_hydrostatic_fsi import recovered_state
    if steps <= 0 or steps % 4:
        raise ValueError('Trajectory qualification requires complete four-step output phases')
    for name in ('case.json','fluid.msh','solid.msh'):
        if digest(candidate/name) != digest(reference/name):
            raise ValueError(f'Different physical inputs: {name}')
    histories = [assembly.history(d/'tube.csv',steps,DT) for d in (candidate,reference)]
    observed = [physical(d,'eon',meshes,steps,n,write=False) for d,n in zip((candidate,reference),ranks)]
    gates = compare(*observed)
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in gates.values()):
        raise ValueError(f'Frozen physical constraint failed: {gates}')
    if policy['protocol_id'] == 'STRICT-v1':
        return dict(physical_gates=gates, history_difference=assembly.compare_history(*histories),
                    field_difference=compare_states(candidate,reference,steps,meshes,ranks=ranks))
    faces = compare_face_history(candidate,reference,histories,policy)
    obs_budget = policy['document']['internal_observables']
    history_max, observable_max, field_phases = {}, {}, []
    for x,y in zip(*histories):
        if x.keys()!=y.keys():
            raise ValueError('Mismatched history columns')
        for key in x:
            quantity = history_quantity(key)
            delta = abs(x[key]-y[key])
            history_max[key] = max(history_max.get(key,0),delta)
            if quantity == 'diagnostic':
                continue
            limit = 0. if quantity == 'exact' else budget(policy,quantity)
            if delta > limit:
                raise ValueError(f'History step {x["step"]}, {key}: {delta} > {limit}')
    for a,b in zip(observed[0]['trace'],observed[1]['trace']):
        for key,limit in obs_budget.items():
            delta = (max(abs(x-y) for x,y in zip(a[key],b[key])) if key == 'area'
                     else abs(a[key]-b[key]))
            observable_max[key] = max(observable_max.get(key,0),delta)
            if delta > limit:
                raise ValueError(f'Observable step {a["step"]}, {key}: {delta} > {limit}')
    for step in range(4,steps+1,4):
        phase = dict(step=step)
        for solid,mesh in enumerate(meshes):
            name=f'tube_step{step}' + ('_solid' if solid else '')
            states=[recovered_state(d,name,mesh,bool(solid),n) for d,n in zip((candidate,reference),ranks)]
            if not states[0] or states[0].keys() != states[1].keys():
                raise ValueError('Field node coverage mismatch')
            measures={'wall_velocity' if solid else 'fluid_velocity':('velocity','wall_velocity' if solid else 'fluid_velocity'),
                      'wall_displacement' if solid else 'mesh_displacement':('displacement','displacement')}
            if not solid:
                measures['pressure']=('pressure','pressure')
            for field,(attr,quantity) in measures.items():
                peak = square_sum = 0.
                for node,left in states[0].items():
                    a,b = getattr(left,attr), getattr(states[1][node],attr)
                    delta = abs(a-b) if attr=='pressure' else math.dist(a,b)
                    if not math.isfinite(delta):
                        raise ValueError(f'Nonfinite field {field} at node {node}')
                    peak = max(peak,delta)
                    square_sum += delta*delta
                rms=math.sqrt(square_sum / len(states[0]))
                limit=budget(policy,quantity)
                phase[field]=dict(nodes=len(states[0]), rms=rms, maximum=peak, limit=limit)
                if rms > limit or peak > limit:
                    raise ValueError(f'Field step {step}, {field}: rms {rms}, max {peak}, limit {limit}')
        field_phases.append(phase)
    return dict(protocol_hash=policy['hash'], physical_gates=gates, physical=observed, pressure_face_differences=faces,
                history_maximum_difference=history_max, observable_maximum_difference=observable_max,
                full_field_differences=field_phases)
