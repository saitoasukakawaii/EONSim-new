#!/usr/bin/env python3
"""Re-audit this stored FSI campaign using only Python's standard library.

No solver, build, MPI process, or archived Python code is executed. The pinned
archive is unpacked as regular files into a temporary directory and removed on
exit. Run: python3 replay.py [--archive evidence.tar.xz] [--output replay.json]
"""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET


ARCHIVE_SHA256 = '03990426bfc193038353da504f38119cd006cf8ea7fd95743cb1ccb66f4bccdf'
FINAL_COMMIT = 'b52281d7585ead08e545f29f8d83eca9177e7eac'
MANIFEST = 'build/evidence-staging/manifest.jsonl'
EXTRAS = {MANIFEST, 'build/evidence-staging/archive-plan.json',
          'build/evidence-staging/stage_manifest.py'}
FINAL = Path('build/cloud-3.23.7-release')
ARTERIAL = FINAL / 'fsi_tube/arterial-block'
MODES = ('direct', 'physics_lower', 'coupled_diagonal', 'coupled_nodal',
         'twolevel_nodal', 'added_mass')
GRIDS = {'s24-r3-w2-a6': (1, 1027), 's48-r4-w4-a6': (2, 3024)}
TESTS = {'fsi_tube', 'fsi_tube_rcr', 'pc_recipe_retry', 'pc_added_mass_retry',
         'pc_twolevel_retry', 'pc_recipe_hybrid', 'schur_verification', 'time_retry_verification'}
EQUATIONS = {'mesh', 'pressure', 'structure', 'velocity'}
FIELDS = (('', {'velocity': 3, 'pressure': 1, 'mesh_displacement': 3}),
          ('_solid', {'velocity': 3, 'displacement': 3}))


class AuditError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def number(value, where):
    result = float(value)
    require(math.isfinite(result) and result >= 0., f'{where}: nonfinite or negative value {value}')
    return result


def integer(value, where, minimum=0):
    result = int(value)
    require(str(result) == str(value) and result >= minimum, f'{where}: invalid integer {value}')
    return result


def close(actual, stored, where, tolerance=2e-12):
    stored = number(stored, where)
    require(math.isclose(actual, stored, rel_tol=tolerance, abs_tol=1e-300),
            f'{where}: recomputed {actual} differs from stored {stored}')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def reject_constant(value):
    raise AuditError(f'Invalid JSON numeric constant: {value}')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant)


def safe_parts(name):
    parts = name.split('/')
    require(name and not PurePosixPath(name).is_absolute()
            and not any(part in ('', '.', '..') for part in parts)
            and not any(char in name for char in ('\\', ':', '\0')),
            f'Unsafe archive path: {name!r}')
    return parts


