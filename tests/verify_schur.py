"""Schur/GAMG versus direct solves and reference FSI tangent on 1/2/4 ranks."""
import argparse
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
    error = max(abs(v-w) for node in x for v, w in zip(x[node], y[node]))
    assert error < 2e-8, error
    return error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--recipe', choices=['physics', 'quantity', 'hybrid'])
    a = parser.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    cases = [('flow', ROOT / 'cases/fluid/rotated_channel.yaml'),
             ('domains', generate(a.work / 'domains', 3)),
             ('rigid', ROOT / 'cases/fsi/rigid.yaml'),
             ('hyperelastic', ROOT / 'cases/fsi/hyperelastic.yaml')]
    for name, case in cases:
        reference = a.work / f'{name}_direct.vtu'
        run([a.executable, '-case', case, '-output', reference])
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
            text = run(command)
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
            if name != 'flow':
                expected_fields |= {'mesh', 'rigid' if name == 'rigid' else 'structure'}
            assert {f['name'] for f in field_residuals} == expected_fields, text
            assert len(field_residuals) == len(residuals) * len(expected_fields), text
            for field in field_residuals:
                assert math.isfinite(float(field['rms'])) and float(field['rms']) >= 0, field
                assert float(field['constraint_max']) < 1e-8, field
            reports = [dict(item.split('=',1) for item in line.split()[1:])
                       for line in text.splitlines() if line.startswith('solver_report ')]
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
            print(name, ranks, 'max_error', error, 'linear_iterations', iterations, flush=True)
        if name == 'domains':
            fd = a.work / 'domains_fd.vtu'
            run([a.executable, '-case', case, '-output', fd, '-fsi_fd_tangent'])
            compare(expected, fields(fd, 1))
            compare(expected_solid, fields(fd.with_stem(fd.stem + '_solid'), 1))
    print('Schur, MPI and FSI tangent equivalence passed')


if __name__ == '__main__':
    main()
