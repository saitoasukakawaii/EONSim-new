"""Schur/GAMG versus direct solves and reference FSI tangent on 1/2/4 ranks."""
import argparse
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
                '-schur_pc', '-solver_report']
            text = run(command)
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