def unpack_and_verify(archive, destination):
    require(sha256(archive) == ARCHIVE_SHA256, 'Archive SHA256 does not match the published evidence')
    names, unpacked_bytes = set(), 0
    with tarfile.open(archive, 'r:xz') as bundle:
        for member in bundle:
            parts = safe_parts(member.name)
            require(member.isreg() and not member.sparse, f'Nonregular archive member: {member.name}')
            require(member.name not in names, f'Duplicate archive member: {member.name}')
            names.add(member.name)
            unpacked_bytes += member.size
            require(len(names) <= 4096 and 0 <= member.size <= 64 * 1024 * 1024
                    and unpacked_bytes <= 256 * 1024 * 1024, 'Archive exceeds bounded replay limits')
            path = destination.joinpath(*parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            require(path.stat().st_size == member.size, f'Incomplete extracted file: {member.name}')
    records = {}
    for line in (destination / MANIFEST).read_text(encoding='utf-8').splitlines():
        row = json.loads(line, parse_constant=reject_constant)
        name = row['path']
        safe_parts(name)
        require(name not in records and name in names, f'Duplicate or missing manifest file: {name}')
        require(row.get('pending_final_batch') is False and row.get('hash_state') == 'hashed',
                f'Unfinished manifest record: {name}')
        require(isinstance(row['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', row['sha256']),
                f'Invalid manifest hash: {name}')
        path = destination.joinpath(*safe_parts(name))
        require(path.stat().st_size == integer(row['bytes'], name), f'Manifest size mismatch: {name}')
        require(sha256(path) == row['sha256'], f'Manifest SHA256 mismatch: {name}')
        records[name] = row
    require(len(records) == 2557 and not (set(records) & EXTRAS) and names == set(records) | EXTRAS,
            'Archive must contain exactly 2,557 manifest files and the three declared metadata files')
    return records


def audit_receipt(root):
    receipt = read_json(root / FINAL / 'evidence/summary.json')
    require(receipt['commit'] == FINAL_COMMIT and receipt['dirty'] is False
            and receipt['status'] == 'passed', 'Final receipt is not the clean, passed b52281d campaign')
    tests = receipt['tests']
    require(len(tests) == 8 and {row['name'] for row in tests} == TESTS
            and set(receipt['selected_tests']) == TESTS, 'Final receipt test selection differs')
    require(all(row['status'] == 'passed' and row['exit_code'] == 0 and row['timeout'] is False
                for row in tests), 'Final receipt contains a failed or incomplete test')


def pairs(line):
    items = re.findall(r'(\w+)=([^\s]+)', line)
    require(len(items) == len(dict(items)), f'Duplicate log key: {line}')
    return dict(items)


def audit_log(path, run, ranks, dofs):
    text = path.read_text(encoding='utf-8')
    require(text.splitlines().count('status=success') == 1, f'{path}: missing or repeated success marker')
    require(sha256(path) == run['log_sha256'], f'{path}: run log hash differs')
    steps = integer(run['steps_requested'], str(path), 1)
    history, counts, current, reports = [], {}, [], []
    accepted, nonlinear_fields, pending_report = 0, set(), None
    for line in text.splitlines():
        where = f'{path.name}, step {accepted + 1}'
        if line.startswith(('linear_residual_unavailable', 'linear_iteration_limit_residual ',
                            'step_retry=', 'error=', 'EONSim rank 0:')):
            raise AuditError(f'{path}: forbidden failure/retry marker: {line}')
        if line.startswith('linear_residual '):
            row = pairs(line)
            require(pending_report is None, f'{where}: correction after its solver report')
            require(integer(row['solve'], where, 1) == len(current) + 1, f'{where}: correction numbering')
            norm, rhs = number(row['norm'], where), number(row['rhs_norm'], where)
            ratio = norm / max(1e-23, 1e-10 * rhs)
            require(ratio <= 1.00001, f'{where}: true residual target exceeded ({ratio})')
            current.append(dict(step=accepted + 1, norm=norm, rhs=rhs, ratio=ratio, fields={}))
        elif line.startswith('linear_field_residual '):
            row = pairs(line)
            require(current and integer(row['solve'], where, 1) == len(current), f'{where}: orphan field norm')
            name = row['name']
            require(name in EQUATIONS and name not in current[-1]['fields'], f'{where}: duplicate/unknown field')
            require(number(row['constraint_max'], where) == 0.
                    and number(row['residual_scale'], where) == 1., f'{where}: scaled/constrained field norm')
            current[-1]['fields'][name] = number(row['rms'], where)
        elif line.startswith('field_residual '):
            row = pairs(line)
            name, count = row['name'], integer(row['equation_rows'], where, 1)
            require(name in EQUATIONS and name not in nonlinear_fields, f'{where}: nonlinear field count')
            require(integer(row['constraint_rows'], where) == 0 and counts.setdefault(name, count) == count,
                    f'{where}: inconsistent equation rows')
            require(integer(row['accepted'], where) == 1
                    and number(row['rms'], where) <= number(row['limit'], where)
                    and number(row['constraint_max'], where) <= number(row['constraint_limit'], where),
                    f'{where}: nonlinear field acceptance failed')
            nonlinear_fields.add(name)
        elif line.startswith('solver_report '):
            row = pairs(line)
            require(pending_report is None and integer(row['ranks'], where, 1) == ranks
                    and integer(row['dofs'], where, 1) == dofs, f'{where}: invalid solver report')
            integer(row['snes_reason'], where, 1)
            integer(row['ksp_reason'], where, 1)
            require(integer(row['domain_rejections'], where) == 0, f'{where}: domain rejection')
            require(integer(row['linear_started'], where) == integer(row['linear_completed'], where)
                    == len(current) and current, f'{where}: incomplete linear solve counts')
            pending_report = row
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
            for correction in current:
                require(set(correction['fields']) == EQUATIONS, f'{where}: incomplete linear field norms')
                reconstructed = math.sqrt(math.fsum(counts[name] * rms * rms
                                                    for name, rms in correction['fields'].items()))
                close(reconstructed, correction['norm'], f'{where}: reconstructed norm')
            history.extend(current)
            reports.append(pending_report)
            accepted, current, nonlinear_fields, pending_report = step, [], set(), None
    require(accepted == steps and not current and not nonlinear_fields and pending_report is None,
            f'{path}: incomplete trajectory')
    require(len(history) == integer(run['corrections'], str(path), 1)
            == integer(run['within_target'], str(path), 1)
            and integer(run['steps'], str(path), 1) == steps, f'{path}: stored step/correction counts differ')
    require(len(run['correction_history']) == len(history), f'{path}: stored correction history length differs')
    for actual, stored in zip(history, run['correction_history']):
        require(stored['step'] == actual['step'] and set(stored['fields']) == EQUATIONS,
                f'{path}: stored correction provenance differs')
        for key in ('norm', 'rhs', 'ratio'):
            close(actual[key], stored[key], f'{path}: stored {key}')
        for name in EQUATIONS:
            close(actual['fields'][name], stored['fields'][name], f'{path}: stored {name} RMS')
    worst = max(row['ratio'] for row in history)
    close(worst, run['worst_ratio'], f'{path}: worst target ratio')
    require(sum(integer(row['linear_iterations'], str(path)) for row in reports) == run['outer_iterations'],
            f'{path}: outer iteration total differs')
    close(math.fsum(number(row['linear_seconds'], str(path)) for row in reports), run['linear_seconds'],
          f'{path}: linear time sum')
    return steps, len(history), worst


def owned_fields(directory, step, suffix, names, ranks):
    fields, owners = {name: {} for name in names}, {}
    for rank in range(ranks):
        path = directory / (f'tube_step{step}{suffix}' + (f'_rank{rank}' if ranks > 1 else '') + '.vtu')
        pieces = ET.parse(path).findall('.//Piece')
        require(len(pieces) == 1, f'{path}: expected one VTU piece')
        count = integer(pieces[0].attrib['NumberOfPoints'], str(path), 1)
        arrays = {}
        for array in pieces[0].findall('./PointData/DataArray'):
            name = array.attrib['Name']
            require(name not in arrays and array.attrib.get('format') == 'ascii', f'{path}: duplicate/binary array')
            arrays[name] = array
        ids, ranks_at_nodes = [], []
        for name, values in (('mesh_node_id', ids), ('owner', ranks_at_nodes)):
            array = arrays[name]
            require(array.attrib['type'] in ('Int32', 'Int64')
                    and integer(array.attrib.get('NumberOfComponents', '1'), str(path), 1) == 1,
                    f'{path}: invalid {name} metadata')
            values.extend(integer(token, str(path)) for token in (array.text or '').split())
            require(len(values) == count, f'{path}: invalid {name} length')
        require(len(set(ids)) == count, f'{path}: duplicate node IDs')
        for node, owner in zip(ids, ranks_at_nodes):
            require(owner < ranks and owners.setdefault(node, owner) == owner, f'{path}: inconsistent node owner')
        for name, components in names.items():
            array = arrays[name]
            require(array.attrib['type'] == 'Float64'
                    and integer(array.attrib.get('NumberOfComponents', '1'), str(path), 1) == components,
                    f'{path}: invalid {name} component count/type')
            values = [float(token) for token in (array.text or '').split()]
            require(len(values) == count * components and all(math.isfinite(value) for value in values),
                    f'{path}: truncated or nonfinite {name}')
            for index, (node, owner) in enumerate(zip(ids, ranks_at_nodes)):
                if owner == rank:
                    require(node not in fields[name], f'{path}: duplicate owned {name} node')
                    fields[name][node] = values[index * components:(index + 1) * components]
    require(owners and all(set(values) == set(owners) for values in fields.values()),
            f'{directory}: missing owned nodes')
    return fields


def compare_trajectories(directory, reference, ranks):
    peaks, differences = {}, {}
    for step in range(4, 33, 4):
        for suffix, names in FIELDS:
            first = reference[(step, suffix)]
            actual = first if directory.name == 'full-direct' else owned_fields(directory, step, suffix, names, ranks)
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
        require(peaks[name] > 0. or differences[name] == 0., f'{directory}: nonzero difference in zero reference field')
        ratios[name] = differences[name] / peaks[name] if peaks[name] else 0.
        require(ratios[name] <= 2e-6, f'{directory}: {name} relative peak exceeds 2e-6')
    return ratios


def replay(root, manifest):
    audit_receipt(root)
    results = read_json(root / ARTERIAL / 'results.json')
    require(not results['failures'] and results['target'] == 'max(1e-23, 1e-10*rhs_norm)'
            and results['tolerance_margin'] == 1.00001 and results['field_relative_peak_limit'] == 2e-6,
            'Arterial acceptance contract or failure list differs')
    require(len(results['cases']) == 2 and {case['grid'] for case in results['cases']} == set(GRIDS),
            'Arterial grid inventory differs')
    totals = dict(status='passed', archive_sha256=ARCHIVE_SHA256, manifest_files=len(manifest),
                  manifest_bytes=sum(row['bytes'] for row in manifest.values()), validation_commit=FINAL_COMMIT,
                  passed_tests=8, arterial_runs=0, accepted_steps=0, linear_corrections=0,
                  full_trajectories=0, saved_states=0, field_comparisons=0, volume_vtus=0,
                  max_linear_target_ratio=0., max_field_relative_peak=0.)
    for case in results['cases']:
        grid = case['grid']
        ranks, dofs = GRIDS[grid]
        require(case['ranks'] == ranks and case['dofs'] == dofs, f'{grid}: rank/DoF provenance differs')
        runs = case['runs']
        labels = {prefix + mode for prefix in ('full-', 'warmup-', 'timing-1-', 'timing-2-', 'timing-3-')
                  for mode in MODES}
        require(len(runs) == 30 and {run['label'] for run in runs} == labels, f'{grid}: run inventory differs')
        directory = root / ARTERIAL / grid
        for run in runs:
            label, mode = run['label'], run['mode']
            require(mode in MODES and label.endswith('-' + mode) and run['status'] == 'passed'
                    and run['exit_code'] == 0 and not run.get('timeout', False)
                    and run['steps_requested'] == (32 if label.startswith('full-') else 4),
                    f'{grid}/{label}: invalid run status/mode/step count')
            steps, corrections, worst = audit_log(directory / label / 'solve.log', run, ranks, dofs)
            totals['arterial_runs'] += 1
            totals['accepted_steps'] += steps
            totals['linear_corrections'] += corrections
            totals['max_linear_target_ratio'] = max(totals['max_linear_target_ratio'], worst)
        reference = {(step, suffix): owned_fields(directory / 'full-direct', step, suffix, names, ranks)
                     for step in range(4, 33, 4) for suffix, names in FIELDS}
        for mode in MODES:
            run = next(item for item in runs if item['label'] == 'full-' + mode)
            ratios = compare_trajectories(directory / run['label'], reference, ranks)
            stored = run.get('field_relative_peaks', {name: 0. for name in ratios} if mode == 'direct' else {})
            require(set(stored) == set(ratios), f'{grid}/{mode}: stored field inventory differs')
            for name, value in ratios.items():
                close(value, stored[name], f'{grid}/{mode}: stored {name} relative peak')
                totals['max_field_relative_peak'] = max(totals['max_field_relative_peak'], value)
            totals['full_trajectories'] += 1
            totals['saved_states'] += 8
            totals['field_comparisons'] += 8 * len(ratios)
            totals['volume_vtus'] += 8 * 2 * ranks
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path(__file__).with_name('evidence.tar.xz'))
    parser.add_argument('--output', type=Path, help='Also save the compact audit result as JSON')
    args = parser.parse_args()
    if args.output and (args.output.resolve() == args.archive.resolve()
                        or (args.output.exists() and args.archive.exists() and args.output.samefile(args.archive))):
        parser.error('--output must not overwrite the evidence archive')
    try:
        with tempfile.TemporaryDirectory(prefix='fsi-block-replay-') as temporary:
            root = Path(temporary)
            manifest = unpack_and_verify(args.archive, root)
            result = replay(root, manifest)
    except (AuditError, OSError, ValueError, KeyError, TypeError, OverflowError, tarfile.TarError, ET.ParseError) as error:
        result = dict(status='failed', error=str(error))
    output = json.dumps(result, sort_keys=True, allow_nan=False)
    print(output)
    if args.output:
        args.output.write_text(output + '\n', encoding='utf-8')
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
