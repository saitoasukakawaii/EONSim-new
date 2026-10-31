"""Small fixed-problem comparison of direct/physics/quantity/hybrid (not scaling)."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from verify_schur import fields, compare, physical_records, compare_physics, generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--environment-evidence', type=Path, required=True,
                        help='Completed cloud/run.sh Release evidence/summary.json for this build')
    args = parser.parse_args()
    exe, work = args.executable.resolve(), args.work.resolve()
    environment = json.loads(args.environment_evidence.read_text())
    if environment['mode'] != 'release' or environment['status'] != 'passed':
        raise RuntimeError('Benchmark requires completed Release validation evidence')
    if exe.parent != args.environment_evidence.resolve().parent.parent:
        raise RuntimeError('Executable and evidence must belong to the same build directory')
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    commands, rows = [], []

    def run(command, label):
        command = list(map(str, command))
        start = time.perf_counter()
        result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        wall = time.perf_counter()-start
        (work / f'{label}.log').write_text(result.stdout)
        commands.append(dict(command=command, exit_code=result.returncode, wall_seconds=wall))
        if result.returncode:
            raise RuntimeError(f'{label} failed; see saved log')
        return result.stdout, wall

    cases = [('flow', ROOT / 'cases/fluid/rotated_channel.yaml'),
             ('domains', generate(work / 'domains', 3))]
    metrics = ('setup_seconds', 'schur_setup_seconds', 'solve_seconds', 'linear_seconds',
               'linear_iterations', 'rss_max_bytes', 'peak_rss_max_bytes')
    modes = ('direct', 'physics', 'quantity', 'hybrid')
    for name, case in cases:
        for ranks in (1, 2, 4):
            label = f'{name}-r{ranks}'
            part = work / f'{label}-part'
            run([exe, '-case', case, '-prepare', part, '-parts', ranks], label+'-prepare')
            base = [args.mpiexec, '-n', ranks, exe, '-case', case, '-partition', part, '-solver_report']
            reference = work / f'{label}-reference.vtu'
            ref_text, _ = run(base+['-output', reference], label+'-reference')
            ref_fields, ref_physics = fields(reference, ranks), physical_records(ref_text)
            ref_solid = fields(reference.with_stem(reference.stem+'_solid'), ranks) if name == 'domains' else None
            # One unrecorded warmup per mode, then rotate order over three repeats.
            for repeat in (-1, 0, 1, 2):
                order = modes if repeat < 0 else modes[repeat:] + modes[:repeat]
                for mode in order:
                    stem = f'{label}-{mode}-{repeat}'
                    output = work / f'{stem}.vtu'
                    command = base+['-output', output]+([] if mode == 'direct' else ['-pc_recipe', mode])
                    text, wall = run(command, stem)
                    error = compare(ref_fields, fields(output, ranks))
                    if ref_solid is not None:
                        error = max(error, compare(ref_solid, fields(output.with_stem(output.stem+'_solid'), ranks)))
                    compare_physics(ref_physics, physical_records(text))
                    reports = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
                               if line.startswith('solver_report ')]
                    assert reports, text
                    for report in reports:
                        assert int(report['snes_reason']) > 0 and int(report['ksp_reason']) > 0, report
                        for key in metrics:
                            assert math.isfinite(float(report[key])) and float(report[key]) >= 0, report
                    if repeat >= 0:
                        totals = {key: (max if key.endswith('_bytes') else sum)(float(r[key]) for r in reports)
                                  for key in metrics}
                        rows.append(dict(case=name, ranks=ranks, mode=mode, repeat=repeat,
                                         wall_seconds=wall, max_field_error=error, metrics=totals, reports=reports))
                        (work / 'partial.json').write_text(json.dumps(rows, indent=2)+'\n')
            print(label, 'verified', flush=True)
    summary = []
    for name, _ in cases:
        for ranks in (1, 2, 4):
            for mode in modes:
                group = [row for row in rows if (row['case'], row['ranks'], row['mode']) == (name, ranks, mode)]
                summary.append(dict(case=name, ranks=ranks, mode=mode, metrics={
                    key: dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
                    for key in metrics for values in [[row['metrics'][key] for row in group]]}))
    result = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                  executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), platform=platform.platform(),
                  build_environment={key: environment[key] for key in
                                     ('mode', 'petsc', 'platform', 'resources', 'lock_sha256', 'dependencies')},
                  affinity_cpus=len(os.sched_getaffinity(0)), threads=1, repeats=3,
                  cpu_model=next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                                  if line.startswith('model name')), 'unknown'),
                  source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for folder in ('include', 'src') for p in sorted((ROOT / folder).rglob('*')) if p.is_file()},
                  cases=[dict(name=name, path=str(path), configuration=path.read_text(),
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in cases],
                  scope='Two small single-node problems; nested phase times must not be added; RSS is rank maximum',
                  commands=commands, runs=rows, summary=summary)
    (work / 'results.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
