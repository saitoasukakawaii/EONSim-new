"""Schur/GAMG versus direct solves and reference FSI tangent on 1/2/4 ranks."""
import argparse
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/fsi'))
from generate_domains import generate


def run(command):
    result = subprocess.run(list(map(str, command)), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=100)
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def fields(path, ranks):
    owned = {}
    for rank in range(ranks):
        file = path if ranks == 1 else path.with_name(f'{path.stem}_rank{rank}.vtu')
        root = ET.parse(file)
        arrays = {x.attrib['Name']: list(map(float, x.text.split()))
                  for x in root.findall('.//PointData/DataArray')}
        count = len(arrays['mesh_node_id'])
        for i, node in enumerate(arrays['mesh_node_id']):
            if int(arrays['owner'][i]) == rank:
                owned[int(node)] = [v for name, values in sorted(arrays.items())
                                    if name not in ('mesh_node_id', 'algebra_node_id', 'owner')
                                    for v in values[i*(len(values)//count):(i+1)*(len(values)//count)]]
    return owned


def compare(x, y):
    assert x.keys() == y.keys()
    assert all(len(x[node]) == len(y[node]) for node in x)
    assert all(math.isfinite(v) for state in (x, y) for values in state.values() for v in values)
    error = max(abs(v-w) for node in x for v, w in zip(x[node], y[node]))
    assert error < 2e-8, error
    return error


def physical_records(text):
    """Compare physical observations separately from solver iteration trajectories."""
    records = []
    for line in text.splitlines():
        if line.startswith('boundary_tag='):
            keys = ('boundary_tag', 'area', 'outward_flow', 'mean_pressure')
        elif line.startswith('fsi_step='):
            keys = ('fsi_step', 'time', 'position', 'velocity', 'fluid_force', 'body_balance')
        else:
            continue
        values = dict(re.findall(r'(\w+)=([^\s]+)', line))
        row = {key: float(values[key]) for key in keys}
        assert all(math.isfinite(v) for v in row.values()), row
        records.append(row)
    assert records, text
    return records


def compare_physics(reference, actual):
    assert len(reference) == len(actual), (reference, actual)
    for expected, result in zip(reference, actual):
        assert expected.keys() == result.keys()
        for key in expected:
            if key in ('boundary_tag', 'fsi_step'):
                assert expected[key] == result[key], (key, expected, result)
            else:
                assert abs(expected[key]-result[key]) < 2e-8, (key, expected, result)
    boundaries = [r for r in actual if 'outward_flow' in r]
    if boundaries:
        assert abs(sum(r['outward_flow'] for r in boundaries)) < 2e-8, boundaries
    for row in actual:
        if 'body_balance' in row:
            assert abs(row['body_balance']) < 2e-8, row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--recipe', choices=['physics', 'quantity', 'hybrid'])
    a = parser.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    results = []
    cases = [('flow', ROOT / 'cases/fluid/rotated_channel.yaml'),
             ('domains', generate(a.work / 'domains', 3)),
             ('rigid', ROOT / 'cases/fsi/rigid.yaml'),
             ('hyperelastic', ROOT / 'cases/fsi/hyperelastic.yaml')]
    # Same affine velocity patch with two distinct algebraic pressure conventions.
    mesh = ROOT / 'cases/fluid/rotated_channel.msh'
    first_node = int(mesh.read_text().split('$Nodes\n', 1)[1].splitlines()[1].split()[0])
    boundaries = [dict(tag=tag, type='velocity', value=[0, 0, 0], origin=[2, -1, .3],
                       gradient=[[-.064, .048, 0], [-.08533333333333333, .064, 0], [0, 0, 0]])
                  for tag in (11, 22, 33, 44, 55, 66)]
    for mode in ('gauge', 'mean'):
        fluid = dict(mode='stokes', density=1, viscosity=1, boundaries=boundaries)
        if mode == 'gauge':
            fluid['pressure_gauge'] = dict(node=first_node, value=2)
        else:
            fluid['pressure_normalization'] = 'mean'
        case = a.work / f'flow_{mode}.json'
        case.write_text(json.dumps(dict(mesh=str(mesh), output=str(a.work / 'unused.vtu'), fluid=fluid,
                                       solver=dict(relative_tolerance=1e-10, absolute_tolerance=1e-12,
                                                   maximum_iterations=30))))
        cases.append((f'flow_{mode}', case))
    for name, case in cases:
        reference = a.work / f'{name}_direct.vtu'
        direct_text = run([a.executable, '-case', case, '-output', reference])
        (a.work / f'{name}_direct.log').write_text(direct_text)
        expected_physics = physical_records(direct_text)
        expected = fields(reference, 1)
        solid = name in ('domains', 'hyperelastic')
        expected_solid = fields(reference.with_stem(reference.stem + '_solid'), 1) if solid else None
        for ranks in (1, 2, 4):
            part = a.work / f'{name}_part{ranks}'
            run([a.executable, '-case', case, '-prepare', part, '-parts', ranks])
            output = a.work / f'{name}_schur{ranks}.vtu'
            command = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [
                a.executable, '-case', case, '-partition', part, '-output', output,
                '-linear_report'] + (['-pc_recipe', a.recipe] if a.recipe else ['-schur_pc'])
            if a.recipe == 'hybrid':
                command += ['-verify_operator_permutation']
            text = run(command)
            actual_physics = physical_records(text)
            compare_physics(expected_physics, actual_physics)
            (a.work / f'{name}_schur{ranks}.log').write_text(text)
            residuals = [dict(item.split('=',1) for item in line.split()[1:])
                         for line in text.splitlines() if line.startswith('linear_residual ')]
            assert residuals and 'linear_residual_unavailable' not in text, text
            for residual in residuals:
                norm, rhs = float(residual['norm']), float(residual['rhs_norm'])
                assert math.isfinite(norm) and norm <= 1e-8 + 1e-7 * rhs, residual
            field_residuals = [dict(item.split('=',1) for item in line.split()[1:])
                               for line in text.splitlines() if line.startswith('linear_field_residual ')]
            expected_fields = {'velocity', 'pressure'}
            if not name.startswith('flow'):
                expected_fields |= {'mesh', 'rigid' if name == 'rigid' else 'structure'}
            assert {f['name'] for f in field_residuals} == expected_fields, text
            assert len(field_residuals) == len(residuals) * len(expected_fields), text
            for field in field_residuals:
                assert math.isfinite(float(field['rms'])) and float(field['rms']) >= 0, field
                assert float(field['constraint_max']) < 1e-8, field
            reports = [dict(item.split('=',1) for item in line.split()[1:])
                       for line in text.splitlines() if line.startswith('solver_report ')]
            if a.recipe == 'hybrid':
                assert len(re.findall(r'^operator_permutation dofs=', text, re.M)) == len(reports), text
            if name in ('flow_gauge', 'flow_mean'):
                pressure = 2 if name == 'flow_gauge' else 0
                assert all(abs(row['mean_pressure']-pressure) < 2e-8 for row in actual_physics)
            assert sum(int(r['linear_completed']) for r in reports) == len(residuals), text
            for report in reports:
                assert report['linear_started'] == report['linear_completed'], report
                for key in ('setup_seconds', 'schur_setup_seconds', 'linear_seconds',
                            'linear_diagnostic_seconds', 'finalize_seconds', 'callback_seconds',
                            'failure_sync_seconds', 'assembly_finalize_seconds', 'constraint_seconds'):
                    assert math.isfinite(float(report[key])) and float(report[key]) >= 0, report
                # Each phase maximum is bounded by the maximum enclosing successful assembly time.
                # Do not sum rank maxima: they can come from different ranks.
                for key in ('callback_seconds', 'failure_sync_seconds', 'assembly_finalize_seconds', 'constraint_seconds'):
                    assert float(report[key]) <= float(report['assembly_seconds']) * 1.0001 + 1e-9, report
            nodes = [dict(item.split('=',1) for item in line.split()[1:])
                     for line in text.splitlines() if line.startswith('solver_node ')]
            assert {int(node['rank']) for node in nodes} == set(range(ranks)), text
            assert any('fieldsplit_pressure_' in node['prefix'] for node in nodes), text
            assert any(node['path'].endswith('/coarse') for node in nodes), text
            assert all(int(node['ksp_reason']) > 0 for node in nodes if node['path']=='root'), text
            assert 'solver_node_unavailable' not in text, text
            # Matrix dimensions are local metadata reads, including coarse subcommunicators.
            dofs = int(reports[-1]['dofs'])
            for node in nodes:
                assert int(node['operator_set']) == 1, node
                rows, cols = int(node['operator_rows']), int(node['operator_columns'])
                assert 0 < rows <= dofs and rows == cols, node
                assert 0 <= int(node['operator_local_rows']) <= rows, node
                assert 0 <= int(node['operator_local_columns']) <= cols, node
                if node['path'] == 'root':
                    assert rows == dofs, node
            # Each steady/time-step report includes one root per world rank.
            roots = [node for node in nodes if node['path'] == 'root']
            assert len(roots) == len(reports) * ranks, roots
            assert sum(int(node['operator_local_rows']) for node in roots) == len(reports) * dofs
            error = compare(expected, fields(output, ranks))
            if solid:
                compare(expected_solid, fields(output.with_stem(output.stem + '_solid'), ranks))
                assert max(abs(float(x)) for x in re.findall(r'body_balance=(\S+)', text)) < 2e-8
            iterations = sum(map(int, re.findall(r'linear_iterations=(\d+)', text)))
            assert iterations > 0
            results.append(dict(case=name, ranks=ranks, recipe=a.recipe or 'legacy_schur',
                                max_field_error=error, physical=actual_physics,
                                direct_physical=expected_physics, linear_iterations=iterations))
            print(name, ranks, 'max_error', error, 'linear_iterations', iterations, flush=True)
        if name == 'domains':
            fd = a.work / 'domains_fd.vtu'
            run([a.executable, '-case', case, '-output', fd, '-fsi_fd_tangent'])
            compare(expected, fields(fd, 1))
            compare(expected_solid, fields(fd.with_stem(fd.stem + '_solid'), 1))
    (a.work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('Schur, MPI, physical observations and FSI tangent equivalence passed')


if __name__ == '__main__':
    main()
