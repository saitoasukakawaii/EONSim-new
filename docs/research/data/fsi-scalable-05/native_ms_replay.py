"""Locate growth of the MS4 shared-copy error using the saved native equation."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

import numpy as np

from native_mesh import digest, save


def observe_cg(original, target):
    if digest(original) != 'a2e29df50799bcdec162aa8778293aabb3aa10118000f2561c500cc71c3ce7cf':
        raise ValueError('Unexpected native CGRAD.f')
    header, body = original.read_text().split('      SUBROUTINE CGRADV(', 1)
    declarations = '      nNo = lhs%nNo'
    initial = '      DO i=1, ls%mItr'
    updated = '         CALL OMPMULV(dof, nNo, err/errO, P)'
    if any(body.count(anchor) != 1 for anchor in (declarations, initial, updated)):
        raise ValueError('Unrecognized CGRADV recurrence')
    body = body.replace(declarations, '''      INTEGER trace_unit, probe_local
      COMMON /ms_trace/ trace_unit, probe_local
''' + declarations)
    for anchor, index in ((initial, '0'), (updated, 'i')):
        write = ('      IF (probe_local.GT.0) WRITE(trace_unit,*) ' + index
                 + ',\n     & X(3,probe_local),R(3,probe_local),P(3,probe_local),err')
        body = body.replace(anchor, write + '\n' + anchor if index == '0' else anchor + '\n' + write)
    target.write_text(header + '      SUBROUTINE CGRADV(' + body)


def summarize(stage):
    series = {}
    for rank in (21, 24):
        path = stage / f'trace-{rank:03}.dat'
        scales = np.loadtxt(path, max_rows=1)
        rows = np.loadtxt(path, skiprows=1)
        if rows.shape != (2001, 5) or not np.array_equal(rows[:, 0], np.arange(2001)):
            raise ValueError('Incomplete native CG trace')
        if not np.isfinite(rows).all() or not np.all(scales > 0):
            raise ValueError('Nonfinite native CG trace or invalid RCS scales')
        # X and R up to this point are the scaled native recurrence.
        series[rank] = (rows[:, 1] * scales[0], rows[:, 2], rows[:, 4]**0.5)
    copy, owner = series[21], series[24]
    if not np.array_equal(copy[2], owner[2]):
        raise ValueError('MPI owner norms differ between ranks')
    gap = np.abs(copy[0] - owner[0])
    rhs = np.abs(copy[1] - owner[1])

    def sample(i):
        return dict(iteration=int(i), owner=float(owner[0][i]), copy=float(copy[0][i]),
                    unscaled_x_gap=float(gap[i]), scaled_r_gap=float(rhs[i]),
                    native_r_norm=float(owner[2][i]))

    crossing = {}
    for limit in (0., 1e-15, 1e-12, 1e-9, 1e-6, 1e-3):
        indices = np.flatnonzero(gap > limit)
        crossing[str(limit)] = sample(indices[0]) if len(indices) else None
    best = int(np.argmin(owner[2]))
    return dict(global_node=7591, axis='z', owner_rank=24, copy_rank=21,
                initial=sample(0), minimum_native_norm=sample(best), final=sample(2000),
                first_unscaled_gap_exceeding=crossing)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    if not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0)) != 32:
        parser.error('the original decomposition requires 32 Slurm cores')
    capture, stage = args.capture.resolve(), args.stage.resolve()
    original_receipt = capture / 'ms-snapshot.json'
    receipt = json.loads(original_receipt.read_text())
    if digest(original_receipt) != '0f4caae6a841c0df607cbef076111042029bfc3eed137da640c9f0fb4a0d8796':
        raise ValueError('Unrecognized capture')
    for name, expected in receipt['artifacts'].items():
        if name.startswith('ms-4-') and digest(capture / name) != expected:
            raise ValueError('Changed native shard ' + name)
    stage.mkdir(parents=True)
    source = Path.home() / 'software/svFSI/svFSI'
    build = source / 'build/svFSI-build'
    library = build / 'lib/lib_simvascular_svfsils.a'
    if digest(library) != 'c31f311c8ecfe67893cc9134778742582e61dee3046c461c2bcea95fead70332':
        raise ValueError('Native FSILS archive changed')
    src = source / 'Code/Source/svFSILS'
    observe_cg(src / 'CGRAD.f', stage / 'CGRAD.f')
    app = build / 'Source/svFSI'
    flags_file, = (build / 'Source/svFSILS/CMakeFiles').glob('*.dir/flags.make')
    flags = [arg for line in flags_file.read_text().splitlines() if line.startswith('Fortran_')
             for arg in shlex.split(line.split('=', 1)[1])]
    link = shlex.split((app / 'CMakeFiles/svFSI.dir/link.txt').read_text())
    objects = []
    driver = Path(__file__).with_suffix('.f').resolve()
    for unit in (stage / 'CGRAD.f', driver):
        obj = stage / (unit.stem + '.o')
        subprocess.run(['/opt/software/gcc-11.3.0/bin/gfortran', *flags, '-I' + str(src),
                        '-c', unit, '-o', obj], cwd=stage, check=True)
        objects.append(str(obj))
    link = [arg for arg in link if not arg.endswith('.o')]
    link[link.index('-o')+1] = str(stage / 'replay')
    link[1:1] = objects
    subprocess.run(link, cwd=app, check=True)
    command = [*receipt['command'][:-2], str(stage / 'replay'), str(capture)]
    log = stage / 'replay.log'
    row = dict(job=os.environ['SLURM_JOB_ID'], capture=digest(original_receipt),
               native_cg=digest(src / 'CGRAD.f'), observed_cg=digest(stage / 'CGRAD.f'),
               driver=digest(driver), archive=digest(library), binary=digest(stage / 'replay'),
               command=command)
    try:
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
        with log.open('w') as f:
            subprocess.run(command, cwd=stage, env=env, stdout=f, stderr=subprocess.STDOUT,
                           timeout=120, check=True)
        row['trace'] = summarize(stage)
        row['files'] = {p.name:digest(p) for p in (log, *sorted(stage.glob('trace-*.dat')))}
        row['status'] = 'identical native matrix, initial/final norms and all returned components'
    finally:
        save(stage / 'replay.json', row)


if __name__ == '__main__':
    main()
