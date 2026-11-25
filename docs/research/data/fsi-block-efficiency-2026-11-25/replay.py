#!/usr/bin/env python3
"""Independently replay the selected 66b0a62 FSI efficiency evidence.

Only Python's standard library is used. No solver, MPI process, build, repo
module, or archived Python code is executed. This verifies the stored numerical
evidence; it does not reproduce elapsed wall time or rerun the simulation.

Usage: python3 replay.py --archive evidence.tar.xz --sha256 HASH --work NEW_DIR
NEW_DIR must not exist. Extracted files remain in NEW_DIR/unpacked; the result is
written to NEW_DIR/replay.json and stdout, including on an audit failure.

Archive schema: exactly manifest.json plus the regular files in manifest.files.
The root manifest has exactly these required fields: format (integer 1),
original_repo (canonical absolute POSIX path), build_source_commit,
driver_commit, campaign_results (two repo-relative receipt paths),
script_snapshots (bare script name -> repo-relative snapshot path), and files
(records containing exactly path, bytes, sha256). The optional field
initial_screening_results names a historical receipt, verified by hash only.
All recorded absolute output paths are mapped by stripping original_repo.
Original receipt bytes are preserved. Extra archived historical evidence is
hash-verified but does not contribute to the selected campaign's pass totals.

The archive hash is supplied by the caller from the published evidence record;
the manifest's own assertions are never treated as numerical pass evidence.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import statistics
import sys
import tarfile
import xml.etree.ElementTree as ET


BUILD_COMMIT = '664a6238ab08a42639a6c180addc99ddbf38886b'
DRIVER_COMMIT = '66b0a62af6575d8a98d85b7c90d88d6e22666439'
EXECUTABLE_SHA256 = '654f809bc2e273d0c74d77ea2813859a7ca0ee2044e0f2729f4b20e8a113aed9'
FIXTURE_SHA256 = '662518aa06f1d9f3072c92910fcfd08c3788f0be8bf0875ec035ff6e0984fae6'
SCRIPT_HASHES = {
    'verify_fsi_block_efficiency.py': '83bd0d91f9f57299f796f297747c8fdf55f1ecb6ca35b2bf1a37d9848f7f0d20',
    'verify_fsi_tube.py': 'b62b51dc0e633643d330199cdab5d7fad1713f4a05f1099c7e461291f603d550',
    'verify_fsi_inlet.py': '5046ce811e749839c2d3babb11cdb533348ff7110b98d79c8ee324a7f7284162',
}
INPUT_HASHES = {
    's24-r3-w2-a6': {
        'case.json': '436d8bed9ac9aadb7def6defa1b0ffa7e10baf9642dc377018b50cc3fbd4f7a9',
        'fluid.msh': '1fa0f0964747eb27afe2521c77705a426066e940e4c27048a230647befd88d16',
        'solid.msh': 'abb75c9acbabb20976f5b1aec0c14330c4a9f6f8f7633bd62542dee4ab291db9',
    },
    's48-r4-w4-a6': {
        'case.json': '436d8bed9ac9aadb7def6defa1b0ffa7e10baf9642dc377018b50cc3fbd4f7a9',
        'fluid.msh': '7124e8f5a6a21a88731d109a79cd00ee15aaf324e81fdfa4d430d6459e7eabee',
        'solid.msh': '88e8adf13651217e6306f871e32cad4b7e621cc97893ed76fa67a8ee7ab14cd7',
    },
}
MODES = ('direct', 'coupled_nodal', 'added_mass', 'added_mass_fluid_onecycle',
         'twolevel_iterative', 'twolevel_onecycle')
GRIDS = {'coarse': ('s24-r3-w2-a6', 1, 1027, 'natural'),
         'fine': ('s48-r4-w4-a6', 2, 3024, 'rcm')}
EQUATIONS = {'mesh', 'pressure', 'structure', 'velocity'}
FIELDS = (('', {'velocity': 3, 'pressure': 1, 'mesh_displacement': 3}),
          ('_solid', {'velocity': 3, 'displacement': 3}))
TIMERS = ('linear_seconds', 'setup_seconds', 'schur_setup_seconds',
          'assembly_seconds', 'solve_seconds', 'linear_diagnostic_seconds')
TARGET = 'max(1e-23, 1e-10*rhs_norm)'
MARGIN = 1.00001
FIELD_LIMIT = 2e-6
# Exact positive KSPConvergedReason values in the pinned PETSc 3.23.7 header.
CONVERGED_REASONS = {1, 2, 3, 4, 5, 6, 7, 9}
ENVIRONMENT = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
TIMING_SEMANTICS = {
    'linear_seconds': 'rank-max KSP intervals, including PC setup and inner solves',
    'setup_seconds': 'nonlinear solve initialization, not total PC setup',
    'schur_setup_seconds': 'explicit tree configuration outside KSP intervals',
    'wall_seconds': 'Runner.command elapsed time, including launch and log read',
}


class AuditError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def number(value, where):
    require(not isinstance(value, bool), f'{where}: boolean is not a number')
    result = float(value)
    require(math.isfinite(result) and result >= 0., f'{where}: nonfinite or negative value {value}')
    return result


def integer(value, where, minimum=0):
    require(not isinstance(value, bool), f'{where}: boolean is not an integer')
    result = int(value)
    require(str(result) == str(value) and result >= minimum, f'{where}: invalid integer {value}')
    return result


def close(actual, stored, where):
    require(math.isclose(number(actual, where), number(stored, where),
                         rel_tol=2e-12, abs_tol=1e-300),
            f'{where}: recomputed {actual} differs from stored {stored}')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def hash_value(value, where):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value),
            f'{where}: invalid SHA256')
    return value


def reject_constant(value):
    raise AuditError(f'Invalid JSON numeric constant: {value}')


def finite_json_float(value):
    result = float(value)
    require(math.isfinite(result), f'Nonfinite JSON number: {value}')
    return result


def unique_object(items):
    result = {}
    for key, value in items:
        require(key not in result, f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant,
                      parse_float=finite_json_float, object_pairs_hook=unique_object)


def safe_parts(name):
    require(isinstance(name, str), 'Archive path must be a string')
    parts = name.split('/')
    require(name and not PurePosixPath(name).is_absolute()
            and not any(part in ('', '.', '..') for part in parts)
            and not any(char in name for char in ('\\', ':', '\0')),
            f'Unsafe archive path: {name!r}')
    return parts


def canonical_absolute(name, where):
    require(isinstance(name, str) and PurePosixPath(name).is_absolute()
            and str(PurePosixPath(name)) == name and name != '/'
            and '..' not in PurePosixPath(name).parts
            and not any(char in name for char in ('\\', ':', '\0')),
            f'{where}: noncanonical absolute POSIX path')
    return PurePosixPath(name)


def unpack_and_verify(archive, expected_hash, destination):
    require(sha256(archive) == hash_value(expected_hash, 'archive'), 'Archive SHA256 differs')
    destination.mkdir()
    names, unpacked_bytes = set(), 0
    with tarfile.open(archive, 'r:xz') as bundle:
        for member in bundle:
            parts = safe_parts(member.name)
            require(member.isreg() and not member.sparse, f'Nonregular archive member: {member.name}')
            require(member.name not in names, f'Duplicate archive member: {member.name}')
            names.add(member.name)
            unpacked_bytes += member.size
            require(len(names) <= 32768 and 0 <= member.size <= 256 * 1024 * 1024
                    and unpacked_bytes <= 2 * 1024 * 1024 * 1024,
                    'Archive exceeds bounded replay limits')
            path = destination.joinpath(*parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            require(path.stat().st_size == member.size, f'Incomplete extracted file: {member.name}')
    require('manifest.json' in names, 'Missing root manifest.json')
    manifest = read_json(destination / 'manifest.json')
    required = {'format', 'original_repo', 'build_source_commit', 'driver_commit',
                'campaign_results', 'script_snapshots', 'files'}
    require(isinstance(manifest, dict) and required <= set(manifest)
            and set(manifest) <= required | {'initial_screening_results'}, 'Manifest schema differs')
    require(type(manifest['format']) is int and manifest['format'] == 1, 'Manifest format differs')
    canonical_absolute(manifest['original_repo'], 'original_repo')
    require(manifest['build_source_commit'] == BUILD_COMMIT
            and manifest['driver_commit'] == DRIVER_COMMIT, 'Pinned source commits differ')
    records = {}
    require(isinstance(manifest['files'], list), 'Manifest files must be a list')
    for row in manifest['files']:
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
                'Manifest file-record schema differs')
        name = row['path']
        safe_parts(name)
        require(name != 'manifest.json' and name not in records and name in names,
                f'Duplicate, missing, or self-listed manifest file: {name}')
        path = destination.joinpath(*safe_parts(name))
        require(type(row['bytes']) is int and path.stat().st_size == integer(row['bytes'], name),
                f'Manifest size mismatch: {name}')
        require(sha256(path) == hash_value(row['sha256'], name), f'Manifest SHA256 mismatch: {name}')
        records[name] = row
    require(names == set(records) | {'manifest.json'}, 'Archive inventory differs from manifest')
    result_paths = manifest['campaign_results']
    require(isinstance(result_paths, list) and len(result_paths) == 2
            and len(set(result_paths)) == 2, 'Exactly two distinct campaign receipts are required')
    for name in result_paths:
        safe_parts(name)
        require(name in records, f'Campaign receipt not in manifest: {name}')
    snapshots = manifest['script_snapshots']
    require(isinstance(snapshots, dict) and set(snapshots) == set(SCRIPT_HASHES)
            and len(set(snapshots.values())) == len(SCRIPT_HASHES), 'Script snapshot inventory differs')
    for name, relative in snapshots.items():
        safe_parts(relative)
        require(relative in records and records[relative]['sha256'] == SCRIPT_HASHES[name],
                f'Pinned script source bytes differ: {name}')
    if 'initial_screening_results' in manifest:
        historical = manifest['initial_screening_results']
        safe_parts(historical)
        require(historical in records and historical not in result_paths,
                'Historical screening receipt must be separately archived')
    return manifest, records


def mapped_path(root, manifest, recorded):
    absolute = canonical_absolute(recorded, 'recorded path')
    try:
        relative = absolute.relative_to(PurePosixPath(manifest['original_repo'])).as_posix()
    except ValueError as error:
        raise AuditError(f'Recorded path leaves original repository: {recorded}') from error
    return root.joinpath(*safe_parts(relative))


def archived_file(root, records, path):
    name = path.relative_to(root).as_posix()
    require(name in records and path.is_file(), f'Required evidence file not archived: {name}')
    return path


def expected_flags(mode, ordering):
    if mode == 'direct':
        return ['-ksp_type', 'preonly', '-pc_type', 'lu', '-pc_factor_mat_solver_type', 'mumps']
    flags = ['-ksp_pc_side', 'right', '-ksp_norm_type', 'unpreconditioned',
             '-ksp_rtol', '5e-11', '-ksp_atol', '5e-24', '-ksp_max_it', '3000',
             '-ksp_gmres_restart', '100', '-ksp_gmres_modifiedgramschmidt',
             '-pc_plan_schur_approx', 'nodal',
             '-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type', 'lower']
    if mode in ('added_mass', 'added_mass_fluid_onecycle'):
        fluid = '-fieldsplit_dynamics_fieldsplit_fluid_'
        structure = '-fieldsplit_dynamics_fieldsplit_structure_'
        return flags + ['-pc_recipe', 'added_mass', '-pc_plan_structure_approx', 'a11',
                        fluid + 'ksp_type', 'preonly' if mode.endswith('onecycle') else 'fgmres',
                        fluid + 'ksp_rtol', '1e-4', fluid + 'ksp_max_it', '20',
                        structure + 'ksp_type', 'fgmres', structure + 'ksp_rtol', '1e-2',
                        structure + 'ksp_max_it', '20']
    prefix = '-fieldsplit_dynamics_fieldsplit_velocity_'
    twolevel = mode.startswith('twolevel_')
    flags += ['-pc_recipe', 'hybrid', '-pc_plan_velocity_solver', 'twolevel' if twolevel else 'coupled',
              prefix + ('mg_levels_' if twolevel else '') + 'sub_pc_factor_mat_ordering_type', ordering]
    if twolevel:
        flags += [prefix + 'ksp_type', 'preonly' if mode.endswith('onecycle') else 'fgmres',
                  prefix + 'ksp_rtol', '1e-4', prefix + 'ksp_max_it', '20',
                  prefix + 'pc_mg_multiplicative_cycles', '1', prefix + 'pc_mg_cycle_type', 'v']
    return flags


def expected_solvers(mode):
    if mode == 'direct':
        return {'-': ('preonly', 'lu')}
    result = {'-': ('fgmres', 'fieldsplit')}
    if mode in ('added_mass', 'added_mass_fluid_onecycle'):
        result['fieldsplit_dynamics_fieldsplit_fluid_'] = (
            'preonly' if mode.endswith('onecycle') else 'fgmres', 'fieldsplit')
        result['fieldsplit_dynamics_fieldsplit_structure_'] = ('fgmres', 'gamg')
    elif mode.startswith('twolevel_'):
        result['fieldsplit_dynamics_fieldsplit_velocity_'] = (
            'preonly' if mode.endswith('onecycle') else 'fgmres', 'mg')
    else:
        result['fieldsplit_dynamics_fieldsplit_velocity_'] = ('gmres', 'asm')
    return result


def pairs(line):
    items = re.findall(r'(\w+)=([^\s]+)', line)
    require(len(items) == len(dict(items)), f'Duplicate log key: {line}')
    return dict(items)


def audit_log(path, run, ranks, dofs):
    text = path.read_text(encoding='utf-8')
    require(text.splitlines().count('status=success') == 1, f'{path}: missing or repeated success marker')
    require(sha256(path) == run['log_sha256'], f'{path}: receipt log hash differs')
    steps = integer(run['steps_requested'], str(path), 1)
    expected = expected_solvers(run['mode'])
    current_targets = {prefix: [0] * ranks for prefix in expected}
    target_observations, omitted = 0, 0
    history, counts, current, reports, nodes = [], {}, [], [], {}
    accepted, nonlinear_fields, pending_report = 0, set(), None
    for line in text.splitlines():
        where = f'{path.parent.name}, step {accepted + 1}'
        if line.startswith(('linear_residual_unavailable', 'linear_iteration_limit_residual ',
                            'step_retry=', 'error=', 'EONSim rank ')):
            raise AuditError(f'{path}: forbidden failure/retry marker: {line}')
        if line.startswith('linear_residual '):
            row = pairs(line)
            require(pending_report is None and not nonlinear_fields,
                    f'{where}: correction after its nonlinear/report record')
            require(not current or set(current[-1]['fields']) == EQUATIONS,
                    f'{where}: incomplete prior correction fields')
            require(integer(row['solve'], where, 1) == len(current) + 1, f'{where}: correction numbering')
            norm, rhs = number(row['norm'], where), number(row['rhs_norm'], where)
            ratio = norm / max(1e-23, 1e-10 * rhs)
            require(ratio <= MARGIN, f'{where}: true residual target exceeded ({ratio})')
            current.append(dict(step=accepted + 1, norm=norm, rhs=rhs, ratio=ratio, fields={}))
        elif line.startswith('linear_field_residual '):
            row = pairs(line)
            require(pending_report is None and current
                    and integer(row['solve'], where, 1) == len(current), f'{where}: orphan field norm')
            name = row['name']
            require(name in EQUATIONS and name not in current[-1]['fields'], f'{where}: duplicate/unknown field')
            require(number(row['constraint_max'], where) == 0.
                    and number(row['residual_scale'], where) == 1.
                    and number(row['constraint_scale'], where) == 1., f'{where}: scaled/constrained field norm')
            current[-1]['fields'][name] = number(row['rms'], where)
        elif line.startswith('field_residual '):
            row = pairs(line)
            name, count = row['name'], integer(row['equation_rows'], where, 1)
            require(pending_report is None and current and name in EQUATIONS
                    and name not in nonlinear_fields, f'{where}: nonlinear field record')
            require(integer(row['constraint_rows'], where) == 0 and counts.setdefault(name, count) == count,
                    f'{where}: inconsistent equation rows')
            require(integer(row['accepted'], where) == 1
                    and number(row['residual_scale'], where) == number(row['constraint_scale'], where) == 1.
                    and number(row['rms'], where) <= number(row['limit'], where)
                    and number(row['constraint_max'], where) <= number(row['constraint_limit'], where),
                    f'{where}: nonlinear field acceptance failed')
            nonlinear_fields.add(name)
        elif line.startswith('solver_report '):
            row = pairs(line)
            require(pending_report is None and integer(row['ranks'], where, 1) == ranks
                    and integer(row['dofs'], where, 1) == dofs, f'{where}: invalid solver report')
            require((row['ksp'], row['pc']) == expected['-'], f'{where}: outer solver type differs')
            integer(row['snes_reason'], where, 1)
            integer(row['ksp_reason'], where, 1)
            require(integer(row['domain_rejections'], where) == 0, f'{where}: domain rejection')
            require(integer(row['linear_started'], where) == integer(row['linear_completed'], where)
                    == len(current) and current, f'{where}: incomplete linear solve counts')
            integer(row['linear_iterations'], where)
            for name in TIMERS:
                number(row[name], f'{where}: {name}')
            pending_report = row
        elif line.startswith('solver_node '):
            row = pairs(line)
            require(pending_report is not None, f'{where}: solver snapshot outside report interval')
            rank = integer(row['rank'], where)
            require(rank < ranks, f'{where}: invalid solver-node rank')
            iterations = integer(row['last_iterations'], where)
            number(row['reported_norm'], where)
            prefix = row['prefix']
            if prefix in expected:
                require((row['ksp'], row['pc']) == expected[prefix],
                        f'{where}: requested solver type differs for {prefix} rank {rank}')
                reason = int(row['ksp_reason'])
                require(str(reason) == row['ksp_reason'], f'{where}: malformed KSP reason')
                if prefix == '-':
                    require(row['path'] == 'root' and reason in CONVERGED_REASONS
                            and row['ksp_reason'] == pending_report['ksp_reason'],
                            f'{where}: root snapshot reason disagrees with successful report')
                else:
                    require(reason in CONVERGED_REASONS
                            or (reason == -3 and row['ksp'] in ('gmres', 'fgmres') and iterations > 0),
                            f'{where}: required response failed beyond its allowed iteration budget')
                require(integer(row['operator_set'], where) == 1
                        and integer(row['operator_rows'], where, 1)
                        == integer(row['operator_columns'], where, 1)
                        and integer(row['pc_reason'], where) == 0, f'{where}: requested PC/operator failed')
                current_targets[prefix][rank] += 1
                target_observations += 1
            key = (row['rank'], row['path'], prefix)
            if key not in nodes and len(nodes) == 256:
                omitted += 1
                continue
            record = nodes.setdefault(key, dict(rank=rank, path=row['path'], prefix=prefix,
                                               observations=0, max_last_iterations=0, reason_counts={}))
            record['observations'] += 1
            record['max_last_iterations'] = max(record['max_last_iterations'], iterations)
            reason = row['ksp_reason']
            record['reason_counts'][reason] = record['reason_counts'].get(reason, 0) + 1
            record['last'] = row
        elif line.startswith('fsi_step='):
            row = pairs(line)
            step = accepted + 1
            require(pending_report is not None and nonlinear_fields == EQUATIONS
                    and sum(counts.values()) == dofs, f'{where}: incomplete accepted step')
            require(integer(row['fsi_step'], where, 1) == step, f'{where}: accepted-step numbering')
            stage = (step - 1 + (1. if step == 1 else 2. / 3.)) / 32.
            pressure = 80. * stage ** 3 * (10. + stage * (-15. + 6. * stage))
            require(abs(number(row['time'], where) - step / 32.) < 1e-14
                    and abs(number(row['accepted_dt'], where) - 1. / 32.) < 1e-14
                    and abs(number(row['evaluation_time'], where) - stage) < 1e-14
                    and abs(number(row['applied_pressure'], where) - pressure) < 1e-11,
                    f'{where}: physical time or load history differs')
            for prefix, observations in current_targets.items():
                require(observations == [1] * ranks,
                        f'{where}: expected one {prefix} observation per rank, got {observations}')
            for correction in current:
                require(set(correction['fields']) == EQUATIONS, f'{where}: incomplete linear field norms')
                reconstructed = math.sqrt(math.fsum(counts[name] * rms * rms
                                                    for name, rms in correction['fields'].items()))
                close(reconstructed, correction['norm'], f'{where}: reconstructed norm')
            history.extend(current)
            reports.append(pending_report)
            accepted, current, nonlinear_fields, pending_report = step, [], set(), None
            current_targets = {prefix: [0] * ranks for prefix in expected}
        elif line == 'status=success':
            require(accepted == steps and not current and pending_report is None,
                    f'{where}: success marker before requested trajectory completed')
    require(accepted == steps and not current and not nonlinear_fields and pending_report is None,
            f'{path}: incomplete trajectory')
    require(len(history) == integer(run['corrections'], str(path), 1)
            == integer(run['within_target'], str(path), 1)
            and integer(run['steps'], str(path), 1) == steps, f'{path}: stored step/correction counts differ')
    require(len(run['correction_history']) == len(history), f'{path}: stored correction history length differs')
    for actual, stored in zip(history, run['correction_history']):
        require(stored['step'] == actual['step'] and set(stored['fields']) == EQUATIONS,
                f'{path}: stored correction provenance differs')
        for name in ('norm', 'rhs', 'ratio'):
            close(actual[name], stored[name], f'{path}: stored {name}')
        for name in EQUATIONS:
            close(actual['fields'][name], stored['fields'][name], f'{path}: stored {name} RMS')
    require(run['step_reports'] == reports, f'{path}: stored solver reports differ')
    stored_nodes = {}
    for row in run['solver_nodes']:
        key = (str(row['rank']), row['path'], row['prefix'])
        require(key not in stored_nodes, f'{path}: duplicate stored solver-node summary')
        stored_nodes[key] = row
    require(stored_nodes == nodes and run['omitted_node_observations'] == omitted
            and run['inner_iteration_semantics'] == 'last-call snapshots, not accumulated inner iterations',
            f'{path}: bounded snapshot summary differs')
    result = dict(steps=steps, corrections=len(history), worst_ratio=max(row['ratio'] for row in history),
                  outer_iterations=sum(integer(row['linear_iterations'], str(path)) for row in reports),
                  target_solver_observations=target_observations,
                  wall_seconds=number(run['wall_seconds'], f'{path}: external wall time'))
    close(result['worst_ratio'], run['worst_ratio'], f'{path}: worst target ratio')
    require(result['outer_iterations'] == run['outer_iterations'], f'{path}: outer iteration total differs')
    for name in TIMERS:
        result[name] = math.fsum(number(row[name], str(path)) for row in reports)
        close(result[name], run[name], f'{path}: {name} sum')
    return result


def owned_fields(root, records, directory, step, suffix, names, ranks, consumed_vtus):
    fields, owners = {name: {} for name in names}, {}
    for rank in range(ranks):
        path = directory / (f'tube_step{step}{suffix}' + (f'_rank{rank}' if ranks > 1 else '') + '.vtu')
        archived_file(root, records, path)
        consumed_vtus.add(path.relative_to(root).as_posix())
        pieces = ET.parse(path).findall('.//Piece')
        require(len(pieces) == 1, f'{path}: expected one VTU piece')
        count = integer(pieces[0].attrib['NumberOfPoints'], str(path), 1)
        arrays = {}
        for array in pieces[0].findall('./PointData/DataArray'):
            name = array.attrib['Name']
            require(name not in arrays and array.attrib.get('format') == 'ascii', f'{path}: duplicate/binary array')
            arrays[name] = array
        ids, owners_at_nodes = [], []
        for name, values in (('mesh_node_id', ids), ('owner', owners_at_nodes)):
            array = arrays[name]
            require(array.attrib['type'] in ('Int32', 'Int64')
                    and integer(array.attrib.get('NumberOfComponents', '1'), str(path), 1) == 1,
                    f'{path}: invalid {name} metadata')
            values.extend(integer(token, str(path)) for token in (array.text or '').split())
            require(len(values) == count, f'{path}: invalid {name} length')
        require(len(set(ids)) == count, f'{path}: duplicate node IDs')
        for node, owner in zip(ids, owners_at_nodes):
            require(owner < ranks and owners.setdefault(node, owner) == owner, f'{path}: inconsistent node owner')
        for name, components in names.items():
            array = arrays[name]
            require(array.attrib['type'] == 'Float64'
                    and integer(array.attrib.get('NumberOfComponents', '1'), str(path), 1) == components,
                    f'{path}: invalid {name} component count/type')
            values = [float(token) for token in (array.text or '').split()]
            require(len(values) == count * components and all(math.isfinite(value) for value in values),
                    f'{path}: truncated or nonfinite {name}')
            for index, (node, owner) in enumerate(zip(ids, owners_at_nodes)):
                if owner == rank:
                    require(node not in fields[name], f'{path}: duplicate owned {name} node')
                    fields[name][node] = values[index * components:(index + 1) * components]
    require(owners and all(set(values) == set(owners) for values in fields.values()),
            f'{directory}: missing owned nodes')
    return fields


def compare_fields(root, records, directory, reference, ranks, steps, consumed_vtus):
    peaks, differences = {}, {}
    for step in range(4, steps + 1, 4):
        for suffix, names in FIELDS:
            first = reference[(step, suffix)]
            actual = owned_fields(root, records, directory, step, suffix, names, ranks, consumed_vtus)
            for name in names:
                key = ('wall_' if suffix else 'fluid_') + name
                require(first[name].keys() == actual[name].keys(), f'{directory}: {key} owned node IDs differ')
                peak, difference = peaks.get(key, 0.), differences.get(key, 0.)
                for node, values in first[name].items():
                    other = actual[name][node]
                    require(len(values) == len(other), f'{directory}: {key} component count differs')
                    peak = max(peak, *(abs(value) for value in values))
                    difference = max(difference, *(abs(value - second) for value, second in zip(values, other)))
                peaks[key], differences[key] = peak, difference
    ratios = {}
    for name in peaks:
        require(peaks[name] > 0. or differences[name] == 0., f'{directory}: error against zero reference field')
        ratios[name] = differences[name] / peaks[name] if peaks[name] else 0.
        require(ratios[name] <= FIELD_LIMIT, f'{directory}: {name} relative peak exceeds {FIELD_LIMIT}')
    require(len(ratios) == 5, f'{directory}: incomplete field inventory')
    return ratios


def run_labels(stage):
    if stage == 'quick':
        return ['quick-' + mode for mode in MODES]
    labels = ['full-' + mode for mode in MODES] + ['warmup-' + mode for mode in MODES]
    for repeat in range(3):
        sequence = MODES[repeat:] + MODES[:repeat]
        labels.extend(f'timing-{repeat + 1}-{mode}' for mode in sequence)
    return labels


def audit_campaign(root, manifest, records, receipt_path, results, totals, consumed_vtus, launchers):
    stage = results['stage']
    require(stage in ('quick', 'full') and results['status'] == 'passed' and results['failures'] == [],
            f'{receipt_path}: incomplete or failed campaign receipt')
    require(results['source_commit'] == DRIVER_COMMIT and results['source_dirty'] is False
            and results['executable_sha256'] == EXECUTABLE_SHA256
            and results['input_sha256'] == FIXTURE_SHA256
            and results['script_hashes'] == SCRIPT_HASHES, f'{receipt_path}: source/input provenance differs')
    require(results['modes'] == list(MODES) and results['grids'] == list(GRIDS)
            and results['target'] == TARGET and results['tolerance_margin'] == MARGIN
            and results['field_relative_peak_limit'] == FIELD_LIMIT
            and results['environment'] == ENVIRONMENT
            and results['timing_semantics'] == TIMING_SEMANTICS, f'{receipt_path}: campaign contract differs')
    base = mapped_path(root, manifest, results['output_directory'])
    require(len(results['cases']) == len(GRIDS)
            and [case['grid'] for case in results['cases']] == [grid[0] for grid in GRIDS.values()],
            f'{receipt_path}: grid inventory/order differs')
    for alias, case in zip(GRIDS, results['cases']):
        grid, ranks, dofs, ordering = GRIDS[alias]
        require(case['ranks'] == ranks and case['dofs'] == dofs and case['ordering'] == ordering
                and case['prepare_status'] == 'passed', f'{grid}: grid/preparation contract differs')
        directory = base / grid
        original_directory = PurePosixPath(results['output_directory']) / grid
        require(case['input_hashes'] == INPUT_HASHES[grid], f'{grid}: pinned input member hashes differ')
        for name, expected_hash in INPUT_HASHES[grid].items():
            path = archived_file(root, records, directory / 'input' / name)
            require(sha256(path) == expected_hash, f'{grid}: input bytes differ for {name}')
        runs = case['runs']
        require([run['label'] for run in runs] == run_labels(stage), f'{grid}: run inventory/order differs')
        direct = directory / (stage + '-direct')
        reference = {(step, suffix): owned_fields(root, records, direct, step, suffix, names, ranks, consumed_vtus)
                     for step in range(4, (4 if stage == 'quick' else 32) + 1, 4)
                     for suffix, names in FIELDS}
        audited = {}
        for run in runs:
            mode, label = run['mode'], run['label']
            steps = 32 if label.startswith('full-') else 4
            require(mode in MODES and label.endswith('-' + mode) and run['steps_requested'] == steps
                    and run['status'] == 'passed' and type(run['exit_code']) is int
                    and run['exit_code'] == 0 and run['timeout'] is False,
                    f'{grid}/{label}: mode/status/step contract differs')
            require(number(run['execution_budget_seconds'], label) > 0., f'{label}: invalid execution budget')
            expected_directory = directory / label
            require(mapped_path(root, manifest, run['output_directory']) == expected_directory,
                    f'{grid}/{label}: output path does not match the unique run directory')
            flags = expected_flags(mode, ordering)
            require(run['flags'] == flags, f'{grid}/{label}: explicit solver controls differ')
            command = run['command']
            require(isinstance(command, list) and len(command) >= 18, f'{label}: missing launcher command')
            launcher, executable = command[0], command[7]
            canonical_absolute(launcher, 'MPI launcher')
            canonical_absolute(executable, 'executable')
            launchers.add((launcher, executable))
            expected_command = [launcher, '--map-by', 'core', '--bind-to', 'core', '-n', str(ranks),
                                executable, '-case', str(original_directory / 'input/case.json'),
                                '-partition', str(original_directory / 'partition'),
                                '-output', str(original_directory / label / 'tube.vtu'),
                                '-solver_report', '-linear_report', '-stop_after', str(steps), *flags]
            require(command == expected_command, f'{grid}/{label}: command or rank binding differs')
            require(case['prepare_command'] == [executable, '-case', str(original_directory / 'input/case.json'),
                                               '-prepare', str(original_directory / 'partition'),
                                               '-parts', str(ranks)], f'{grid}: prepare command differs')
            path = archived_file(root, records, expected_directory / 'solve.log')
            audited[label] = audit_log(path, run, ranks, dofs)
            ratios = compare_fields(root, records, expected_directory, reference, ranks, steps, consumed_vtus)
            require(set(run['field_relative_peaks']) == set(ratios), f'{grid}/{label}: stored field inventory differs')
            for name, value in ratios.items():
                close(value, run['field_relative_peaks'][name], f'{grid}/{label}: stored {name} relative peak')
                totals['max_field_relative_peak'] = max(totals['max_field_relative_peak'], value)
            actual = audited[label]
            totals['runs'] += 1
            totals[stage + '_runs'] += 1
            totals['accepted_steps'] += steps
            totals['linear_corrections'] += actual['corrections']
            totals['target_solver_observations'] += actual['target_solver_observations']
            totals['max_linear_target_ratio'] = max(totals['max_linear_target_ratio'], actual['worst_ratio'])
            totals['saved_states'] += steps // 4
            totals['field_comparisons'] += steps // 4 * 5
            if steps == 32:
                totals['full_trajectories'] += 1
                totals['full_trajectory_corrections'] += actual['corrections']
        if stage == 'full':
            require(set(case['medians']) == set(MODES), f'{grid}: median mode inventory differs')
            medians = {}
            for mode in MODES:
                stored = case['medians'][mode]
                keys = ('wall_seconds', 'outer_iterations', *TIMERS)
                require(set(stored) == {'samples', *keys} and stored['samples'] == 3,
                        f'{grid}/{mode}: median schema/sample count differs')
                medians[mode] = {'samples': 3}
                for name in keys:
                    value = statistics.median(audited[f'timing-{repeat}-{mode}'][name] for repeat in range(1, 4))
                    close(value, stored[name], f'{grid}/{mode}: median {name}')
                    medians[mode][name] = value
            totals['medians'][grid] = medians


def replay(root, manifest, records, archive_hash):
    campaigns = {}
    for relative in manifest['campaign_results']:
        path = archived_file(root, records, root.joinpath(*safe_parts(relative)))
        results = read_json(path)
        stage = results['stage']
        require(stage in ('quick', 'full') and stage not in campaigns, 'Campaign stages duplicate or differ')
        campaigns[stage] = path, results
    require(set(campaigns) == {'quick', 'full'}, 'Both quick and full receipts are required')
    quick_path, quick = campaigns['quick']
    full_path, full = campaigns['full']
    require(mapped_path(root, manifest, full['quick_evidence']['path']) == quick_path
            and full['quick_evidence']['sha256'] == sha256(quick_path), 'Full receipt is not bound to archived quick bytes')
    for name in ('source_commit', 'source_dirty', 'executable_sha256', 'input_sha256',
                 'script_hashes', 'target', 'tolerance_margin', 'field_relative_peak_limit'):
        require(quick[name] == full[name], f'Quick/full provenance differs: {name}')
    require(quick['output_directory'] != full['output_directory'], 'Quick/full reused output directory')
    totals = dict(status='passed', archive_sha256=archive_hash, manifest_files=len(records),
                  manifest_bytes=sum(row['bytes'] for row in records.values()),
                  build_source_commit=BUILD_COMMIT, driver_commit=DRIVER_COMMIT,
                  executable_sha256=EXECUTABLE_SHA256, script_hashes=SCRIPT_HASHES,
                  runs=0, quick_runs=0, full_runs=0, accepted_steps=0, linear_corrections=0,
                  full_trajectories=0, full_trajectory_corrections=0, saved_states=0,
                  field_comparisons=0, target_solver_observations=0, volume_vtus=0,
                  max_linear_target_ratio=0., max_field_relative_peak=0., medians={},
                  wall_time_audit='finite recorded values and recomputed sample medians only',
                  inner_iteration_semantics='last-call snapshots, not accumulated inner iterations',
                  initial_screening_numerically_replayed=False,
                  initial_screening_hash_verified='initial_screening_results' in manifest)
    consumed_vtus, launchers = set(), set()
    audit_campaign(root, manifest, records, quick_path, quick, totals, consumed_vtus, launchers)
    audit_campaign(root, manifest, records, full_path, full, totals, consumed_vtus, launchers)
    totals['volume_vtus'] = len(consumed_vtus)
    require(len(launchers) == 1, 'Quick/full MPI launcher or executable path differs')
    require((totals['runs'], totals['quick_runs'], totals['full_runs'], totals['full_trajectories'],
             totals['accepted_steps'], totals['saved_states'], totals['field_comparisons'], totals['volume_vtus'])
            == (72, 12, 60, 12, 624, 156, 780, 468), 'Selected campaign inventory totals differ')
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--sha256', required=True, help='Published SHA256 of the complete archive')
    parser.add_argument('--work', required=True, type=Path, help='New directory; existing paths are rejected')
    args = parser.parse_args()
    work = args.work.resolve()
    if work.exists():
        parser.error('--work must not already exist; use a fresh directory')
    work.mkdir(parents=True)
    try:
        root = work / 'unpacked'
        manifest, records = unpack_and_verify(args.archive.resolve(), args.sha256, root)
        result = replay(root, manifest, records, args.sha256)
    except (AuditError, OSError, ValueError, KeyError, TypeError, OverflowError,
            UnicodeError, tarfile.TarError, ET.ParseError) as error:
        result = dict(status='failed', error=str(error))
    output = json.dumps(result, sort_keys=True, allow_nan=False)
    (work / 'replay.json').write_text(output + '\n', encoding='utf-8')
    print(output)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
