"""Bounded SOLVER-04 study: steady flow, 3 meshes, 1/2 ranks, direct reference."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/poisson'))
sys.path.insert(0, str(ROOT / 'tests'))
from generate_mesh import write_mesh
from verify_schur import fields


PHASES = ('callback_seconds', 'failure_sync_seconds',
          'assembly_finalize_seconds', 'constraint_seconds')


def records(text, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(prefix + ' ')]


def integer(record, key, minimum=0):
    """Require an integer token, rather than accepting NaN or fractional counters."""
    try:
        value = int(record[key])
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f'Missing or invalid integer field: {key}') from exc
    if value < minimum:
        raise RuntimeError(f'{key} must be >= {minimum}')
    return value


def measurement(record, key):
    try:
        value = float(record[key])
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f'Missing or invalid measurement: {key}') from exc
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(f'{key} must be finite and nonnegative')
    return value


def parse(text, ranks):
    reports, nodes = records(text, 'solver_report'), records(text, 'solver_node')
    if len(reports) != 1 or 'solver_node_unavailable' in text:
        raise RuntimeError('Expected one complete steady solver report')
    report = reports[0]
    required = set(PHASES) | {'assembly_seconds', 'ghost_seconds', 'domain_rejections',
                              'solve_seconds', 'schur_setup_seconds', 'linear_seconds',
                              'rss_max_bytes', 'linear_iterations', 'dofs', 'ranks'}
    if not required <= report.keys():
        raise RuntimeError('Missing assembly phase fields; rebuild the current solver')
    if integer(report, 'domain_rejections') != 0:
        raise RuntimeError('Rejected evaluations require a separate profiling study')
    for key in ('snes_reason', 'ksp_reason'):
        integer(report, key, 1)
    integer(report, 'linear_iterations')
    integer(report, 'dofs', 1)
    if integer(report, 'ranks', 1) != ranks:
        raise RuntimeError('Report rank count differs from requested run')
    for key in report:
        if key.endswith(('_seconds', '_bytes')):
            measurement(report, key)
    for key in PHASES:
        if float(report[key]) > float(report['assembly_seconds']) * 1.0001 + 1e-9:
            raise RuntimeError('Phase exceeds enclosing assembly time')
    identities = [(integer(n, 'rank'), n.get('path')) for n in nodes]
    if any(not path for _, path in identities) or len(set(identities)) != len(identities):
        raise RuntimeError('Missing path or duplicate hierarchy node')
    if {rank for rank, _ in identities} != set(range(ranks)):
        raise RuntimeError('Missing rank hierarchy')
    if {rank for rank, path in identities if path == 'root'} != set(range(ranks)):
        raise RuntimeError('Missing root hierarchy')
    if not any(path.endswith('/coarse') for _, path in identities):
        raise RuntimeError('Missing GAMG coarse hierarchy')
    for node in nodes:
        if node['path'] == 'root':
            integer(node, 'ksp_reason', 1)
    return report, nodes


def delta(reference, current):
    if reference.keys() != current.keys():
        raise RuntimeError('Output node sets differ')
    error = 0.
    for node in reference:
        a, b = reference[node], current[node]
        if len(a) != len(b) or not all(math.isfinite(v) for v in a+b):
            raise RuntimeError('Invalid output fields')
        error = max(error, max(abs(x-y) for x, y in zip(a, b)))
    if error > 2e-8:
        raise RuntimeError(f'Direct/Schur or rank mismatch: {error}')
    return error


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, required=True)
    p.add_argument('--mpiexec', required=True)
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    exe, work = args.executable.resolve(), args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    commands, runs, cases = [], [], []

    def run(cmd, stem):
        commands.append(cmd)
        start = time.perf_counter()
        with (work / (stem+'.log')).open('w') as stream:
            subprocess.run(cmd, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        return time.perf_counter()-start, (work / (stem+'.log')).read_text()

    for n in (2, 4, 6):
        mesh, case = work/f'mesh{n}.msh', work/f'case{n}.yaml'
        write_mesh(mesh, n)
        yaml = (ROOT/'cases/fluid/steady.yaml').read_text()
        yaml = yaml.replace('../poisson/cube.msh', mesh.name)
        case.write_text(yaml)
        cases.append(dict(subdivisions=n, nodes=(n+1)**3, tetrahedra=6*n**3,
                          yaml=yaml, mesh_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest()))
        single_reference = None
        for ranks in (1, 2):
            stem = f'n{n}-r{ranks}'
            part = work/(stem+'-part')
            run([str(exe), '-case', str(case), '-prepare', str(part), '-parts', str(ranks)], stem+'-prepare')
            base = [args.mpiexec, '-n', str(ranks), str(exe), '-case', str(case), '-partition', str(part)]
            direct = work/(stem+'-direct.vtu')
            wall, text = run(base+['-output', str(direct), '-solver_report'], stem+'-direct')
            direct_report = records(text, 'solver_report')
            if len(direct_report) != 1 or any(int(direct_report[0][k]) <= 0 for k in ('snes_reason','ksp_reason')):
                raise RuntimeError('Invalid direct reference')
            reference = fields(direct, ranks)
            if single_reference is None:
                single_reference = reference
            rank_delta = delta(single_reference, reference)
            runs.append(dict(n=n, ranks=ranks, mode='direct', wall_seconds=wall,
                             rank_delta=rank_delta, report=direct_report[0]))
            for repeat in range(3):
                label = stem+f'-schur{repeat}'
                output = work/(label+'.vtu')
                wall, text = run(base+['-output',str(output),'-schur_pc','-solver_report'], label)
                report, nodes = parse(text, ranks)
                error = delta(reference, fields(output, ranks))
                runs.append(dict(n=n,ranks=ranks,mode='schur',repeat=repeat,wall_seconds=wall,
                                 max_delta=error,report=report,hierarchy=nodes))
                (work/'partial.json').write_text(json.dumps(runs,indent=2)+'\n')
            print(stem, 'passed', flush=True)
    summary = []
    for n in (2,4,6):
        for ranks in (1,2):
            group = [r for r in runs if r['n']==n and r['ranks']==ranks and r['mode']=='schur']
            metrics = {}
            for key in ('solve_seconds','schur_setup_seconds','linear_seconds','rss_max_bytes','linear_iterations',
                        'assembly_seconds','ghost_seconds') + PHASES:
                values = [float(r['report'][key]) for r in group]
                metrics[key] = dict(median=statistics.median(values),minimum=min(values),maximum=max(values))
            summary.append(dict(n=n,ranks=ranks,dofs=int(group[0]['report']['dofs']),metrics=metrics,
                                max_delta=max(r['max_delta'] for r in group)))
    result = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases=cases,commands=commands,
                  cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
                  memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),threads_per_rank=1,
                  runs=runs,summary=summary)
    (work/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: 6 direct references and 18 Schur runs; results.json')


if __name__ == '__main__':
    main()
