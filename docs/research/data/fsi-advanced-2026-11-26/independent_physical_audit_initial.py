"""Read-only numerical audit of saved FSI runs; never launches a solver.

Uses only Python standard-library parsing. The production receipt supplies the
run inventory and historical hashes, never numerical pass/fail results.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 2e-9


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def records(text, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line))
            for line in text.splitlines() if line.startswith(prefix)]


def read_csv(path):
    with path.open() as stream:
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    need(rows and all(math.isfinite(x) for row in rows for x in row.values()), str(path)+' nonfinite/empty history')
    return rows


def difference(expected, actual):
    need(expected.keys() == actual.keys(), 'physical node/field sets changed')
    largest = 0.
    location = None
    by_field = {}
    for key, first in expected.items():
        second = actual[key]
        need(len(first) == len(second), 'physical component count changed')
        for c, (a, b) in enumerate(zip(first, second)):
            delta = abs(a-b)
            label = key[0]+'/'+key[2]
            by_field[label] = max(by_field.get(label, 0.), delta)
            if delta > largest:
                largest, location = delta, dict(domain=key[0], node=key[1], field=key[2], component=c)
    need(largest <= LIMIT, 'physical field gate failed: '+str(largest))
    return dict(max_absolute=largest, location=location, by_field=by_field)


def fields(directory, stem, ranks):
    owned, ghosts, topology = {}, [], {}
    files = []
    for domain, suffix in [('fluid', ''), ('solid', '_solid')]:
        pieces, support = [], set()
        for rank in range(ranks):
            path = directory/(stem+suffix+(f'_rank{rank}' if ranks > 1 else '')+'.vtu')
            files.append(path)
            tree = ET.parse(path)
            piece = tree.find('.//Piece')
            need(piece is not None, 'missing VTU Piece: '+str(path))
            count = int(piece.attrib['NumberOfPoints'])
            arrays = {}
            for a in tree.findall('.//PointData/DataArray'):
                name = a.attrib['Name']
                need(name not in arrays and a.attrib.get('format') == 'ascii', 'duplicate/non-ASCII point array')
                width = int(a.attrib.get('NumberOfComponents', '1'))
                values = tuple(map(float, (a.text or '').split()))
                arrays[name] = (width, values)
            coords = tree.find('.//Points/DataArray')
            arrays['coordinates'] = (3, tuple(map(float, (coords.text or '').split())))
            need({'mesh_node_id', 'owner'} <= arrays.keys(), 'missing physical identities')
            for width, values in arrays.values():
                need(width > 0 and len(values) == count*width and all(map(math.isfinite, values)), 'invalid physical array')
            ids, owners = arrays['mesh_node_id'][1], arrays['owner'][1]
            need(all(v.is_integer() for v in ids) and all(v.is_integer() and 0 <= v < ranks for v in owners), 'invalid node id/owner')
            cells = {a.attrib['Name']: tuple(map(int, (a.text or '').split())) for a in tree.findall('.//Cells/DataArray')}
            data = {a.attrib['Name']: tuple(map(int, (a.text or '').split())) for a in tree.findall('.//CellData/DataArray')}
            need(all(0 <= i < count for i in cells['connectivity']), 'invalid connectivity index')
            ncells = int(piece.attrib['NumberOfCells'])
            need(len(cells['offsets']) == ncells == len(data['mesh_element_id']) == len(data['physical_tag']), 'invalid cell array lengths')
            previous = 0
            for j, end in enumerate(cells['offsets']):
                need(previous <= end <= len(cells['connectivity']), 'invalid cell offsets')
                nodes = tuple(int(ids[i]) for i in cells['connectivity'][previous:end])
                support.update(nodes)
                key = (domain, data['mesh_element_id'][j])
                value = (data['physical_tag'][j], cells['types'][j], nodes)
                need(key not in topology, 'duplicate physical element ownership')
                topology[key] = value
                previous = end
            need(previous == len(cells['connectivity']), 'unused cell connectivity')
            pieces.append(arrays)
        need(support, 'empty physical domain')
        for rank, arrays in enumerate(pieces):
            for i, (node, owner) in enumerate(zip(arrays['mesh_node_id'][1], arrays['owner'][1])):
                if int(node) not in support:
                    continue
                for name, (width, values) in arrays.items():
                    if name in ('mesh_node_id', 'owner', 'algebra_node_id'):
                        continue
                    key = (domain, int(node), name)
                    value = values[width*i:width*(i+1)]
                    if int(owner) == rank:
                        need(key not in owned, 'duplicate owned physical node')
                        owned[key] = value
                    else:
                        ghosts.append((key, value))
    ghost_error = 0.
    for key, value in ghosts:
        need(key in owned and len(value) == len(owned[key]), 'ghost without matching owner')
        ghost_error = max(ghost_error, *(abs(x-y) for x, y in zip(value, owned[key])))
    need(ghost_error <= LIMIT, 'owner/ghost gate failed')
    return dict(values=owned, topology=topology, ghost_error=ghost_error,
                files=files, scalar_components=sum(map(len, owned.values())))


def history_difference(expected, actual):
    need(len(expected) == len(actual), 'history length changed')
    largest = 0.
    by_column = {}
    for a, b in zip(expected, actual):
        need(a.keys() == b.keys(), 'history columns changed')
        for key in a:
            if key == 'snes_iterations':
                continue
            error = abs(a[key]-b[key])
            by_column[key] = max(by_column.get(key, 0.), error)
            if key in ('step', 'time', 'accepted_dt'):
                need(error <= 1e-13, 'accepted time grid changed')
            largest = max(largest, error)
    need(largest <= LIMIT, 'history physical gate failed')
    return dict(max_absolute=largest, by_column=by_column,
                ignored_column='snes_iterations (counted separately)')


def audit_log(text, rows, ranks, mode, configuration):
    reports = records(text, 'solver_report ')
    steps = records(text, 'fsi_step=')
    residuals = records(text, 'linear_residual ')
    nonlinear = records(text, 'field_residual ')
    need(text.splitlines().count('status=success') == 1, 'missing/duplicate success completion')
    need(not any(s in text for s in ['linear_residual_unavailable', 'linear_iteration_limit_residual ', 'step_retry=']), 'rejected/unmeasured solve')
    need(len(reports) == len(steps) == len(rows) > 0 and residuals, 'incomplete accepted-step or linear diagnostics')
    need(sum(int(r['linear_completed']) for r in reports) == len(residuals), 'linear count mismatch')
    need(sum(int(r['snes_iterations']) for r in steps) == sum(int(r['snes_iterations']) for r in rows) == len(residuals), 'Newton/CSV/correction count mismatch')
    mapping = dict(step='fsi_step', endpoint_position='position', endpoint_velocity='velocity',
                   evaluation_fluid_force='stage_fluid_force', evaluation_body_balance='stage_body_balance',
                   evaluation_interface_power='stage_interface_power', evaluation_body_power='stage_body_power',
                   evaluation_power_balance='stage_power_balance')
    max_csv_log = 0.
    step_data, start = [], 0
    for report, step, row in zip(reports, steps, rows):
        need(int(report['ranks']) == ranks and int(report['snes_reason']) > 0 and int(report['ksp_reason']) > 0, 'failed nonlinear/root linear solve')
        need(report['ksp'] == ('preonly' if mode == 'direct' else 'fgmres'), 'wrong outer solver')
        if mode == 'direct':
            need(report['pc'] == 'lu', 'direct reference did not use an LU preconditioner')
        completed = int(report['linear_completed'])
        need(int(report['linear_started']) == completed == int(row['snes_iterations']), 'unfinished Newton correction')
        need(int(report['domain_rejections']) == 0, 'domain rejection was observed')
        batch = residuals[start:start+completed]
        start += completed
        need([int(r['solve']) for r in batch] == list(range(1, completed+1)), 'noncontiguous linear solve diagnostics')
        ratios = []
        for r in batch:
            norm, rhs = float(r['norm']), float(r['rhs_norm'])
            need(math.isfinite(norm) and math.isfinite(rhs) and min(norm, rhs) >= 0, 'nonfinite residual')
            limit = 1e-12+1e-10*rhs
            ratio = norm/limit
            need(ratio <= 1., 'original-Jacobian scalar residual gate failed')
            ratios.append(dict(solve=int(r['solve']), norm=norm, rhs_norm=rhs, limit=limit, ratio=ratio))
        for key, value in row.items():
            other = mapping.get(key, key)
            if other in step:
                max_csv_log = max(max_csv_log, abs(value-float(step[other])))
        need(max_csv_log <= 1e-13, 'CSV/log accepted history mismatch')
        callbacks = int(report['jacobian_callbacks'])
        initial = int(report['initial_jacobian_assemblies'])
        reuse = int(report['initial_jacobian_reuses'])
        need(callbacks == int(row['snes_iterations']) and int(report['jacobian_assemblies']) == initial+callbacks-reuse,
             'Jacobian/Newton accounting mismatch')
        step_data.append(dict(step=int(row['step']), time=row['time'], accepted_dt=row['accepted_dt'],
                              newton_iterations=int(row['snes_iterations']), outer_iterations=int(report['linear_iterations']),
                              linear_residuals=ratios,
                              snes_reason=int(report['snes_reason']), ksp_reason=int(report['ksp_reason'])))
    need(nonlinear, 'nonlinear field acceptance diagnostics missing')
    nonlinear_ratio = 0.
    for r in nonlinear:
        rms, limit = float(r['rms']), float(r['limit'])
        bound, cap = float(r['constraint_max']), float(r['constraint_limit'])
        need(all(map(math.isfinite, [rms, limit, bound, cap])) and rms <= limit and bound <= cap and int(r['accepted']) == 1,
             'nonlinear field acceptance failed')
        nonlinear_ratio = max(nonlinear_ratio, rms/limit if limit else 0., bound/cap if cap else 0.)
    schedule = configuration.get('time_control', {}).get('step_sizes')
    if schedule is None:
        schedule = [configuration['fsi']['dt']]*configuration['fsi']['steps']
    for row in rows:
        n = int(row['step'])
        need(row['step'] == n and 1 <= n <= len(schedule), 'invalid accepted step')
        need(abs(row['time']-math.fsum(schedule[:n])) <= 1e-13 and abs(row['accepted_dt']-schedule[n-1]) <= 1e-13, 'case/accepted time grid mismatch')
        need(abs(row['evaluation_body_balance']) <= LIMIT and abs(row['evaluation_power_balance']) <= LIMIT, 'accepted balance failed')
        need(all(v > 0 for k, v in row.items() if k.endswith('_j')), 'nonpositive accepted geometry determinant')
    result = dict(accepted_steps=len(rows), corrections=len(residuals), newton_iterations=sum(int(r['snes_iterations']) for r in rows),
                  outer_iterations=sum(int(r['linear_iterations']) for r in reports), dofs=int(reports[-1]['dofs']),
                  max_true_residual_ratio=max(x['ratio'] for s in step_data for x in s['linear_residuals']),
                  max_nonlinear_field_limit_ratio=nonlinear_ratio, csv_log_max_difference=max_csv_log,
                  steps=step_data, linear_seconds=math.fsum(float(r['linear_seconds']) for r in reports),
                  schur_setup_seconds=math.fsum(float(r['schur_setup_seconds']) for r in reports),
                  peak_rss_max_bytes=max(float(r['peak_rss_max_bytes']) for r in reports),
                  observed_retry_markers=0, successful_completion_markers=1)
    hierarchy = records(text, 'pc_field_amg ')
    solver_nodes = records(text, 'solver_node ')
    transfers = records(text, 'pc_field_amg_level ')
    pressure = records(text, 'pressure_schur ')
    patches = records(text, 'interface_patch_pc ')
    if mode not in ('direct', 'aggregate_nodal'):
        need(hierarchy and all(int(r['rigid_modes']) == 1 and int(r['coarse_rows']) > 0 for r in hierarchy), 'field-aware hierarchy not observed')
        need(all(float(r['reproduction_error']) <= 1e-10 and int(r['fine_rows']) > int(r['coarse_rows']) for r in transfers), 'invalid hierarchy transfer')
        need(all(any(n.get('prefix') == h['prefix'] and n.get('pc') == 'mg' for n in solver_nodes) for h in hierarchy),
             'reported field hierarchy not found in actual solver tree')
    if mode.split('_')[0] in ('lsc', 'bfbt', 'pcd'):
        need(pressure and all(r['kind'] == mode.split('_')[0] for r in pressure), 'pressure backend not observed')
    if 'vanka' in mode:
        need(patches and {int(r['rank']) for r in patches} == set(range(ranks)), 'missing rank patch diagnostics')
        need(all(int(r['fp32'])+int(r['fp64']) == int(r['patches']) for r in patches), 'factor accounting mismatch')
        if mode.endswith('double'):
            need(all(int(r['fp32']) == 0 for r in patches), 'unexpected FP32 factor')
        else:
            need(any(int(r['fp32']) > 0 for r in patches), 'single mode never constructed FP32 factors')
    result['backend_observation'] = dict(field_amg=hierarchy, field_amg_transfers=transfers, pressure=pressure, patches=patches)
    return result


def circuit(directory, label, rows, model):
    path = directory/(label+'_pressure_faces.csv')
    faces = [r for r in read_csv(path) if int(r['tag']) == int(model['tag'])]
    need(len(faces) == len(rows), 'missing RCR face history')
    worst = 0.
    for row, face in zip(rows, faces):
        need(row['step'] == face['step'] and row['time'] == face['time'], 'RCR accepted time mismatch')
        for stage in ('stage', 'endpoint'):
            q, p = face[stage+'_outward_flow'], face[stage+'_prescribed_pressure']
            pc = row[stage+'_capacitor_pressure']
            errors = [row[stage+'_rcr_flow']-q, row[stage+'_rcr_pressure']-p,
                      p-pc-model['proximal_resistance']*q, face[stage+'_pressure_power']+p*q]
            if stage == 'stage':
                errors += [model['compliance']*row['stage_capacitor_rate']-q+(pc-model['distal_pressure'])/model['distal_resistance'], row['applied_pressure']-p]
            worst = max(worst, *map(abs, errors))
    need(worst <= 2e-10, 'RCR equation/face diagnostic failed')
    return dict(max_absolute_defect=worst, gate=2e-10, path=str(path))


def observations(cases):
    result = dict(scaling=[], coupling=[], same_case_comparisons=[])
    scalings = {}
    for case in cases:
        runs = {r['mode']: r for r in case['runs'] if r['status'] == 'passed' and r['kind'] == 'full'}
        name = Path(case['directory']).name
        match = re.fullmatch(r'scaling-n(\d+)-r(\d+)', name)
        if match:
            for mode, run in runs.items():
                if mode == 'direct':
                    continue
                scalings.setdefault((case['ranks'], mode), []).append(dict(n=int(match[1]), dofs=run['dofs'],
                    outer_iterations=run['outer_iterations'], corrections=run['corrections'],
                    iterations_per_correction=run['outer_iterations']/run['corrections']))
        if name.startswith('coupling-'):
            physical = case['physical_configuration']['fsi']
            data = dict(case=name, ranks=case['ranks'], solid_fluid_density_ratio=physical['solid_density']/physical['density'],
                        dt=physical['dt'], outer_iterations={k:v['outer_iterations'] for k,v in runs.items()})
            if {'bfbt_field', 'bfbt_vanka_single', 'pcd_vanka_single'} <= runs.keys():
                before = runs['bfbt_field']['outer_iterations']
                after = runs['bfbt_vanka_single']['outer_iterations']
                data['bfbt_patch_iteration_reduction_fraction'] = (before-after)/before
                data['pcd_to_bfbt_patch_iteration_ratio'] = runs['pcd_vanka_single']['outer_iterations']/after
            result['coupling'].append(data)
        if 'nodal_field' in runs:
            baseline = runs['nodal_field']['outer_iterations']
            data = dict(case=name, ranks=case['ranks'], nodal_field_outer_iterations=baseline,
                        relative_outer_iterations={k: v['outer_iterations']/baseline for k,v in runs.items() if k != 'direct'})
            if {'pcd_vanka_double', 'pcd_vanka_single'} <= runs.keys():
                storage = {}
                for mode in ('pcd_vanka_double', 'pcd_vanka_single'):
                    latest = {}
                    for p in runs[mode]['backend_observation']['patches']:
                        rank = int(p['rank'])
                        if rank not in latest or int(p['rebuilds']) > int(latest[rank]['rebuilds']):
                            latest[rank] = p
                    storage[mode] = sum(int(p['factor_bytes']) for p in latest.values())
                data['last_reported_patch_factor_bytes_sum_across_ranks'] = storage
                data['fp32_to_fp64_patch_factor_storage_ratio'] = storage['pcd_vanka_single']/storage['pcd_vanka_double']
                data['fp32_vs_fp64_outer_iteration_difference'] = runs['pcd_vanka_single']['outer_iterations']-runs['pcd_vanka_double']['outer_iterations']
            result['same_case_comparisons'].append(data)
    for (ranks, mode), samples in sorted(scalings.items()):
        samples.sort(key=lambda r: r['n'])
        first, last = samples[0], samples[-1]
        result['scaling'].append(dict(ranks=ranks, mode=mode, samples=samples,
                                      dof_growth=last['dofs']/first['dofs'],
                                      iteration_growth=last['iterations_per_correction']/first['iterations_per_correction'],
                                      fitted_endpoint_log_slope=math.log(last['iterations_per_correction']/first['iterations_per_correction'])/math.log(last['dofs']/first['dofs'])))
    result['interpretation'] = [
        'These are integer iteration observations from matched physical inputs and tolerance settings, not repeatable timing estimates.',
        'For 703 to 5367 DOFs, nodal_field rises 77 to 108 iterations on one rank and 82 to 131 on two ranks. This is finite-grid moderate growth, not proof of mesh independence.' if scalings else 'The initial campaign alone has no mesh refinement sweep.',
        'PCD is substantially more iteration-expensive than nodal or BFBt in these saved source versions. No across-the-board pressure-preconditioner improvement is supported.',
        'The coupling sweep measures the added patch together with its selected precision; it does not isolate FP32 from FP64 there.',
        'Where the initial paired double/single patch runs exist, factor-array bytes halve and outer counts coincide; this does not establish halved total memory, lower bandwidth, or a timing speedup.'
    ]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    out = dict(schema=1, status='running', audit_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               auditor_script=str(Path(__file__).resolve()), auditor_sha256=sha(__file__),
               input_receipt=dict(path=str(args.receipt.resolve()), sha256=sha(args.receipt)),
               methods=dict(inventory='Original command list cross-checked against actual log, case JSON, CSV and VTU files; original numerical pass flags are not used.',
                            residual='Recalculate each norm/(1e-12+1e-10*rhs_norm) from original linear_residual log scalars, match every correction to solver reports and Newton counts. This is not a new offline J*dx-b evaluation.',
                            fields='Independently parse ASCII VTU; match owned values by domain/source mesh node; verify ghost values, cell identities/connectivity and finite shapes. Compare every physical point array plus deformed coordinates at every accepted step and final output.',
                            history='Independently parse all CSV columns; exclude only snes_iterations from physical difference, count it separately; verify time grid, log agreement, balances and positive Jacobians.',
                            restarts='Count checkpoint and resumed invocations separately; compare both against same-step direct reference and uninterrupted candidate.',
                            hashes='Rehash every original pinned artifact and all current campaign files. Separate original pins from hashes first recorded by this audit.'),
               cases=[], failures=[], limitations=[])
    pinned = {}
    for command in receipt['commands']:
        if command.get('log_sha256'):
            pinned[str(Path(command['log']).resolve())] = command['log_sha256']
    for case in receipt['cases']:
        for run in case['runs']:
            for artifact in run.get('artifacts', []):
                pinned[str(Path(artifact['path']).resolve())] = artifact['sha256']
            for artifact in run.get('partition', {}).get('files', []):
                pinned[str((Path(case['directory'])/artifact['path']).resolve())] = artifact['sha256']
    provenance = dict(build_source=receipt['build_source'], driver_source=receipt['source_commit'],
                      recorded_binary_sha256=receipt['executable_sha256'], recorded_binary_path=receipt['executable'], source_files=[])
    binary = Path(receipt['executable'])
    provenance['current_binary_sha256'] = sha(binary) if binary.is_file() else None
    provenance['recorded_binary_bytes_available_at_original_path'] = provenance['current_binary_sha256'] == provenance['recorded_binary_sha256']
    if not provenance['recorded_binary_bytes_available_at_original_path']:
        out['limitations'].append('The original executable path has been rebuilt; original executable identity is available only as the run-time receipt SHA256. No old binary was rebuilt or substituted during this audit.')
    source_pins = dict(receipt.get('helper_sha256', {}))
    source_pins['tests/verify_fsi_advanced_pc.py'] = receipt['driver_sha256']
    for path, expected in source_pins.items():
        result = subprocess.run(['git', 'show', receipt['source_commit']+':'+path], cwd=ROOT, capture_output=True)
        observed = hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None
        provenance['source_files'].append(dict(path=path, recorded_sha256=expected, git_blob_sha256=observed, matches=observed == expected))
        if observed != expected:
            out['failures'].append(dict(category='source_hash', path=path, expected=expected, observed=observed))
    out['software_provenance'] = provenance
    all_metrics, cache = [], {}
    for case in receipt['cases']:
        directory, ranks, config = Path(case['directory']), int(case['ranks']), case['configuration']
        name = directory.name
        case_out = dict(directory=str(directory), ranks=ranks,
                        physical_configuration=config, runs=[])
        out['cases'].append(case_out)
        commands = [c for c in receipt['commands'] if Path(c['log']).parent == directory and '-prepare' not in c['command']]
        modes = {r['label']: r['mode'] for r in case['runs']}
        for command in commands:
            label = command['label']
            mode = modes.get(label, modes.get('restart'))
            kind = 'checkpoint_start' if '-checkpoint' in command['command'] else 'restart_tail' if '-restart' in command['command'] else 'full'
            row_out = dict(label=label, mode=mode, kind=kind, status='running', recorded_exit_code=command.get('exit_code'),
                           recorded_wall_seconds=command.get('wall_seconds'), command=command['command'])
            case_out['runs'].append(row_out)
            try:
                need(command.get('exit_code') == 0 and not command.get('timeout'), 'recorded unsuccessful process exit')
                case_path = Path(command['command'][command['command'].index('-case')+1])
                actual_config = json.loads(case_path.read_text())
                need({k:v for k,v in actual_config.items() if k != 'output'} == {k:v for k,v in config.items() if k != 'output'}, 'run physical configuration differs from reference')
                history_stem = label+'_restart1' if kind == 'restart_tail' else label
                rows = read_csv(directory/(history_stem+'.csv'))
                text = (directory/(label+'.log')).read_text()
                metric = audit_log(text, rows, ranks, mode, config)
                expected_steps = list(range(1, int(config['fsi']['steps'])+1))
                if kind == 'checkpoint_start':
                    stop = int(command['command'][command['command'].index('-stop_after')+1])
                    expected_steps = expected_steps[:stop]
                elif kind == 'restart_tail':
                    expected_steps = expected_steps[1:]
                need([int(r['step']) for r in rows] == expected_steps, 'unexpected accepted steps for invocation')
                saved = {}
                for r in rows:
                    step = int(r['step'])
                    saved[step] = fields(directory, history_stem+f'_step{step}', ranks)
                final = fields(directory, label, ranks)
                need(final['topology'] == saved[expected_steps[-1]]['topology'], 'final/saved topology mismatch')
                row_out['final_vs_last_saved'] = difference(saved[expected_steps[-1]]['values'], final['values'])
                row_out['owner_ghost_max_difference'] = max(final['ghost_error'], *(v['ghost_error'] for v in saved.values()))
                reference = saved if label == 'reference' else cache[(name, 'reference')]['saved']
                reference_rows = rows if label == 'reference' else [r for r in cache[(name, 'reference')]['rows'] if int(r['step']) in expected_steps]
                comparisons = []
                for step, value in saved.items():
                    need(reference[step]['topology'] == value['topology'], 'candidate/reference cell topology changed')
                    comparisons.append(dict(step=step, **difference(reference[step]['values'], value['values'])))
                row_out['fields_vs_direct_by_step'] = comparisons
                row_out['field_max_difference'] = max(v['max_absolute'] for v in comparisons)
                row_out['history_vs_direct'] = history_difference(reference_rows, rows)
                row_out['history_max_difference'] = row_out['history_vs_direct']['max_absolute']
                row_out['physical_scalar_components'] = final['scalar_components']
                if kind != 'full':
                    uninterrupted = cache[(name, mode)]
                    row_out['restart_fields_vs_uninterrupted'] = [dict(step=s, **difference(uninterrupted['saved'][s]['values'], v['values'])) for s,v in saved.items()]
                    row_out['restart_history_vs_uninterrupted'] = history_difference([r for r in uninterrupted['rows'] if int(r['step']) in expected_steps], rows)
                model = config['fsi'].get('domains', {}).get('rcr_outlet')
                if model:
                    row_out['rcr_circuit'] = circuit(directory, history_stem, rows, model)
                row_out.update(metric)
                row_out['status'] = 'passed'
                cache[(name, label)] = dict(saved=saved, rows=rows, final=final)
                all_metrics.append(row_out)
                print(name, label, 'passed', metric['accepted_steps'], metric['outer_iterations'], row_out['field_max_difference'], flush=True)
            except Exception as exc:
                row_out.update(status='failed', error=str(exc))
                out['failures'].append(dict(case=name, label=label, error=str(exc)))
    integrity = []
    campaign_root = args.receipt.resolve().parent
    for path in sorted(p for p in campaign_root.rglob('*') if p.is_file()):
        digest = sha(path)
        expected = pinned.pop(str(path.resolve()), None)
        item = dict(path=str(path.relative_to(campaign_root)), sha256=digest, bytes=path.stat().st_size,
                    pinned_by_original_receipt=expected is not None)
        if expected:
            item['original_pin_matches'] = digest == expected
            if digest != expected:
                out['failures'].append(dict(category='artifact_hash', path=str(path), expected=expected, observed=digest))
        integrity.append(item)
    for path, digest in pinned.items():
        out['failures'].append(dict(category='missing_original_pinned_artifact', path=path, expected=digest))
    out['artifact_integrity'] = dict(files=integrity, original_pinned_count=sum(x['pinned_by_original_receipt'] for x in integrity),
                                     newly_hashed_count=sum(not x['pinned_by_original_receipt'] for x in integrity))
    groups = {kind: [r for r in all_metrics if r['kind'] == kind] for kind in ('full', 'checkpoint_start', 'restart_tail')}
    summary = dict(solver_invocations=sum(len(c['runs']) for c in out['cases']), passed_solver_invocations=len(all_metrics),
                   prepare_commands=sum('-prepare' in c['command'] for c in receipt['commands']),
                   accepted_step_records=sum(r['accepted_steps'] for r in all_metrics),
                   newton_iterations=sum(r['newton_iterations'] for r in all_metrics),
                   measured_linear_corrections=sum(r['corrections'] for r in all_metrics),
                   invocation_counts={k: len(v) for k,v in groups.items()},
                   full_trajectory_accepted_step_records=sum(r['accepted_steps'] for r in groups['full']),
                   restart_trajectories=len(groups['restart_tail']),
                   max_true_residual_ratio=max((r['max_true_residual_ratio'] for r in all_metrics), default=None),
                   max_field_absolute_difference=max((r['field_max_difference'] for r in all_metrics), default=None),
                   max_history_absolute_difference=max((r['history_max_difference'] for r in all_metrics), default=None),
                   max_owner_ghost_difference=max((r['owner_ghost_max_difference'] for r in all_metrics), default=None),
                   raw_failure_count=len(out['failures']))
    out['summary'] = summary
    out['independent_comparisons'] = observations(out['cases'])
    out['limitations'] += [
        'Original assembled J, right-hand sides and correction vectors were not archived. The independently recalculated scalar gate relies on the original log of the explicit original-operator residual, not an offline reassembly or new matrix-vector product.',
        'Process exit codes and launcher wall times are historical command-receipt records; process exits cannot be independently observed again from saved files. Raw logs independently contain completion and accepted-step diagnostics.',
        'Mesh inputs and checkpoint/restart artifacts not pinned by the original receipt are hashed for the first time by this audit. Their numerical content is validated, but retrospective byte identity is not established for those unpinned files.',
        'Single short trajectories per configuration do not establish repeatable timing speedup, bandwidth reduction, MPI scalability or production-scale robustness. Rank counts are at most two in these physical campaigns.',
        'Preserved coarse candidates and finite-grid iteration trends do not establish mesh-independent asymptotic convergence. Pressure variants must be compared separately; correctness is not a pressure-iteration speedup claim.',
        'Patch factor_bytes describe stored local factor arrays, not total process memory or measured memory bandwidth. FP32 versus FP64 end-to-end performance requires controlled repeated samples.'
    ]
    out['status'] = 'passed_with_evidence_limits' if not out['failures'] else 'failed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, allow_nan=False)+'\n')
    print(json.dumps(summary, indent=2), flush=True)
    print('AUDIT', out['status'], str(args.output), flush=True)
    if out['failures']:
        print(json.dumps(out['failures'], indent=2), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
