"""Conditionally round fine columns against frozen coarse FP64 coordinates on saved B."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import lsmr

from refine_system import DATA, FIELDS, WIDE, audit, finite, matrix, norm, read_layout, sha, vector


def conditional_round(a, b, x, layout, target):
    """Normalize columns for LSMR but minimize the *unweighted* full original equations."""
    if np.finfo(WIDE).nmant <= 52 or x.dtype != np.float64:
        raise ValueError('An FP64 iterate and extended residual arithmetic are required')
    aw = a.astype(WIDE)
    bw = b.astype(WIDE)
    c = a.tocsc()
    col_norm = np.sqrt(np.asarray(c.power(2).sum(axis=0)).ravel())
    if not np.all(finite(col_norm) > 0):
        raise ValueError('Zero or unrepresentable column norm')

    # MatZeroRows(A, ..., 1) replaces essential equations with unit rows.
    # Keep their actual FP64 coordinates fixed in each conditional solve.
    lengths = np.diff(a.indptr)
    unit = np.zeros(len(x), dtype=bool)
    ids = np.flatnonzero(lengths == 1)
    starts = a.indptr[ids]
    unit[ids] = (a.indices[starts] == ids) & (a.data[starts] == 1)

    free = np.flatnonzero(~unit)
    widths = np.maximum(np.nextafter(x, np.inf).astype(WIDE) - x,
                        x.astype(WIDE) - np.nextafter(x, -np.inf))
    influence = finite(col_norm.astype(WIDE) * widths)
    order = free[np.argsort(influence[free], kind='stable')]
    # Independent uniform rounding predicts this energy; it *only* selects the
    # subspace. Correlations and every actual stored vector are checked explicitly.
    energy = np.cumsum(influence[order]**2 / 12, dtype=WIDE)
    best = x.copy()
    best[unit] = b[unit]
    fixed_seed_changes = int(np.count_nonzero(best != x))
    records = []
    counts = set()
    for ratio in (2.0, 1.0, 0.5, 0.125):
        count = int(np.searchsorted(energy, WIDE(ratio*target)**2, side='right'))
        if not count or count in counts:
            continue
        counts.add(count)
        start = time.perf_counter()
        cols = np.sort(order[:count])
        r = finite(bw - aw @ best.astype(WIDE))
        original = norm(r)
        if original <= target and norm(finite(b - a @ best)) <= target:
            break
        if original == 0:
            break
        scaled = c[:, cols].multiply(1 / col_norm[cols]).tocsr()
        result = lsmr(scaled, (r / original).astype(float), atol=1e-12, btol=1e-12,
                      maxiter=160, conlim=1e12)
        dx = finite(result[0].astype(WIDE) * original / col_norm[cols])
        temporary = best.astype(WIDE)
        temporary[cols] += dx
        trial = finite(temporary.astype(float))
        actual = norm(finite(bw - aw @ trial.astype(WIDE)))
        changed = trial != best
        records.append(dict(rounding_budget_relative=ratio, free_columns=count,
                            unit_rows_frozen=int(unit.sum()), projected_seed_entries=fixed_seed_changes,
                            before=original,
                            lsmr_reason=int(result[1]), lsmr_iterations=int(result[2]),
                            relaxed_raw_norm=norm(finite(bw-aw @ temporary)),
                            stored_norm=actual, stored_csr_fp64_norm=norm(finite(b-a @ trial)),
                            max_abs_move=float(np.max(np.abs(dx))),
                            changed_by_field={f:int(np.count_nonzero(changed & (layout[0] == k)))
                                              for k, f in enumerate(FIELDS)},
                            accepted=actual < original, seconds=time.perf_counter()-start))
        if actual < original:
            best = trial
    return best, records


def self_check():
    # With the coarse coordinate frozen, adjusting the much finer second coordinate
    # cancels most of the first-row defect at the cost of a measured second-row defect.
    a = csr_matrix([[3., 2.**-25, 0.], [0., 2.**-35, 0.], [0., 0., 1.]])
    b = np.array([1., 0., 2.])
    x = np.array([1/3, 0., 2.])
    layout = (np.zeros(3, dtype=int),)
    stored, history = conditional_round(a, b, x, layout, 1e-18)
    observed = norm(b.astype(WIDE)-a.astype(WIDE) @ stored.astype(WIDE))
    if not history or observed > 1e-18 or stored[0] != x[0] or stored[2] != 2.:
        raise ValueError('Conditional rounding or fixed-coordinate regression')


def run(args, report):
    self_check()
    evidence = json.loads(args.polish.read_text())
    if evidence['status'] != 'FAILED_ORIGINAL_RESIDUAL' or sha(args.seed) != evidence['written_sha256']:
        raise ValueError('Expected the failed, written coordinate-polish iterate')
    original = [args.directory/'operator.petsc', args.directory/'rhs.petsc',
                *sorted(args.layout.glob('*.csv'))]
    index = json.loads((DATA/'fsi-scalable-03/log-index.json').read_text())
    hashes = {}
    for path in original:
        key = '$HOME/' + path.resolve().relative_to(Path.home()).as_posix()
        digest = sha(path)
        if digest != index[key]['sha256'] or digest != evidence['original_sha256'][key]:
            raise ValueError(f'Changed original input {path}')
        hashes[key] = digest
    if set(hashes) != set(evidence['original_sha256']):
        raise ValueError('Incomplete parent input group')
    a = matrix(original[0])
    b = finite(vector(original[1]))
    x = finite(vector(args.seed))
    if a.shape != (len(b), len(x)):
        raise ValueError('Incompatible saved vector')
    layout = read_layout(args.layout, len(b))
    target = max(1e-23, 1e-10*norm(b.astype(WIDE)))
    report.update(original_sha256=hashes, seed_sha256=sha(args.seed), polish_sha256=sha(args.polish),
                  tolerance=target, mantissa_bits=int(np.finfo(WIDE).nmant+1),
                  initial=audit(a, a.astype(WIDE), b, x, layout))
    best, report['stages'] = conditional_round(a, b, x, layout, target)
    with args.write_vector.open('xb') as f:
        np.asarray([1211214, len(best)], dtype='>i4').tofile(f)
        best.astype('>f8').tofile(f)
    returned = vector(args.write_vector)
    if not np.array_equal(returned, best):
        raise ValueError('Wrong persisted vector')
    report['written_sha256'] = sha(args.write_vector)
    report['returned'] = audit(a, a.astype(WIDE), b, returned, layout)
    return max(report['returned'][k] for k in ('wide_norm','fp64_csr_norm')) <= target


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', type=Path)
    for name in ('seed', 'polish', 'layout', 'output', 'write-vector'):
        cli.add_argument('--'+name, type=Path, required=True)
    args = cli.parse_args()
    report = dict(status='ERROR', script_sha256=sha(Path(__file__)), options=sys.argv[1:],
                  slurm_job=os.environ.get('SLURM_JOB_ID'))
    start = time.perf_counter()
    try:
        passed = run(args, report)
        report['status'] = 'PASS_OFFLINE' if passed else 'FAILED_ORIGINAL_RESIDUAL'
        return 0 if passed else 3
    except Exception as err:
        report['error'] = f'{type(err).__name__}: {err}'
        return 2
    finally:
        report['seconds'] = time.perf_counter()-start
        with args.output.open('x') as f:
            json.dump(report, f, indent=2, allow_nan=False)
            f.write('\n')


if __name__ == '__main__':
    sys.exit(main())
