"""Bounded first-Newton probe on the archived C system and partition (not a trajectory)."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

from tube_protocol import BLOCKS, audit_row, records, select, solver_options

DATA = Path(__file__).resolve().parent.parent
ROOT = DATA.parents[2]
sys.path[:0] = [str(DATA/'fsi-scalable-02'), str(DATA/'fsi-scalable-04'), str(ROOT/'tests')]
from paired_tube import digest, run, save
from arterial_ksp import options
from verify_fsi_multigrid import flags
from refine_system import WIDE, audit, matrix, norm, read_layout, vector


def describe(mode):
    if mode == 'physics':
        opts = options('inner-mgs')
        for field in ('fluid_fieldsplit_velocity', 'fluid_fieldsplit_pressure', 'solid', 'mesh'):
            opts += ['-fieldsplit_' + field + '_ksp_converged_reason']
    else:
        opts = flags('mono_pressure_auto', ports=True)
    # Drop previous outer defaults before adding the frozen fixed profile.
    for key in ('-ksp_type', '-ksp_norm_type', '-ksp_pc_side', '-ksp_rtol', '-ksp_atol', '-ksp_max_it'):
        if key in opts:
            i = opts.index(key)
            del opts[i:i+2]
    return opts


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('physics', 'pressure-mg'))
    cli.add_argument('binary', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    job = os.environ.get('SLURM_JOB_ID')
    if not job or len(os.sched_getaffinity(0)) != 64:
        cli.error('requires a 64-core Slurm allocation')
    if os.environ.get('PETSC_OPTIONS'):
        cli.error('requires clean PETSC_OPTIONS')
    old = Path.home()/'workspace/fsi-scalable-03-runs'
    case, layout = old/'C-first-64', old/'C-layout'
    partition = old.parent/'fsi-scalable-02-runs/C20-fixed/partition'
    index = json.loads((DATA/'fsi-scalable-03/log-index.json').read_text())
    artifacts = [case/n for n in ('operator.petsc', 'rhs.petsc', 'diagnosis.json')]
    for p in artifacts + list(layout.glob('*.csv')):
        if digest(p) != index['$HOME/' + p.relative_to(Path.home()).as_posix()]['sha256']:
            raise ValueError(f'Changed archived artifact {p}')
    frozen = json.loads((case/'diagnosis.json').read_text())
    parts = {f.name:digest(f) for f in partition.iterdir() if f.is_file()}
    if parts != frozen['partition']:
        raise ValueError('C partition changed')
    exe = args.binary.resolve(strict=True)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    policy = select('CALIBRATED-v2', 'fixed-1e-8')
    for n, expected in frozen['inputs'].items():
        if digest(case/n) != expected:
            raise ValueError(f'Changed frozen input {n}')
        shutil.copyfile(case/n, root/n)
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    cmd = [frozen['command'][0], '--map-by', 'core', '--bind-to', 'core', '-n', '64',
           str(exe), '-case', 'case.json', '-partition', str(partition),
           *describe(args.mode), *solver_options(policy), '-ksp_max_it', '500',
           '-snes_max_it', '1', '-stop_after', '1', '-ksp_monitor', '-ksp_converged_reason',
           '-ksp_view_mat', 'binary:operator.petsc', '-ksp_view_rhs', 'binary:rhs.petsc',
           '-ksp_view_solution', 'binary:iterate.petsc', '-options_view', '-options_left']
    row = dict(scope='first correction only', mode=args.mode, protocol_id=policy['protocol_id'],
               profile=policy['profile'], protocol_hash=policy['hash'], inputs=frozen['inputs'],
               partition=parts, archive_receipt=digest(case/'diagnosis.json'), job=job,
               source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               binary_sha256=digest(exe), affinity=sorted(os.sched_getaffinity(0)),
               budget=dict(seconds=420, process_tree_bytes=100*2**30, outer_iterations=500))
    try:
        try:
            run(root, cmd, row, row['budget']['seconds'], row['budget']['process_tree_bytes'])
        except RuntimeError:
            # The intentional single-Newton cap can reject the time step after a valid linear solve.
            # Validate the returned vector and failure reason separately below.
            pass
        lines = (root/'solve.log').read_text(errors='replace').splitlines()
        row['accepted_steps'] = len(records(lines, 'fsi_step='))
        row['linear'] = records(lines, 'linear_residual ') + records(lines, 'linear_iteration_limit_residual ')
        row['blocks'] = records(lines, 'linear_field_residual ') + records(lines, 'linear_iteration_limit_field_residual ')
        row['solvers'] = [r for r in records(lines, 'solver_node ') if r.get('rank') == '0']
        row['rcr'] = [r for r in records(lines, 'rcr_port_stats ') if r.get('rank') == '0']
        row['artifacts'] = {n:digest(root/n) for n in ('operator.petsc', 'rhs.petsc', 'iterate.petsc') if (root/n).is_file()}
        if len(row['linear']) != 1 or len(row['blocks']) != 4:
            raise ValueError('Missing or repeated first correction')
        if any(row['artifacts'].get(n) != frozen['artifacts'][n] for n in ('operator.petsc','rhs.petsc')):
            raise ValueError('Reassembled first system differs from archived C system')
        if np.finfo(WIDE).nmant <= 52:
            raise ValueError('Extended accumulation unavailable')
        a, b, x = matrix(case/'operator.petsc'), vector(case/'rhs.petsc'), vector(root/'iterate.petsc')
        if b.shape != (924953,) or x.shape != b.shape or a.shape != (b.size,b.size):
            raise ValueError('Invalid first-system dimensions')
        measured = audit(a, a.astype(WIDE), b, x, read_layout(layout, b.size))
        row['independent'] = measured
        rhs = norm(b.astype(WIDE))
        threshold = max(policy['atol'], policy['rtol']*rhs)
        row.update(rhs_norm=rhs, threshold=threshold, relative=measured['wide_norm']/rhs)
        event, = row['linear']
        identity = ('step','newton','solve','attempt','pc_attempt','protocol_hash')
        if (tuple(int(event[k]) for k in identity[:-1]) != (1,1,1,1,1)
                or {f['name'] for f in row['blocks']} != BLOCKS
                or any(any(f[k] != event[k] for k in identity)
                       or not all(math.isfinite(float(f[k])) and float(f[k]) >= 0 for k in ('rms','constraint_max'))
                       for f in row['blocks'])):
            raise ValueError('First correction or field identity mismatch')
        row['production_ratio'] = audit_row(event, policy)
        if row['exit_code'] and not any('SNES did not converge: reason=-5' in line for line in lines):
            raise ValueError('Unrecognized solver failure after linear correction')
        if max(measured['wide_norm'], measured['fp64_csr_norm']) > threshold:
            raise ValueError('Returned iterate misses original saved system tolerance')
        row['first_correction'] = 'passed'
    except Exception as error:
        row.update(first_correction='failed', diagnosis=str(error))
        raise
    finally:
        save(root/'first.json', row)


if __name__ == '__main__':
    main()
