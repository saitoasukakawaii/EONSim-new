"""Screen representable one-ULP column updates on a stored, refined B correction."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

from refine_system import DATA, FIELDS, WIDE, audit, finite, matrix, norm, read_layout, sha, vector


def sweep(a, x, residual, reverse):
    """Accept one adjacent double only when it decreases the extended residual objective.

    For a column c_j and r=b-Ax the change of ||r||² is d²||c_j||²-2d c_jᵀr.
    The opposite direction to c_jᵀr cannot decrease it, even when ULPs are asymmetric.
    Recheck the complete original system after each sweep to bound incremental drift.
    """
    touched = np.zeros(len(x), dtype=bool)
    order = reversed(range(len(x))) if reverse else range(len(x))
    for j in order:
        start, end = a.indptr[j:j+2]
        rows, col = a.indices[start:end], a.data[start:end]
        projection = col @ residual[rows]
        if not np.isfinite(projection):
            raise ArithmeticError('Nonfinite projected column residual')
        if not projection:
            continue
        other = np.nextafter(x[j], np.inf if projection > 0 else -np.inf)
        if not np.isfinite(other):
            continue
        move = WIDE(other) - WIDE(x[j])
        gain = move * (2 * projection - move * (col @ col))
        if not np.isfinite(gain):
            raise ArithmeticError('Nonfinite predicted decrease')
        if gain > 0:
            x[j] = other
            residual[rows] -= move * col
            touched[j] = True
    finite(residual)
    return touched


def polish(a, rhs, x, layout, sweeps, tolerance):
    if np.finfo(WIDE).nmant <= 52 or x.dtype != np.float64:
        raise ValueError('Requires original FP64 storage and an extended residual')
    finite(rhs)
    finite(x)
    finite(a.data)
    aw = a.astype(WIDE)
    columns = aw.tocsc()
    if not columns.has_canonical_format:
        raise ValueError('Noncanonical column indices')
    rhsw = rhs.astype(WIDE)
    best = x.copy()
    residual = finite(rhsw - aw @ best.astype(WIDE))
    records = []
    stop = 'sweep budget reached'
    for i in range(sweeps):
        start = time.perf_counter()
        before = norm(residual)
        if before <= tolerance and norm(finite(rhs - a @ best)) <= tolerance:
            stop = 'both original-system diagnostics within tolerance'
            break
        trial = best.copy()
        touched = sweep(columns, trial, residual.copy(), reverse=bool(i % 2))
        # Signed zero and representable writes are evaluated in original units.
        candidate = finite(rhsw - aw @ trial.astype(WIDE))
        after = norm(candidate)
        records.append(dict(sweep=i + 1, order='reverse' if i%2 else 'forward',
                            wide_before=before, wide_after=after,
                            fp64_after=norm(finite(rhs-a @ trial)),
                            changed_by_field={name: int(np.count_nonzero(touched & (layout[0] == k)))
                                              for k, name in enumerate(FIELDS)},
                            accepted=after < before, seconds=time.perf_counter()-start))
        if not touched.any() or after >= before:
            stop = 'no improving coordinate' if not touched.any() else 'global audit rejected sweep'
            break
        best, residual = trial, candidate
    return best, records, stop


def run(args, report):
    seed_receipt = json.loads(args.refinement.read_text())
    if seed_receipt['status'] != 'FAILED_ORIGINAL_RESIDUAL':
        raise ValueError('Requires a completed refinement failing the original residual')
    if sha(args.seed) != seed_receipt['returned_vector_sha256']:
        raise ValueError('Seed differs from the written refinement iterate')
    # Refuse a mixture of different trajectories or row orderings.
    raw = [args.directory / 'operator.petsc', args.directory / 'rhs.petsc',
           *sorted(args.layout.glob('*.csv'))]
    index = json.loads((DATA / 'fsi-scalable-03/log-index.json').read_text())
    report['original_sha256'] = {}
    for path in raw:
        key = '$HOME/' + path.resolve().relative_to(Path.home()).as_posix()
        actual = sha(path)
        if actual != index[key]['sha256'] or actual != seed_receipt['sha256'][key]:
            raise ValueError(f'Changed archived input {path}')
        report['original_sha256'][key] = actual
    a, rhs, x = matrix(raw[0]), finite(vector(raw[1])), finite(vector(args.seed))
    if a.shape != (len(rhs), len(x)):
        raise ValueError('Mismatch between matrix, RHS and seed dimensions')
    layout = read_layout(args.layout, len(rhs))
    tol = max(1e-23, 1e-10*norm(rhs.astype(WIDE)))
    report.update(tolerance=tol, effective_mantissa_bits=int(np.finfo(WIDE).nmant + 1),
                  seed_sha256=sha(args.seed), refinement_sha256=sha(args.refinement))
    report['initial'] = audit(a, a.astype(WIDE), rhs, x, layout)
    best, report['sweeps'], report['stop'] = polish(a, rhs, x, layout, args.sweeps, tol)
    with args.write_vector.open('xb') as stream:
        np.asarray([1211214, len(best)], dtype='>i4').tofile(stream)
        best.astype('>f8').tofile(stream)
    recorded = finite(vector(args.write_vector))
    if not np.array_equal(best, recorded):
        raise ValueError('Written iterate differs from the audited result')
    report['written_sha256'] = sha(args.write_vector)
    report['returned'] = audit(a, a.astype(WIDE), rhs, recorded, layout)
    return max(report['returned'][k] for k in ('wide_norm', 'fp64_csr_norm')) <= tol


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', type=Path)
    for name in ('layout', 'seed', 'refinement', 'write-vector', 'output'):
        cli.add_argument('--' + name, required=True, type=Path)
    cli.add_argument('--sweeps', type=int, choices=range(1, 6), default=5)
    args = cli.parse_args()
    report = dict(options=sys.argv[1:], status='ERROR', job=os.environ.get('SLURM_JOB_ID'),
                  script_sha256=sha(Path(__file__)))
    start = time.perf_counter()
    try:
        good = run(args, report)
        report['status'] = 'PASS_OFFLINE' if good else 'FAILED_ORIGINAL_RESIDUAL'
        return 0 if good else 3
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        return 2
    finally:
        report['seconds'] = time.perf_counter()-start
        with args.output.open('x') as stream:
            json.dump(report, stream, allow_nan=False, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    sys.exit(main())
