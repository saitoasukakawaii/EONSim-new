"""Frozen tube protocol, original-equation receipts and trajectory comparisons.

Policy selection has no PETSc or postprocessing dependencies. The numerical
checks import the existing mesh and history readers only when needed.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BLOCKS = {'velocity', 'pressure', 'mesh', 'structure'}


def archived_case(case):
    """Resolve the original meshes, physics and partition from the committed phase-03/04 index."""
    from paired_tube import digest
    work=Path.home()/'workspace'
    if case=='C':
        directory=work/'fsi-scalable-03-runs/C-first-64'
        file=directory/'diagnosis.json'
        index=HERE.parent/'fsi-scalable-03/log-index.json'
    elif case in ('A','B'):
        directory=work/'fsi-scalable-04-runs'/(case+'-return')
        file=directory/'run.json'
        index=HERE.parent/'fsi-scalable-04/tube-log-index.json'
    else:
        raise ValueError(f'Unknown tube mesh {case}')
    key='$HOME/'+file.relative_to(Path.home()).as_posix()
    sha=json.loads(index.read_text())[key]['sha256']
    if digest(file)!=sha:
        raise ValueError('Historical receipt differs from the committed benchmark index')
    return directory,json.loads(file.read_text()),sha


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
    if any(os.getenv(k) for k in ('PETSC_OPTIONS','PETSC_OPTIONS_YAML')):
        raise ValueError('Tube validation requires a clean PETSc options environment')
    common = ['-skip_petscrc', '-options_view', '-linear_protocol_hash', policy['hash'], '-linear_report', '-solver_report',
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


def verify_invocation(folder, lines, policy):
    """Check effective options against the recorded command and the frozen profile."""
    receipt = json.loads((folder/'run.json').read_text())
    if receipt.get('exit_code') != 0 or receipt['log_sha256'] != hashlib.sha256((folder/'solve.log').read_bytes()).hexdigest():
        raise ValueError('Unsuccessful invocation or changed log')
    command = receipt['command']
    start, end = '#PETSc Option Table entries:', '#End of PETSc Option Table entries'
    if lines.count(start)!=1 or lines.count(end)!=1:
        raise ValueError('Missing effective PETSc option table')
    table = {}
    for line in lines[lines.index(start)+1:lines.index(end)]:
        m = re.fullmatch(r'(-\S+)(?:\s+(.*?))?\s+# \(source: ([^)]+)\)',line)
        if not m or m[1] in table or m[3] not in ('command line','code'):
            raise ValueError(f'Unexpected PETSc option source or repetition: {line}')
        table[m[1]] = (m[2] or '').strip()
    # Older phase-05 invocations without -skip_petscrc remain verifiable: any
    # effective option from an external file/environment is rejected above.
    i = command.index('-case')
    while i < len(command):
        key = command[i]
        if not key.startswith('-'):
            raise ValueError(f'Invalid option in recorded solver invocation: {key}')
        value = ''
        if i+1<len(command) and not command[i+1].startswith('-'):
            value = command[i+1]
            i += 1
        if table.get(key) != value:
            raise ValueError(f'PETSc options and command differ for {key}')
        i += 1
    def produced(key):
        return table.get(key,'').lower()
    diagnostics = produced('-linear_componentwise_error')
    if diagnostics not in ('true','false') or produced('-linear_protocol_hash') != policy['hash']:
        raise ValueError('Missing or changed effective protocol or diagnostic mode')
    if policy['mode']=='lu':
        if (produced('-ksp_type')!='preonly' or produced('-pc_type')!='lu'
                or produced('-pc_factor_mat_solver_type')!='superlu_dist'
                or int(table['-linear_lu_refinement_steps'])!=policy['refinements']):
            raise ValueError('Effective direct reference configuration differs')
        prefix = '-linear_lu_refinement_'
    else:
        if (produced('-ksp_type') not in ('fgmres','pipefgmres') or produced('-nonlinear_true_residual')!='true'
                or produced('-ksp_norm_type')!='unpreconditioned'
                or produced('-nonlinear_inexact_newton') != ('true' if policy['mode']=='inexact' else 'false')):
            raise ValueError('Effective iterative configuration differs')
        prefix = '-ksp_'
    for name in ('rtol','atol'):
        if finite(table,prefix+name)!=policy[name]:
            raise ValueError('Effective tolerance differs from pre-run selection')
    return table, diagnostics=='true'


def audit_row(row, policy, previous=None):
    eta, atol = finite(row, 'requested_rtol'), finite(row, 'requested_atol')
    rhs, norm = finite(row, 'rhs_norm'), finite(row, 'norm')
    inexact = policy['mode'] == 'inexact'
    if (row['protocol_hash'] != policy['hash'] or finite(row, 'roundoff_slack') != 0
            or int(row['forcing']) != int(inexact) or int(row['ksp_reason']) <= 0
            or (policy['mode']!='lu' and int(row['ksp_reason'])==4)
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


def audit_corrections(folder, steps, ranks, policy, start_step=0):
    """Audit actual settings against the independently supplied, pre-run selection."""
    if select(policy['protocol_id'], policy['profile']) != policy:
        raise ValueError('Declaration differs from frozen protocol')
    lines = (folder / 'solve.log').read_text().splitlines()
    options, componentwise = verify_invocation(folder,lines,policy)
    reports, states = records(lines, 'solver_report '), records(lines, 'fsi_step=')
    rows = records(lines, 'linear_residual ')
    fields = records(lines, 'linear_field_residual ')
    finals = records(lines, 'field_residual ')
    length=steps-start_step
    if (not 0<=start_step<steps or len(reports) != length or len(states) != length or len(fields) != 4*len(rows)
            or len(finals) != 4*length or 'status=success' not in lines
            or any(line.startswith(('linear_iteration_limit', 'linear_residual_unavailable')) for line in lines)):
        raise ValueError('Incomplete trajectory, failed correction or missing nonlinear acceptance')
    case = json.loads((folder / 'case.json').read_text())
    ratios, corrections, offset = [], [], 0
    for step, (s, report) in enumerate(zip(states, reports), start_step+1):
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
        if (report['linesearch'] not in ('bt','basic') or (count and not 0 < finite(report,'final_lambda') <= 1)
                or int(report['matrix_free']) != 0 or int(report['pc_rebuild_retries']) != 0
                or int(report['inexact_linear_solves']) != (count if policy['mode']=='inexact' else 0)):
            raise ValueError('Effective nonlinear solver differs from the frozen run')
        expected_pc = options.get('-pc_type')
        if options.get('-pc_recipe')=='physics':
            expected_pc='fieldsplit'
        if expected_pc and report['pc']!=expected_pc:
            raise ValueError('Instantiated outer PC differs from invocation')
        final = finals[(step-start_step-1)*4:(step-start_step)*4]
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
        if (sum(int(row['ksp_iterations']) for row in step_rows) != int(report['linear_iterations'])
                or (count and step_rows[-1]['ksp_reason'] != report['ksp_reason'])):
            raise ValueError('KSP work or final reason disagrees with step summary')
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
                matching = next(f for f in final if f['name']==field['name'])
                for key in ('constraint_scale','residual_scale'):
                    if not math.isclose(finite(field,key),finite(matching,key),rel_tol=1e-15):
                        raise ValueError('Linear field scale differs from nonlinear layout')
                field['equation_l2'] = finite(field,'rms') * finite(field,'residual_scale') * math.sqrt(n_eq)
                field['constraint_physical_max'] = finite(field,'constraint_max') * finite(field,'constraint_scale')
            if sum(int(f['equation_rows'])+int(f['constraint_rows']) for f in blocks) != int(report['dofs']):
                raise ValueError('Linear residual blocks do not cover the system')
            for k in ('wide_norm','backward_error'):
                if (k in row) != componentwise or (componentwise and finite(row,k)<0):
                    raise ValueError(f'Invalid {k}')
            if componentwise and policy['mode']=='lu' and finite(row,'wide_norm') > finite(row,'limit'):
                raise ValueError('Extended residual of the direct reference failed')
            corrections.append(dict(**row, fields=blocks))
            previous = row
        offset += count
    if len(rows) != offset:
        raise ValueError('Unexpected correction count')
    return dict(protocol_id=policy['protocol_id'], profile=policy['profile'], protocol_hash=policy['hash'],
                corrections=len(rows), max_ratio=max(ratios,default=None), dofs=int(reports[0]['dofs']),
                ksp_iterations=sum(int(r['linear_iterations']) for r in reports),
                ksp=reports[0]['ksp'], pc=reports[0]['pc'], rows=corrections,
                accepted_steps=states, solver_reports=reports, nonlinear_fields=finals,
                effective_options=options)

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


def tube_stem(start_step):
    return 'tube' if not start_step else f'tube_restart{start_step}'


def pressure_face_history(folder, accepted, tags, start_step=0):
    with (folder/(tube_stem(start_step)+'_pressure_faces.csv')).open() as stream:
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


def compare_face_history(candidate, reference, histories, policy, starts=(0,0)):
    case = json.loads((candidate/'case.json').read_text())['fsi']
    if not case.get('pressure_face_history',False):
        return {}
    tags = case['domains']['pressure_tags']
    groups = [pressure_face_history(d,h,tags,start) for d,h,start in zip((candidate,reference),histories,starts)]
    maximum = {}
    for key in groups[0]:
        if key[0]<=max(starts):
            continue
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



def output_manifest(folder, steps, ranks, start_step=0):
    """Verify the PVD → PVTU → physical VTU chain and bind all saved fields to the receipt."""
    import xml.etree.ElementTree as ET
    from paired_tube import digest
    cfg=json.loads((folder/'case.json').read_text())['fsi']
    if cfg['steps']!=steps or cfg['output_interval']!=4 or cfg['dt']!=1/32:
        raise ValueError('Unexpected saved-field schedule')
    name=tube_stem(start_step)
    phases=sorted(set(range(start_step//4*4+4,steps+1,4))|{steps})
    result={'phase_hashes':{},'indices':{},'history':{name+'.csv':digest(folder/(name+'.csv'))}}
    if cfg.get('pressure_face_history'):
        result['history'][name+'_pressure_faces.csv']=digest(folder/(name+'_pressure_faces.csv'))
    for domain,suffix in [('fluid',''),('solid','_solid')]:
        pvd=folder/(name+suffix+'.pvd')
        result['indices'][pvd.name]=digest(pvd)
        datasets=ET.parse(pvd).findall('./Collection/DataSet')
        if len(datasets)!=len(phases):
            raise ValueError(f'Missing or extra {domain} output phases')
        for step,entry in zip(phases,datasets):
            stem=f'{name}_step{step}'+suffix
            ext='.pvtu' if ranks>1 else '.vtu'
            if entry.attrib['file']!=stem+ext or float(entry.attrib['timestep'])!=step/32:
                raise ValueError(f'Incorrect {domain} output phase {step}')
            files=[stem+f'_rank{i}.vtu' for i in range(ranks)] if ranks>1 else [stem+ext]
            if ranks>1:
                pvtu=folder/(stem+ext)
                sources=[p.attrib['Source'] for p in ET.parse(pvtu).findall('./PUnstructuredGrid/Piece')]
                if sources!=files:
                    raise ValueError(f'Incorrect piece set for {pvtu.name}')
                result['indices'][pvtu.name]=digest(pvtu)
            hashes=[digest(folder/n) for n in files]
            if step==steps:
                final=['tube'+suffix+(f'_rank{i}' if ranks>1 else '')+'.vtu' for i in range(ranks)]
                if ranks>1:
                    index=folder/('tube'+suffix+'.pvtu')
                    if [p.attrib['Source'] for p in ET.parse(index).findall('./PUnstructuredGrid/Piece')]!=final:
                        raise ValueError('Final state has missing VTU pieces')
                    result['indices'][index.name]=digest(index)
                if [digest(folder/n) for n in final]!=hashes:
                    raise ValueError('Published final state differs from the last snapshot')
            result['phase_hashes'][stem] = hashlib.sha256(''.join(hashes).encode()).hexdigest()
    return result


def full_field_differences(candidate,reference,steps,ranks,policy,starts=(0,0)):
    import benchmark_fsi_assembly as assembly
    spec_file=HERE/'output-fields-v2.1.json'
    spec=json.loads(spec_file.read_text())
    omega=2*math.pi/spec['period_seconds']
    required={(domain,name) for domain,fields in spec['regions'].items() for name in fields}
    phases=[]
    for step in range(max(starts)//4*4+4,steps+1,4):
        fields=[assembly.physical_fields(d/f'{tube_stem(start)}_step{step}.vtu',n)
                for d,n,start in zip((candidate,reference),ranks,starts)]
        if fields[0].keys()!=fields[1].keys():
            raise ValueError(f'Physical field node coverage differs at step {step}')
        stats={}
        for key,a in fields[0].items():
            suffix,node,name=key
            domain='solid' if suffix else 'fluid'
            b=fields[1][key]
            if len(a)!=len(b) or len(a)!=(1 if name=='pressure' else 3):
                raise ValueError(f'Unexpected components for {key}')
            delta=math.dist(a,b)
            if not math.isfinite(delta):
                raise ValueError(f'Nonfinite output {domain}/{name} at node {node}')
            group=stats.setdefault((domain,name),[0,0.,0.])
            group[0]+=1
            group[1]+=delta**2
            group[2]=max(group[2],delta)
        if set(stats)!=required:
            raise ValueError(f'Unbudgeted or missing physical fields at step {step}: {set(stats)^required}')
        phase={'step':step}
        for (domain,name),(count,squares,peak) in stats.items():
            quantity,derivative=spec['regions'][domain][name]
            limit=budget(policy,quantity)*omega**derivative
            rms=math.sqrt(squares/count)
            if rms>limit or peak>limit:
                raise ValueError(f'Step {step} {domain}/{name} rms {rms}, maximum {peak}, limit {limit}')
            phase[domain+'/'+name]=dict(nodes=count,rms=rms,maximum=peak,limit=limit)
        phases.append(phase)
    return phases,hashlib.sha256(spec_file.read_bytes()).hexdigest()

def compare_trajectories(candidate, reference, steps, meshes, ranks, policy, starts=(0,0)):
    """Complete physical comparison; correction audits and algorithm independence are separate prerequisites."""
    import sys
    sys.path.insert(0,str(HERE.parent/'fsi-scalable-02'))
    from paired_tube import compare, digest, physical, DT
    from internal_tube import compare_states
    import benchmark_fsi_assembly as assembly
    if steps <= 0 or steps % 4 or min(starts)<0 or max(starts)>=steps or any(s%4 for s in starts):
        raise ValueError('Trajectory qualification requires complete four-step output phases')
    for name in ('case.json','fluid.msh','solid.msh'):
        if digest(candidate/name) != digest(reference/name):
            raise ValueError(f'Different physical inputs: {name}')
    if any(starts) and policy['protocol_id']!='CALIBRATED-v2':
        raise ValueError('Segmented comparisons require the versioned field budgets')
    histories = [assembly.history(d/(tube_stem(start)+'.csv'),steps,DT,start)
                 for d,start in zip((candidate,reference),starts)]
    observed = [physical(d,'eon',meshes,steps,n,write=False,start_step=start)
                for d,n,start in zip((candidate,reference),ranks,starts)]
    for state in observed:
        state['trace']=[r for r in state['trace'] if r['step']>max(starts)]
    gates = compare(*observed)
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in gates.values()):
        raise ValueError(f'Frozen physical constraint failed: {gates}')
    if policy['protocol_id'] == 'STRICT-v1':
        return dict(physical_gates=gates, history_difference=assembly.compare_history(*histories),
                    field_difference=compare_states(candidate,reference,steps,meshes,ranks=ranks))
    faces = compare_face_history(candidate,reference,histories,policy,starts)
    histories=[[r for r in history if r['step']>max(starts)] for history in histories]
    obs_budget = policy['document']['internal_observables']
    history_max, observable_max = {}, {}
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
    field_phases,field_spec_hash=full_field_differences(candidate,reference,steps,ranks,policy,starts)
    return dict(protocol_hash=policy['hash'], physical_gates=gates, physical=observed, pressure_face_differences=faces,
                history_maximum_difference=history_max, observable_maximum_difference=observable_max,
                full_field_differences=field_phases, output_field_budget_sha256=field_spec_hash)
