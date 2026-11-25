"""Audit EONSim, svFSI and the independent at-rest DAE with four choices of dependent Tet4 vertex."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys

from axisymmetric import TubeParameters
from compare_metric import compare

SMOOTH = Path(__file__).resolve().parents[1] / 'fsi-smooth-load-2026-11-24'
sys.path.insert(0, str(SMOOTH))
from audit_reflection import measured_ring_strains
from audit_vertex_order import audit, state_change
from compare_space_series import pack as paired_runs


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_hashes(folder, entries):
    for name, expected in entries.items():
        if digest(folder / name) != expected:
            raise ValueError('Input or solved field changed: ' + str(folder / name))


def element_runs(root, ref, fsi):
    from study_rigid_tube import read_mesh
    base = root / 'regular-tet-eon'
    runs = []
    states = {}
    meshes = {}
    for path in sorted(base.glob('*/result.json')):
        key = re.fullmatch(r'v([0-3])-n(\d+)-(adaptive|\d+)-p(.+)', path.parent.name)
        if key is None:
            raise ValueError('Unexpected metric comparison name')
        vertex, n, source, pressure = key.groups()
        vertex, n, pressure = int(vertex), int(n), float(pressure)
        coeff = n if source == 'adaptive' else int(source)
        d = json.loads(path.read_text())
        if ((d['pressure_pa'], d['steps'], d['coefficient_steps'], d['fixed']) !=
                (pressure, n, coeff, source != 'adaptive') or d['model'] != 'regular_tet'):
            raise ValueError('Coefficient, time step, load or model differs')
        directory = path.parent
        require_hashes(directory, {**{k: d['mesh_sha256'][k] for k in ('solid.msh', 'fluid.msh')},
                                   'case.json': d['case_sha256'], 'case.log': d['log_sha256'],
                                   'tube_pressure_faces.csv': d['pressure_history_sha256']})
        linear = ref[f'regular-simplex-v{vertex}']
        if linear['sha256'] != d['dae_sha256'] or d['executable_sha256'] != digest(root / 'regular-tet-eonsim'):
            raise ValueError('Binary or independent DAE input differs')
        if len(d['samples']) != 2 or [s['time'] for s in d['samples']] != [.5, 1.]:
            raise ValueError('Incomplete nonlinear history')
        if d['max_load_error'] > pressure * 1e-12:
            raise ValueError('Different applied end tractions')
        mesh = [read_mesh(directory / s) for s in ('fluid.msh', 'solid.msh')]
        xs = d['sections']
        for s in d['samples']:
            step = round(n * s['time'])
            fields = [fsi.recovered_state(directory, f'tube_step{step}' + suffix, region, bool(i), 1)
                      for i, (region, suffix) in enumerate(zip(mesh, ('', '_solid')))]
            for suffix, sha in s['files_sha256'].items():
                require_hashes(directory, {f'tube_step{step}{suffix}.vtu': sha})
            states[vertex, n, coeff, pressure, s['time']] = fields
            measured_x, actual = measured_ring_strains(mesh[1],fields[1])
            if xs != measured_x or max(abs(a - b) for a, b in zip(actual, s['measured_strains'])) > 3e-15:
                raise ValueError('Observed EONSim strains disagree with raw displacements')
        meshes[vertex] = mesh
        runs.append(dict(case=directory.name, vertex=vertex, report=d))
    differences = []
    for (v, n, source, p, t), fields in sorted(states.items()):
        if v == 3 or (3, n, source, p, t) not in states:
            continue
        reference = states[3, n, source, p, t]
        for grid, original in zip(meshes[v], meshes[3]):
            if (grid[0] != original[0] or grid[2] != original[2] or
                    len(grid[1]) != len(original[1]) or any(set(a) != set(b) for a, b in zip(grid[1], original[1]))):
                raise ValueError('Meshes differ in more than local tetrahedral ordering')
        changes = state_change(reference, fields, meshes[3])
        differences.append(dict(vertex=v, steps=n, coefficient_steps=source, pressure_pa=p, time=t, **changes))
    return runs, differences


def pack(root, native, helpers, fsi):
    comparisons = []
    for group in ('vertex-order', 'regular-metric'):
        for path in sorted((root / group).glob('*/results.json')):
            n, dep, mode = path.parent.name.split('-')
            v = int(dep[1:])
            if v == 3:
                continue
            base = root / ('current-time' if group == 'vertex-order' else group)
            base /= n + '-' + (mode if group == 'vertex-order' else 'v3-' + mode)
            comparisons.append(dict(group=group, **audit(base, path.parent, v, helpers, fsi)))
    refs = {p.stem: dict(sha256=digest(p), dae=json.loads(p.read_text())) for p in sorted((root / 'metric-bases').glob('*.json'))}
    refs['native-v3'] = dict(sha256=digest(native), dae=json.loads(lzma.decompress(native.read_bytes())))
    pairs = [s for s in paired_runs(root) if s['group'] in ('regular-metric', 'vertex-order', 'current-time')]
    eon, differences = element_runs(root, refs, fsi)
    return dict(vertex_comparisons=comparisons, operators=refs, pairs=pairs,
                eon_regular=eon, eon_vertex_field_changes=differences)


def tables(data):
    sv_vs_linear = []
    for name, reference in sorted(data['operators'].items()):
        rows, _ = compare(reference['dae'], data['pairs'])
        sv_vs_linear.extend(dict(operator=name, **row) for row in rows)
    matches = []
    for run in data['eon_regular']:
        d = run['report']
        n, peak, v = d['steps'], d['pressure_pa'], run['vertex']
        sv = [p['report'] for p in data['pairs'] if p['group'] == 'regular-metric' and p['case'] == f'n{n}-v{v}-regular'
              and p['peak_pressure'] == peak and not d['fixed']]
        if len(sv) > 1:
            raise ValueError('Ambiguous native same-coefficient measurement')
        static = TubeParameters().lame_area_strain(peak)
        for i, s in enumerate(d['samples']):
            actual = s['measured_strains']
            reference = data['operators'][f'regular-simplex-v{v}']['dae']
            studies = next(a['time_study'] for a in reference['runs'] if a['source_steps'] == d['coefficient_steps'] and a['mode'] == 'native')
            fine = max(studies, key=lambda k: k['steps'])['samples'][i]
            predicted = [a * peak / reference['pressure'] for a in fine['section_area_strain']]
            if (len(actual) != len(predicted) or s['time'] != fine['time'] or
                    max(abs(a - b) for a, b in zip(predicted, s['linear_strains'])) > 2e-14):
                raise ValueError('Independent DAE, pressure or stations differ')
            error = 100 * max(abs(a - b) for a, b in zip(actual, predicted)) / static
            if not math.isclose(error, s['max_abs_difference_pct_static'], rel_tol=1e-8, abs_tol=1e-12):
                raise ValueError('Unreproducible discrete error')
            other = []
            if sv:
                b = sv[0]
                if (b['axial_sections'] != d['sections'] or b['mesh_sha256'] !=
                    [d['mesh_sha256'][k] for k in ('fluid.msh', 'solid.msh')] or b['results'][i]['time'] != s['time']):
                    raise ValueError('Native and EONSim mesh or physical time differs')
                other = b['results'][i]['svfsi']['strains']
            matches.append(dict(case=run['case'], vertex=v, steps=n, coefficient_steps=d['coefficient_steps'],
                                fixed=d['fixed'], pressure_pa=peak, time=s['time'], eon_end_pct_area=100 * actual[0],
                                dae_end_pct_area=100 * predicted[0], sv_end_pct_area=100 * other[0] if other else None,
                                eon_dae_max_pct_static=error, radau_refinement_pct_static=s['radau_change_pct_static'],
                                eon_sv_max_pct_static=100 * max(abs(a-b) for a,b in zip(actual,other)) / static if other else None))
    return sv_vs_linear, matches


def main():
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument('--runs', type=Path)
    src.add_argument('--archive', type=Path)
    for name in ('native-dae', 'reference-scripts', 'write-archive'):
        p.add_argument('--' + name, type=Path)
    for name in ('sv-csv', 'eon-csv'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    if args.runs:
        if not args.native_dae or not args.reference_scripts:
            p.error('Reading raw data requires the pinned native DAE and reference scripts')
        sys.path.append(str(args.reference_scripts.resolve()))
        import compare_svfsi_wall as wall
        import study_hydrostatic_fsi as fsi
        data = pack(args.runs, args.native_dae, wall, fsi)
    else:
        data = json.loads(lzma.decompress(args.archive.read_bytes()))
    for path, rows in zip((args.sv_csv, args.eon_csv), tables(data)):
        if not rows:
            raise ValueError('No comparable measurements')
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    if args.write_archive:
        args.write_archive.write_bytes(lzma.compress(json.dumps(data, separators=(',', ':'), allow_nan=False).encode()))
    print(len(data['eon_regular']), 'measured EONSim trajectories,', len(data['vertex_comparisons']), 'paired permutations')


if __name__ == '__main__':
    main()
