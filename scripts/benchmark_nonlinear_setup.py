"""Measure fixed transient solves; never infer SNES lifetime cost from nested timers."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def fields(output):
    pieces = [output] if output.exists() else [output.with_suffix('.pvtu').parent / e.attrib['Source']
        for e in ET.parse(output.with_suffix('.pvtu')).findall('.//Piece')]
    values = []
    for piece in pieces:
        tree = ET.parse(piece)
        for array in tree.findall('.//PointData/DataArray'):
            data = [float(x) for x in (array.text or '').split()]
            if not all(math.isfinite(x) for x in data):
                raise RuntimeError('Nonfinite output field')
            values.extend(data)
    if not values:
        raise RuntimeError('Missing output fields')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', default='mpiexec')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('At least three repetitions required')
    exe, work = args.executable.resolve(), args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)  # Never mix runs with stale evidence.
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    case = ROOT / 'cases/fluid/transient.yaml'
    rows, commands = [], []

    def run(cmd, log):
        commands.append(cmd)
        begin = time.perf_counter()
        with log.open('w') as f:
            subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=180)
        return time.perf_counter() - begin, log.read_text()

    for ranks in (1, 2):
        partition = work / f'partition{ranks}'
        run([str(exe), '-case', str(case), '-prepare', str(partition), '-parts', str(ranks)], work / f'prepare{ranks}.log')
        reference = None
        # One unmeasured warmup per rank; interleave off/on runs to reduce order bias.
        for repeat in range(-1, args.repeats):
            for report in ([False] if repeat == -1 else [False, True]):
                stem = f'r{ranks}-n{repeat}-report{int(report)}'
                output = work / (stem + '.vtu')
                cmd = [args.mpiexec, '-n', str(ranks), str(exe), '-case', str(case), '-partition', str(partition), '-output', str(output)]
                if report:
                    cmd += ['-solver_report', '-linear_report', '-log_view', ':' + str(work / (stem + '-petsc.log'))]
                elapsed, text = run(cmd, work / (stem + '.log'))
                current = fields(output)
                if reference is None:
                    reference = current
                if len(current) != len(reference) or any(abs(a-b) > 1e-10*(1+abs(b)) for a,b in zip(current, reference)):
                    raise RuntimeError('Output changed across repeats/report modes at fixed rank')
                stages = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith('solver_report ')]
                if report and len(stages) != 10:
                    raise RuntimeError(f'Expected 10 step reports, got {len(stages)}')
                if repeat >= 0:
                    rows.append(dict(ranks=ranks, repeat=repeat, report=report, wall_seconds=elapsed,
                                     field_max_delta=max(abs(a-b) for a,b in zip(current,reference)), stages=stages))
    summary = []
    for ranks in (1,2):
        for report in (False,True):
            samples = [r['wall_seconds'] for r in rows if r['ranks']==ranks and r['report']==report]
            summary.append(dict(ranks=ranks, report=report, count=len(samples), median=statistics.median(samples), minimum=min(samples), maximum=max(samples)))
    result = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), case_sha256=hashlib.sha256(case.read_bytes()).hexdigest(),
                  cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(), memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                  thread_limits=1, commands=commands, summary=summary, runs=rows)
    (work/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
