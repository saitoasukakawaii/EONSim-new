"""Read-only independent audit of saved RCR FSI artifacts; never launches a solver.
No imports from EONSim verification helpers. Audits original point arrays, mesh faces,
circuit/history CSV and PETSc report lines; metrics.json is only cross-checked last.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET

REPO = next(p for p in Path(__file__).resolve().parents
            if (p/'CMakeLists.txt').is_file() and (p/'src/algebra/rcr_port_pc.cpp').is_file())
RAW = REPO / 'build/cloud-3.23.7-release/rcr_port_fsi'
EVIDENCE = REPO / 'docs/research/data/rcr-port-2026-11-26'
HASHES = {}


def read(path):
    logical = str(path.relative_to(REPO))
    if path.exists():
        data = path.read_bytes()
    elif path.name == 'independent-algebra-audit.json':
        data = (EVIDENCE/path.name).read_bytes()
    else:
        # On a clean checkout the ignored build files are available inside the
        # preserved archive. Read the matching member without extracting it.
        manifest = json.loads((EVIDENCE/'archive-manifest.json').read_text())
        member = next(item for item in manifest['files'] if item['source_path'] == logical)
        with tarfile.open(EVIDENCE/'evidence.tar.xz', 'r:xz') as archive:
            stream = archive.extractfile(member['archive_path'])
            assert stream is not None
            data = stream.read()
        assert len(data) == member['bytes'] and hashlib.sha256(data).hexdigest() == member['sha256']
    HASHES[logical] = hashlib.sha256(data).hexdigest()
    return data.decode()

def csv_rows(path):
    rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(read(path).splitlines())]
    assert rows and all(math.isfinite(v) for r in rows for v in r.values())
    return rows

def records(log, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in log.splitlines() if line.startswith(prefix)]

def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))

def load_fields(directory, label, ranks):
    data, counts, names = {}, {}, {}
    duplicate_max = 0.
    scalar_count = 0
    for solid in (False, True):
        nodes = set()
        field_names = set()
        for rank in range(ranks):
            suffix = ('_solid' if solid else '') + (f'_rank{rank}' if ranks > 1 else '') + '.vtu'
            tree = ET.fromstring(read(directory/(label+suffix)))
            xyz = list(map(float, tree.find('.//Points/DataArray').text.split()))
            size = len(xyz)//3
            arrays = {a.attrib['Name']: (int(a.attrib.get('NumberOfComponents', '1')), list(map(float, a.text.split())))
                      for a in tree.findall('.//PointData/DataArray')}
            assert len(xyz) == 3*size and all(map(math.isfinite, xyz))
            assert all(w > 0 and len(a) == w*size and all(map(math.isfinite, a)) for w, a in arrays.values())
            used = set(map(int, tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            assert used and min(used) >= 0 and max(used) < size
            for index in used:
                node = int(arrays['mesh_node_id'][1][index])
                nodes.add(node)
                values = {'coordinates': xyz[3*index:3*index+3]}
                values.update({name: a[w*index:w*(index+1)] for name, (w, a) in arrays.items()
                               if name not in ('mesh_node_id', 'owner', 'algebra_node_id')})
                for name, value in values.items():
                    field_names.add(name)
                    key = (solid, node, name)
                    if key in data:
                        duplicate_max = max(duplicate_max, max(abs(x-y) for x, y in zip(value, data[key])))
                    else:
                        scalar_count += len(value)
                    data[key] = value
        counts['solid' if solid else 'fluid'] = len(nodes)
        names['solid' if solid else 'fluid'] = sorted(field_names)
    assert duplicate_max < 2e-9
    return data, dict(nodes=counts, fields=names, scalar_values=scalar_count, max_duplicate_ghost_disagreement=duplicate_max)

def compare_fields(a, b):
    assert a.keys() == b.keys()
    by_field = {}
    location, maximum = None, 0.
    for key, value in a.items():
        assert len(value) == len(b[key])
        for component, (x, y) in enumerate(zip(value, b[key])):
            difference = abs(x-y)
            field = ('solid/' if key[0] else 'fluid/')+key[2]
            by_field[field] = max(by_field.get(field, 0.), difference)
            if difference > maximum:
                maximum = difference
                location = dict(domain='solid' if key[0] else 'fluid', node=key[1], field=key[2], component=component)
    assert maximum < 2e-8
    return dict(max_abs=maximum, location=location, by_field=by_field)

def load_mesh(directory):
    lines = read(directory/'fluid.msh').splitlines()
    assert lines[1] == '2.2 0 8'
    start = lines.index('$Nodes')
    n = int(lines[start+1])
    nodes = {int(t[0]): tuple(map(float,t[1:])) for t in (s.split() for s in lines[start+2:start+2+n])}
    start = lines.index('$Elements')
    n = int(lines[start+1])
    faces, cells = [], []
    for t in (list(map(int,s.split())) for s in lines[start+2:start+2+n]):
        if t[1] == 2:
            faces.append((t[3], t[3+t[2]:]))
        if t[1] == 4:
            cells.append(t[3+t[2]:])
    return nodes, faces, cells

def geometry_audit(fields, mesh, models, history, face_rows, case):
    reference, faces, cells = mesh
    # Mesh-node IDs are output-partition IDs; reconstruct a reference-coordinate
    # bijection instead of assuming they equal Gmsh's input numbering.
    def rounded(x): return tuple(round(v, 10) for v in x)
    output = {rounded(sub(x, fields[(False, node, 'mesh_displacement')])): node
              for (solid, node, name), x in fields.items() if not solid and name == 'coordinates'}
    assert len(output) == sum(not s and name == 'coordinates' for s, _, name in fields)
    mapped = {node: output[rounded(x)] for node, x in reference.items()}
    assert len(set(mapped.values())) == len(reference)
    current = {node: fields[(False, output_node, 'coordinates')] for node, output_node in mapped.items()}
    velocity = {node: fields[(False, output_node, 'velocity')] for node, output_node in mapped.items()}
    result = {}
    for model in models:
        tag = model['tag']
        normal = (1., 0., 0.) if case == 'single' else (0., 1. if tag == 2 else -1., 0.)
        area, reference_area, flux = 0., 0., 0.
        normal_motion = 0.
        count = 0
        for face_tag, ids in faces:
            if face_tag != tag: continue
            count += 1
            a, b, c = (current[node] for node in ids)
            a0, b0, c0 = (reference[node] for node in ids)
            twice = cross(sub(b, a), sub(c, a))
            orientation = 1. if dot(twice, normal) >= 0 else -1.
            area_vector = tuple(.5*orientation*v for v in twice)
            area += math.sqrt(dot(area_vector, area_vector))
            twice0 = cross(sub(b0, a0), sub(c0, a0))
            reference_area += .5*math.sqrt(dot(twice0, twice0))
            flux += sum(dot(area_vector, velocity[node]) for node in ids)/3.
            normal_motion = max(normal_motion, *(abs(dot(sub(current[node], reference[node]), normal)) for node in ids))
        assert count and reference_area > 0 and normal_motion < 1e-12
        final_face = next(r for r in face_rows if r['step'] == history[-1]['step'] and int(r['tag']) == tag)
        suffix = '' if case == 'single' else '_'+str(tag)
        area_difference = abs(area-final_face['endpoint_area'])
        flux_difference = abs(flux-history[-1]['endpoint_rcr_flow'+suffix])
        assert area_difference < 2e-12 and flux_difference < 2e-12
        result[str(tag)] = dict(faces=count, reference_area=reference_area, current_area=area,
                               fractional_area_change=area/reference_area-1, signed_flux=flux,
                               area_defect=area_difference, flux_defect=flux_difference,
                               max_normal_displacement=normal_motion)
    volume = 0.
    for ids in cells:
        a, b, c, d = (current[node] for node in ids)
        volume += abs(dot(sub(b, a), cross(sub(c, a), sub(d, a))))/6.
    volume_difference = abs(volume-history[-1]['endpoint_volume'])
    assert volume_difference < 2e-12
    return dict(ports=result, endpoint_volume_from_tetrahedra=volume, endpoint_volume_defect=volume_difference)

def circuit_audit(rows, faces, models, case):
    errors = {}
    def add(name, value): errors[name] = max(errors.get(name, 0.), abs(value))
    indexed = {(int(r['step']),int(r['tag'])):r for r in faces}
    assert len(indexed) == len(faces) == len(rows)*len(models)
    for row in rows:
        for model in models:
            tag = model['tag']
            face = indexed[int(row['step']),tag]
            assert row['time'] == face['time'] and row['accepted_dt'] == face['accepted_dt']
            suffix = '' if case == 'single' else '_'+str(tag)
            assert int(row['rcr_tag'+suffix]) == tag and 'distal_pressure_time' not in model
            for phase in ('stage','endpoint'):
                q = row[phase+'_rcr_flow'+suffix]
                pb = row[phase+'_rcr_pressure'+suffix]
                pc = row[phase+'_capacitor_pressure'+suffix]
                add(phase+'_face_flow', q-face[phase+'_outward_flow'])
                add(phase+'_face_pressure', pb-face[phase+'_prescribed_pressure'])
                add(phase+'_proximal_relation', face[phase+'_prescribed_pressure']-pc-model['proximal_resistance']*face[phase+'_outward_flow'])
                add(phase+'_pressure_power', face[phase+'_pressure_power']+face[phase+'_outward_flow']*face[phase+'_prescribed_pressure'])
                if phase == 'stage':
                    add('stage_capacitor_ode', model['compliance']*row['stage_capacitor_rate'+suffix]-face['stage_outward_flow']+(pc-model['distal_pressure'])/model['distal_resistance'])
                    if case == 'single': add('applied_pressure', row['applied_pressure']-face['stage_prescribed_pressure'])
    assert max(errors.values()) < 2e-10
    return dict(max_abs=max(errors.values()), by_relation=errors)

def history_compare(before, after):
    before = {r['step']:r for r in before}
    maxima = {}
    for row in after:
        old = before[row['step']]
        assert old.keys() == row.keys()
        for key in ('time','accepted_dt','evaluation_time'):
            assert abs(row[key]-old[key]) < 1e-14
        for key in row:
            if 'rcr' in key or 'capacitor' in key:
                maxima[key] = max(maxima.get(key,0.),abs(row[key]-old[key]))
    maximum = max(maxima.values())
    assert maximum < 2e-9
    return dict(max_abs=maximum, by_field=maxima)

RUNS = {
    'single': [('direct',1,None,0),('gamg-baseline-two',2,'gamg',0),('split-one',1,'split',1),
               ('gamg-two',2,'gamg',1),('boomeramg-two',2,'boomeramg',1),('adaptive-two',2,'gamg',1),
               ('checkpoint',2,'gamg',1),('resume',2,'boomeramg',1)],
    'multiple': [('direct-two',2,None,0),('gamg-baseline-two',2,'gamg',0),('split-one',1,'split',2),
                 ('gamg-two',2,'gamg',2),('boomeramg-two',2,'boomeramg',2)]}
result = dict(production_source='28e6d54701abced040752aff70b69d29b35f1d01',
              driver_source='ad08887f8b357ef16e6a6b49b89d968f531f8053',
              audit_method='Independent Python parsing of saved files; no solver/build/test launch; no imports from verification helpers',
              raw_directory=str(RAW.relative_to(REPO)), runs={}, comparisons={}, performance={})
fields_by_run, rows_by_run, configs_by_run = {}, {}, {}
for case, runs in RUNS.items():
    directory = RAW/case
    mesh = load_mesh(directory)
    for label, ranks, velocity, port_count in runs:
        key = case+'/'+label
        config = json.loads(read(directory/(label+'.json')))
        configs_by_run[key] = config
        domains = config['fsi']['domains']
        models = [domains['rcr_outlet']] if case == 'single' else domains['rcr_outlets']
        prefix = label+'_restart2' if label == 'resume' else label
        rows = csv_rows(directory/(prefix+'.csv'))
        rows_by_run[key] = rows
        faces = csv_rows(directory/(prefix+'_pressure_faces.csv'))
        fields, field_info = load_fields(directory,label,ranks)
        fields_by_run[key] = fields
        log = read(directory/(label+'.log'))
        assert log.splitlines().count('status=success') == 1
        assert len(records(log,'fsi_step=')) == len(rows)
        assert not any(marker in log for marker in ('linear_residual_unavailable','linear_iteration_limit_residual ','step_retry='))
        min_j = min(r[k] for r in rows for k in ('stage_min_fluid_j','stage_min_solid_j','endpoint_min_fluid_j','endpoint_min_solid_j'))
        max_balance = max(abs(r[k]) for r in rows for k in ('evaluation_body_balance','evaluation_power_balance'))
        assert min_j > 0 and max_balance < 2e-9
        reports = records(log,'solver_report ')
        residuals = records(log,'linear_residual ')
        nodes = records(log,'solver_node ')
        stats = records(log,'rcr_port_stats ')
        assert all(int(n['ksp_reason']) > 0 and int(n['pc_reason']) == 0 for n in nodes)
        info = dict(ranks=ranks, accepted_steps=len(rows), steps=[int(r['step']) for r in rows],
                    times=[r['time'] for r in rows], accepted_dt=[r['accepted_dt'] for r in rows],
                    newton_iterations=sum(int(r['snes_iterations']) for r in rows),
                    min_recorded_determinant=min_j, max_body_or_power_balance=max_balance,
                    fields=field_info, circuit=circuit_audit(rows,faces,models,case),
                    geometry=geometry_audit(fields,mesh,models,rows,faces,case),
                    solver_node_records=len(nodes), true_residual_samples=len(residuals))
        if velocity is None:
            assert not reports and not nodes and not residuals and not stats
            info['direct_reference_diagnostic_limit'] = 'No solver_report/linear_report; Newton counts imply corrections but their true linear residuals and reason codes were not recorded'
        else:
            assert len(reports) == len(rows)
            assert all(int(r['linear_started']) == int(r['linear_completed']) == int(row['snes_iterations'])
                       and int(r['snes_reason']) > 0 and int(r['ksp_reason']) > 0 and int(r['domain_rejections']) == 0
                       for r,row in zip(reports,rows))
            assert sum(int(r['linear_completed']) for r in reports) == len(residuals)
            ratios=[]
            for residual in residuals:
                norm,rhs=float(residual['norm']),float(residual['rhs_norm'])
                assert math.isfinite(norm) and math.isfinite(rhs) and norm>=0 and rhs>=0
                ratio=norm/max(1e-12,1e-9*rhs)
                assert ratio <= 1
                ratios.append(ratio)
            assert len(nodes)>0
            info.update(worst_true_residual_ratio=max(ratios),
                        nonlinear_reason_values=sorted(set(int(r['snes_reason']) for r in reports)),
                        outer_reason_values=sorted(set(int(r['ksp_reason']) for r in reports)),
                        nested_reason_values=sorted(set(int(n['ksp_reason']) for n in nodes)),
                        dofs=sorted(set(int(r['dofs']) for r in reports)))
            for name in ('linear_iterations','linear_started','linear_completed','jacobian_assemblies',
                         'user_schur_updates','pc_refreshes','pc_reuses','pc_context_refreshes'):
                info[name]=sum(int(r[name]) for r in reports)
            for name in ('linear_seconds','schur_setup_seconds','solve_seconds'):
                info[name]=sum(float(r[name]) for r in reports)
            if velocity in ('gamg','boomeramg'):
                target=('rcr_bulk_' if port_count else '')+'fieldsplit_dynamics_fieldsplit_velocity_'
                leaves=[n for n in nodes if n['prefix']==target]
                expected='gamg' if velocity=='gamg' else 'hypre'
                assert len(leaves)==len(rows)*ranks and all(n['ksp']=='preonly' and n['pc']==expected for n in leaves)
                if velocity=='boomeramg': assert 'pc_coupled_boomeramg prefix='+target in log
                info['verified_velocity_leaf']=dict(prefix=target,ksp='preonly',pc=expected,records=len(leaves))
            if port_count:
                assert len(stats)==len(rows)*ranks
                assert all(int(s['ports'])==port_count and int(s['responses'])==port_count*int(s['rebuilds'])
                           and int(s['setup_reductions'])==int(s['rebuilds'])
                           and int(s['apply_reductions'])==int(s['applications']) for s in stats)
                final=[]
                for rank in range(ranks):
                    history=[s for s in stats if int(s['rank'])==rank]
                    final.append({k:int(history[-1][k]) for k in ('ports','rebuilds','responses','setup_reductions','applications','apply_reductions')})
                assert all(s==final[0] for s in final)
                info['port_stats_final_per_rank']=final[0]
                assert final[0]['applications']==info['linear_iterations']
            else:
                assert not stats
            if label=='adaptive-two':
                assert all(int(r['pc_refreshes'])+int(r['pc_reuses'])==int(r['linear_completed']) for r in reports)
                assert info['pc_refreshes']==8 and info['pc_reuses']==4 and info['jacobian_assemblies']==12
                assert info['user_schur_updates']==info['pc_refreshes']==info['port_stats_final_per_rank']['rebuilds']
                assert set(r['solver_generation'] for r in reports)=={'1'}
                info['adaptive_generation']=1
        result['runs'][key]=info
    reference_key=case+'/'+runs[0][0]
    for label, _, velocity, _ in runs:
        if velocity is None or label=='checkpoint': continue
        key=case+'/'+label
        # Configuration must agree apart from output target across solver choices.
        cfg={k:v for k,v in configs_by_run[key].items() if k!='output'}
        refcfg={k:v for k,v in configs_by_run[reference_key].items() if k!='output'}
        assert cfg==refcfg
        result['comparisons'][key]=dict(reference=reference_key,
            fields=compare_fields(fields_by_run[reference_key],fields_by_run[key]),
            circuit_history=history_compare(rows_by_run[reference_key],rows_by_run[key]))
    base=result['runs'][case+'/gamg-baseline-two'];wrapped=result['runs'][case+'/gamg-two']
    result['performance'][case]={name:dict(baseline=base[name],wrapped=wrapped[name],relative_change=wrapped[name]/base[name]-1)
                                for name in ('linear_iterations','linear_seconds','schur_setup_seconds','solve_seconds')}
result['restart_comparison']=dict(reference='single/boomeramg-two',
    fields=compare_fields(fields_by_run['single/boomeramg-two'],fields_by_run['single/resume']),
    circuit_history=history_compare(rows_by_run['single/boomeramg-two'],rows_by_run['single/resume']),
    checkpoint_steps=result['runs']['single/checkpoint']['steps'],resume_steps=result['runs']['single/resume']['steps'],
    checkpoint_velocity_pc='gamg',resume_velocity_pc='hypre/boomeramg')
result['summary']=dict(runs=len(result['runs']),accepted_steps=sum(x['accepted_steps'] for x in result['runs'].values()),
    observed_true_residual_samples=sum(x['true_residual_samples'] for x in result['runs'].values()),
    newton_iterations=sum(x['newton_iterations'] for x in result['runs'].values()),
    uninstrumented_direct_newton_iterations=sum(x['newton_iterations'] for x in result['runs'].values() if 'direct_reference_diagnostic_limit' in x),
    solver_node_records=sum(x['solver_node_records'] for x in result['runs'].values()),
    max_field_difference=max(x['fields']['max_abs'] for x in result['comparisons'].values()),
    max_circuit_history_difference=max(x['circuit_history']['max_abs'] for x in result['comparisons'].values()),
    max_circuit_defect=max(x['circuit']['max_abs'] for x in result['runs'].values()),
    worst_true_residual_ratio=max(x.get('worst_true_residual_ratio',0) for x in result['runs'].values()),
    max_raw_geometry_area_defect=max(p['area_defect'] for x in result['runs'].values() for p in x['geometry']['ports'].values()),
    max_raw_geometry_flux_defect=max(p['flux_defect'] for x in result['runs'].values() for p in x['geometry']['ports'].values()),
    max_raw_endpoint_volume_defect=max(x['geometry']['endpoint_volume_defect'] for x in result['runs'].values()),
    min_recorded_determinant=min(x['min_recorded_determinant'] for x in result['runs'].values()))
assert result['summary']['runs']==13 and result['summary']['accepted_steps']==43
assert result['summary']['observed_true_residual_samples']==96 and result['summary']['newton_iterations']==114
suite=ET.fromstring(read(REPO/'build/rcr-port/fsi-ad08887.xml'))
assert int(suite.attrib['tests'])==1 and int(suite.attrib['failures'])==0 and int(suite.attrib['skipped'])==0
result['ctest']=dict(tests=1,failures=0,skipped=0,seconds=float(suite.find('testcase').attrib['time']))
# Only after independent reconstruction, compare claimed metrics to saved records.
claimed=json.loads(read(RAW/'metrics.json'))
for case,runs in RUNS.items():
    for label,_,velocity,_ in runs:
        if velocity is None: continue
        key=case+'/'+label
        item=claimed[case]['restart' if label=='resume' else label]
        actual=result['runs'][key]
        assert item['corrections']==actual['true_residual_samples']
        assert item['outer_iterations']==actual['linear_iterations']
        assert item['worst_true_residual_ratio']==actual['worst_true_residual_ratio']
        if label!='checkpoint':
            comparison=result['restart_comparison'] if label=='resume' else result['comparisons'][key]
            assert abs(item['field_error']-comparison['fields']['max_abs'])<1e-20
            assert abs(item['circuit_defect']-actual['circuit']['max_abs'])<1e-20
result['metrics_crosscheck']='All listed field errors, circuit defects, correction counts, outer iteration totals and true-residual ratios match independent reconstruction'
result['performance_limit']='Single shared-host samples at 350 and 1020 DoF; timings are sums of solver_report phase fields, not controlled repeated benchmarks or whole-job wall times; no stable speedup/scaling claim'
for path in ('build/rcr-port/fsi-ad08887.log','build/rcr-port/fsi-ad08887-LastTest.log','build/rcr-port/independent-algebra-audit.json',
             'tests/verify_rcr_port_fsi.py','src/algebra/rcr_port_pc.cpp','include/eonsim/rcr_port_pc.hpp'):
    read(REPO/path)
read(Path(__file__))
result['sha256']=HASHES
out=REPO/'build/rcr-port/independent-fsi-audit.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(output=str(out.relative_to(REPO)),summary=result['summary'],performance=result['performance'],ctest=result['ctest'],hashed_files=len(HASHES)),indent=2))
