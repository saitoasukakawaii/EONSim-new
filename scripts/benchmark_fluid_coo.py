"""Paired fixed-topology fluid Jacobian assembly benchmark; no assumed speedup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from profile_multistep_setup import parse
from profile_schur_mesh import ROOT

sys.path.insert(0, str(ROOT/'tests'))
from verify_fluid_coo import check_plan, compare, records
from verify_schur import fields
sys.path.insert(0, str(ROOT/'cases/poisson'))
from generate_mesh import write_mesh


def stats(values):
    return dict(median=statistics.median(values), minimum=min(values), maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--subdivisions', type=int, nargs='+', default=[4, 8])
    parser.add_argument('--ranks', type=int, nargs='+', default=[1, 2, 4])
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('Use at least three paired repetitions')
    if args.ranks != sorted(set(args.ranks)) or not args.ranks or args.ranks[0] != 1 or any(r not in (1, 2, 4) for r in args.ranks):
        parser.error('Use an ascending unique subset of 1/2/4 beginning with 1')
    if args.subdivisions != sorted(set(args.subdivisions)) or any(n < 2 for n in args.subdivisions):
        parser.error('Use positive, ascending unique subdivisions >= 2')
    exe = args.executable.resolve(); work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    runs, pairs, commands, cases = [], [], [], []

    def run(command, stem):
        command = list(map(str, command)); commands.append(command)
        begin = time.perf_counter()
        with (work/(stem+'.log')).open('w') as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=240)
        return time.perf_counter()-begin, (work/(stem+'.log')).read_text()

    for subdivisions in args.subdivisions:
        mesh = work/f'cube{subdivisions}.msh'; write_mesh(mesh, subdivisions)
        case = work/f'case{subdivisions}.yaml'
        case.write_text((ROOT/'cases/fluid/transient.yaml').read_text().replace('mesh: ../poisson/cube.msh', f'mesh: {mesh}'))
        cases.append(dict(subdivisions=subdivisions, yaml=case.read_text(), mesh_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest()))
        rank_reference = None
        for ranks in args.ranks:
            prefix = f'n{subdivisions}-r{ranks}'; part = work/(prefix+'-partition')
            run([exe, '-case', case, '-prepare', part, '-parts', ranks], prefix+'-prepare')
            reference = None
            for repeat in range(-1, args.repeats):
                pair = {}
                for coo in ((False, True) if repeat % 2 else (True, False)):
                    stem = prefix+f'-repeat{repeat}-coo{int(coo)}'; output = work/(stem+'.vtu')
                    command = [args.mpiexec, '-n', ranks, exe, '-case', case, '-partition', part,
                               '-output', output, '-solver_report']+(['-fluid_coo'] if coo else [])
                    wall, text = run(command, stem)
                    steps = parse(text, 'fluid_step'); check_plan(text, ranks, coo)
                    physical = fields(output, ranks)
                    if reference is None: reference = physical
                    if rank_reference is None: rank_reference = physical
                    row = dict(subdivisions=subdivisions, ranks=ranks, repeat=repeat, coo=coo, log=stem+'.log',
                        wall_seconds=wall, steps=steps, field_delta=compare(reference, physical),
                        rank_delta=compare(rank_reference, physical),
                        plan=records(text, 'fluid_coo_plan'))
                    for key in ('solve_seconds', 'assembly_seconds', 'callback_seconds', 'assembly_finalize_seconds', 'linear_seconds'):
                        row[key] = sum(s[key] for s in steps)
                    row['first_step_solve_seconds'] = steps[0]['solve_seconds']
                    row['later_step_solve_seconds'] = statistics.mean(s['solve_seconds'] for s in steps[1:])
                    row['peak_rss_bytes'] = max(float(s['peak_rss_max_bytes']) for s in steps)
                    row['snes_iterations'] = sum(s['snes_iterations'] for s in steps)
                    row['linear_iterations'] = sum(s['linear_iterations'] for s in steps)
                    runs.append(row); pair[coo] = row
                if repeat >= 0:
                    pairs.append(dict(subdivisions=subdivisions, ranks=ranks, repeat=repeat,
                        relative_change={key:pair[True][key]/pair[False][key]-1 for key in
                                         ('wall_seconds', 'solve_seconds', 'assembly_seconds')},
                        iteration_trajectory_equal=[(s['snes_iterations'], s['linear_iterations']) for s in pair[True]['steps']]
                            == [(s['snes_iterations'], s['linear_iterations']) for s in pair[False]['steps']]))
                (work/'partial.json').write_text(json.dumps(dict(runs=runs, pairs=pairs, commands=commands), indent=2)+'\n')
                print(prefix, repeat, 'validated', flush=True)
    summary = []
    measured = [r for r in runs if r['repeat'] >= 0]
    metrics = ('wall_seconds', 'solve_seconds', 'assembly_seconds', 'callback_seconds', 'assembly_finalize_seconds',
               'first_step_solve_seconds', 'later_step_solve_seconds', 'linear_seconds', 'peak_rss_bytes')
    for subdivisions in args.subdivisions:
        for ranks in args.ranks:
            group = [r for r in measured if r['subdivisions'] == subdivisions and r['ranks'] == ranks]
            group_pairs = [p for p in pairs if p['subdivisions'] == subdivisions and p['ranks'] == ranks]
            summary.append(dict(subdivisions=subdivisions, ranks=ranks,
                modes=[dict(coo=coo, metrics={key:stats([r[key] for r in group if r['coo']==coo]) for key in metrics}) for coo in (False, True)],
                paired_relative_change={key:stats([p['relative_change'][key] for p in group_pairs])
                                        for key in ('wall_seconds', 'solve_seconds', 'assembly_seconds')}))
    def metadata(command):
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return dict(command=command, returncode=result.returncode, output=result.stdout)
    result = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_status=metadata(['git', 'status', '--short']), executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        environment=[metadata(c) for c in (['uname', '-a'], ['lscpu'], ['free', '-b'], ['c++', '--version'],
                     [args.mpiexec, '--version'], ['pkg-config', '--modversion', 'PETSc'], ['cmake', '--version'])],
        cmake_cache=(exe.parent/'CMakeCache.txt').read_text(), threads=1, cases=cases, commands=commands,
        runs=runs, pairs=pairs, summary=summary)
    (work/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: {len(measured)} measured runs, {len(runs)-len(measured)} warmups; paired data in results.json')


if __name__ == '__main__':
    main()
