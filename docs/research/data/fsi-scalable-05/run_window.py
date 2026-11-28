"""Run one cold-start window against a frozen partition and retain the raw solver receipt."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'fsi-scalable-02'))
from paired_tube import compare, digest, physical, read_mesh, run, save
from arterial_ksp import options
from tube_protocol import audit_corrections, compare_trajectories, select, solver_options


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('case', choices=('A', 'B', 'C'))
    cli.add_argument('steps', type=int, choices=(1, 4, 20, 32, 100, 224))
    cli.add_argument('profile')
    cli.add_argument('binary', type=Path)
    cli.add_argument('output', type=Path)
    cli.add_argument('--reference', type=Path)
    cli.add_argument('--limit', type=int, required=True, help='Process-tree wall budget in seconds')
    args = cli.parse_args()
    work = Path.home() / 'workspace'
    archived = (work / 'fsi-scalable-03-runs/C-first-64' if args.case == 'C'
                else work / 'fsi-scalable-04-runs' / (args.case + '-return'))
    origin = json.loads((archived / 'run.json').read_text())
    part = Path(origin['command'][origin['command'].index('-partition') + 1])
    ranks = {'A': 4, 'B': 32, 'C': 64}[args.case]
    affinity = sorted(os.sched_getaffinity(0))
    if not os.getenv('SLURM_JOB_ID') or len(affinity) != ranks or os.getenv('PETSC_OPTIONS'):
        cli.error('requires one allocated physical core per rank and no PETSC_OPTIONS override')
    binary = args.binary.resolve(strict=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    build = json.loads((binary.parent / 'build-receipt.json').read_text())
    compiled_paths = ['src', 'include', 'cmake', 'CMakeLists.txt']
    source_diff = subprocess.run(['git','diff','--quiet',build['source'],source,'--',*compiled_paths],
                                 cwd=SOURCE).returncode
    if build['binary'] != digest(binary) or source_diff:
        cli.error('build receipt differs from executable or checkout')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    policy = select('CALIBRATED-v2', args.profile)
    row = dict(case=args.case, steps=args.steps, profile=args.profile, policy=policy,
               source=source, compiled_source=build['source'], binary=build['binary'], job=os.environ['SLURM_JOB_ID'],
               ranks=ranks, affinity=affinity, limit_seconds=args.limit, rss_limit=140*2**30,
               archive_receipt=digest(archived/'run.json'), qualification='open')
    try:
        for name in ('case.json', 'fluid.msh', 'solid.msh'):
            if digest(archived/name) != origin['inputs'][name]:
                raise ValueError('Frozen input changed: ' + name)
            shutil.copyfile(archived/name, out/name)
        pieces = {name: digest(part/name) for name in
                  ['manifest.yaml', *(f'rank_{i}.h5' for i in range(ranks))]}
        if any(origin['partition'].get(name) != sha for name, sha in pieces.items()):
            raise ValueError('Frozen partition differs from the archived receipt')
        row['partition'] = pieces
        config = json.loads((out/'case.json').read_text())
        if args.steps != config['fsi']['steps']:
            config['fsi'].update(steps=args.steps, checkpoint_interval=args.steps)
            save(out/'case.json', config)
        row['inputs'] = {name: digest(out/name) for name in ('case.json', 'fluid.msh', 'solid.msh')}
        recipe = [] if args.profile == 'lu' else options('inner-mgs')
        policy_flags = solver_options(policy)
        # The same outer option must never appear twice in a campaign command.
        for key in ('-ksp_rtol', '-ksp_atol', '-ksp_type', '-ksp_norm_type', '-ksp_pc_side'):
            if key in recipe and key in policy_flags:
                pos = recipe.index(key)
                del recipe[pos:pos+2]
        cmd = ['/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpiexec', '--map-by', 'core',
               '--bind-to', 'core', '-n', str(ranks), str(binary), '-case', 'case.json',
               '-partition', str(part), *recipe, *policy_flags, '-snes_monitor',
               '-snes_linesearch_monitor', '-options_view']
        os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
        run(out, cmd, row, args.limit, row['rss_limit'])
        row['linear'] = audit_corrections(out, args.steps, ranks, policy)
        row['qualification'] = 'linear_window_only'
        if args.steps >= 4:
            meshes = [read_mesh(out/(name+'.msh')) for name in ('fluid','solid')]
            state = physical(out, 'eon', meshes, args.steps, ranks)
            checks = compare(state, state)
            if not all(0 <= v <= 1 for v in checks.values()):
                raise ValueError('Frozen per-run physical budget failed')
            row['physical'] = checks
            row['qualification'] = 'awaiting_independent_crosscheck'
            if args.reference:
                ref = args.reference.resolve(strict=True)
                prev = json.loads((ref/'window.json').read_text())
                if (prev['qualification'] != 'awaiting_independent_crosscheck' or
                        prev['profile'] != 'lu' or args.profile == 'lu' or
                        any(prev[k] != row[k] for k in ('inputs', 'partition', 'binary', 'source')) or
                        prev['log_sha256'] != digest(ref/'solve.log')):
                    raise ValueError('Invalid or incompatible independent LU reference candidate')
                audit_corrections(ref, args.steps, ranks, select('CALIBRATED-v2','lu'))
                row['comparison'] = compare_trajectories(out, ref, args.steps, meshes,
                                                          ranks=(ranks,ranks), policy=policy)
                row['reference_receipt'] = digest(ref/'window.json')
                row['qualification'] = 'independent_pair_passed'
    except Exception as error:
        row.update(qualification='failed', error=str(error))
        raise
    finally:
        if (out/'solve.log').is_file():
            log = (out/'solve.log').read_text(errors='replace')
            row['accepted_steps'] = list(map(int, re.findall(r'^fsi_step=(\d+)', log, re.M)))
            row['core_hours'] = ranks * row.get('T_job', 0) / 3600
        save(out/'window.json', row)


if __name__ == '__main__':
    main()
