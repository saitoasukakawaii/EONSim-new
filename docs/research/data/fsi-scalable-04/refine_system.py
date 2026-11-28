"""Refine an archived PETSc real-double AIJ system and audit the returned FP64 iterate."""
import argparse
import csv
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import splu

DATA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATA / 'fsi-scalable-03'))
from inspect_system import vector

WIDE = np.longdouble
FIELDS = ('mesh', 'velocity', 'pressure', 'structure', 'RCR')


def finite(a):
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite input or arithmetic result')
    return a


def norm(a):
    return float(finite(np.sqrt(a @ a)))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def matrix(path):
    with path.open('rb') as f:
        kind, n, m, nz = map(int, np.fromfile(f, '>i4', 4))
        if kind != 1211216 or n != m or n <= 0 or nz <= 0:
            raise ValueError('Expected one square AIJ system')
        lengths = np.fromfile(f, '>i4', n)
        cols = np.fromfile(f, '>i4', nz).astype(np.int32)
        values = np.fromfile(f, '>f8', nz).astype(float)
        if (len(lengths) != n or np.any(lengths < 0) or lengths.sum() != nz
                or len(values) != nz or len(cols) != nz or cols.min() < 0
                or cols.max() >= n or f.read(1)):
            raise ValueError('Inconsistent AIJ snapshot')
    a = csr_matrix((finite(values), cols, np.r_[0, lengths.cumsum()]), shape=(n, m))
    a.eliminate_zeros()
    if not a.has_canonical_format and not a.sorted_indices().has_canonical_format:
        raise ValueError('Duplicate assembled AIJ entry')
    return a


def read_layout(directory, n):
    field = np.full(n, -1, dtype=np.int8)
    owner = np.full(n, -1, dtype=np.int32)
    interface = np.zeros(n, dtype=bool)
    with (directory / 'port.csv').open() as f:
        port, = csv.DictReader(f)
    port_row = int(port['pressure_row'])
    if int(port['rows']) != n or not 0 <= port_row < n:
        raise ValueError('Wrong port layout')
    pieces = sorted(directory.glob('rows-*.csv'))
    ranks = {int(p.stem.split('-')[1]) for p in pieces}
    if ranks != set(range(len(pieces))):
        raise ValueError('Missing owner shard')
    for p in pieces:
        rank = int(p.stem.split('-')[1])
        with p.open() as f:
            for row in csv.DictReader(f):
                i = int(row['row'])
                if not 0 <= i < n or owner[i] != -1:
                    raise ValueError('Invalid or duplicate owner row')
                owner[i] = rank
                field[i] = FIELDS.index(row['field'])
                interface[i] = bool(int(row['interface']))
    if (owner < 0).any() or field[port_row] != FIELDS.index('pressure'):
        raise ValueError('Missing row or inconsistent port field')
    field[port_row] = FIELDS.index('RCR')
    return field, owner, interface


def solve_factors(a, equilibrate):
    """Power-of-two row and column scaling, including all constraint and port rows."""
    def inverse_power(maxima):
        finite(maxima)
        if np.any(maxima <= 0):
            raise ValueError('Empty or zero equation/unknown in factorization')
        _, exponent = np.frexp(maxima)
        return finite(np.ldexp(np.ones_like(maxima), -exponent))

    row_scale = np.ones(a.shape[0])
    col_scale = np.ones(a.shape[1])
    scaled = a
    if equilibrate:
        row_scale = inverse_power(abs(a).max(axis=1).toarray().ravel())
        scaled = a.multiply(row_scale[:, None]).tocsr()
        col_scale = inverse_power(abs(scaled).max(axis=0).toarray().ravel())
        scaled = scaled.multiply(col_scale).tocsr()
        finite(scaled.data)
        if np.any(scaled.data == 0):
            raise ValueError('Scaling lost a nonzero entry')
    lu = splu(scaled.tocsc(), permc_spec='COLAMD', options={'Equil': False})

    def solve(r):
        return finite(col_scale * lu.solve(finite(row_scale * r.astype(float))))

    return solve, dict(row_scale=[row_scale.min(), row_scale.max()],
                       col_scale=[col_scale.min(), col_scale.max()], factor_nnz=int(lu.nnz))


def audit(a, aw, rhs, x, layout):
    if x.dtype != np.float64:
        raise ValueError('Production audit requires the written FP64 vector')
    xw = x.astype(WIDE)
    residual = finite(rhs.astype(WIDE) - aw @ xw)
    ordinary = finite(rhs - a @ x)
    field, owner, interface = layout
    b_abs = np.abs(rhs.astype(WIDE))
    absolute = abs(aw)
    den = finite(b_abs + absolute @ abs(xw))
    nonzero = den != 0
    if np.any(residual[~nonzero] != 0):
        raise ValueError('Nonzero numerator / zero component denominator')
    ainfty = np.asarray(absolute.sum(axis=1)).max()
    denom = finite(ainfty * abs(xw).max() + b_abs.max())
    max_r = abs(residual).max()
    if denom == 0 and max_r != 0:
        raise ValueError('Nonzero numerator / zero global denominator')
    result = dict(fp64_csr_norm=norm(ordinary), wide_norm=norm(residual),
                  eta_inf=float(max_r/denom) if denom else 0.0,
                  eta_component=float(np.max(abs(residual[nonzero])/den[nonzero])) if nonzero.any() else 0.0,
                  fields={}, worst_owner_rows=[])
    for k, name in enumerate(FIELDS):
        ids = field == k
        result['fields'][name] = dict(rows=int(ids.sum()), wide_norm=norm(residual[ids]),
                                      fp64_norm=norm(ordinary[ids]))
    for i in np.argsort(-abs(residual))[:8]:
        start, end = a.indptr[i:i+2]
        cols = a.indices[start:end]
        vals = a.data[start:end]
        terms = [Fraction(float(v)) * Fraction(float(x[j])) for v, j in zip(vals, cols)]
        pos = sum(t for t in terms if t > 0)
        neg = sum(t for t in terms if t < 0)
        exact = Fraction(float(rhs[i])) - pos - neg
        result['worst_owner_rows'].append(dict(
            row=int(i), owner=int(owner[i]), field=FIELDS[field[i]], interface=bool(interface[i]),
            identity_equation=bool(len(cols) == 1 and cols[0] == i and vals[0] == 1),
            row_abs_sum=float(abs(vals).sum(dtype=WIDE)), rhs=float(rhs[i]),
            positive_products=float(pos), negative_products=float(neg),
            exact_dyadic_residual=float(exact), wide_residual=float(residual[i]),
            fp64_residual=float(ordinary[i])))
    return result


def refine(aw, rhs, seed, solve, steps, tolerance):
    """Every correction starts from the last rounded FP64 iterate, with a best-iterate guard."""
    if not 0 <= steps <= 5:
        raise ValueError('Expected zero to five refinement steps')
    rhsw = rhs.astype(WIDE)
    x = finite(seed.copy())
    best = x.copy()
    best_norm = norm(finite(rhsw - aw @ x.astype(WIDE)))
    stale = 0
    records = []
    stop = 'budget'
    for step in range(1, steps + 1):
        t = time.perf_counter()
        residual = finite(rhsw - aw @ x.astype(WIDE))
        if norm(residual) <= tolerance:
            stop = 'wide target on stored FP64 iterate'
            break
        dx = finite(solve(residual))
        temporary = finite(x.astype(WIDE) + dx.astype(WIDE))
        new = finite(temporary.astype(float))
        changed = int(np.count_nonzero(new != x))
        stored_norm = norm(finite(rhsw - aw @ new.astype(WIDE)))
        records.append(dict(step=step, before=norm(residual), dx_norm=norm(dx),
                            temporary_wide_norm=norm(finite(rhsw - aw @ temporary)),
                            stored_fp64_wide_norm=stored_norm, changed_entries=changed,
                            seconds=time.perf_counter()-t))
        if stored_norm < best_norm:
            best_norm = stored_norm
            best = new.copy()
            stale = 0
        else:
            stale += 1
        x = new
        if not changed or stale >= 2:
            stop = 'no representable update' if not changed else 'two non-improving updates'
            break
    return best, records, stop


def run(args, report):
    if np.finfo(WIDE).nmant <= 52:
        raise ValueError('Extended precision unavailable')
    files = [args.directory / f for f in ('operator.petsc', 'rhs.petsc', 'iterate.petsc')]
    index = json.loads((DATA / 'fsi-scalable-03/log-index.json').read_text())
    raw = files + sorted(args.layout.glob('*.csv')) + [args.directory / 'solve.log']
    report['sha256'] = {}
    for p in raw:
        key = '$HOME/' + str(p.resolve().relative_to(Path.home())).replace(os.sep, '/')
        digest = sha(p)
        if index[key]['sha256'] != digest:
            raise ValueError(f'Archived SHA mismatch: {p}')
        report['sha256'][key] = digest
    report['original_monitor_lines'] = [
        line.strip() for line in raw[-1].read_text(errors='replace').splitlines()
        if re.search(r'^\s*\d+ KSP (?:unpreconditioned |preconditioned |)resid|true resid|linear_residual', line, re.I)
    ][-8:]
    a = matrix(files[0])
    rhs, seed = [finite(vector(path)) for path in files[1:]]
    if seed.shape != rhs.shape or len(rhs) != a.shape[0]:
        raise ValueError('Snapshot dimensions differ')
    layout = read_layout(args.layout, len(rhs))
    aw = a.astype(WIDE)
    tol = max(1e-23, 1e-10*norm(rhs.astype(WIDE)))
    report.update(rows=len(rhs), tolerance=tol, mantissa_bits=int(np.finfo(WIDE).nmant+1),
                  initial=audit(a, aw, rhs, seed, layout))
    x = seed
    if args.steps:
        t = time.perf_counter()
        solve, info = solve_factors(a, args.scaling == 'power2')
        report['factor'] = dict(info, seconds=time.perf_counter()-t, ordering='COLAMD')
        scaled_x = solve(rhs)
        report['direct'] = audit(a, aw, rhs, scaled_x, layout)
        if report['direct']['wide_norm'] < report['initial']['wide_norm']:
            x = scaled_x
            report['seed'] = 'direct'
        else:
            report['seed'] = 'archive'
        x, report['steps'], report['stop'] = refine(aw, rhs, x, solve, args.steps, tol)
    if args.write_vector:
        with args.write_vector.open('xb') as f:
            np.asarray([1211214, len(x)], dtype='>i4').tofile(f)
            x.astype('>f8').tofile(f)
        x = vector(args.write_vector)
        report['returned_vector_sha256'] = sha(args.write_vector)
    report['returned'] = audit(a, aw, rhs, x, layout)
    return max(report['returned'][k] for k in ('wide_norm', 'fp64_csr_norm')) <= tol


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', type=Path)
    cli.add_argument('--layout', required=True, type=Path)
    cli.add_argument('--output', required=True, type=Path)
    cli.add_argument('--write-vector', type=Path)
    cli.add_argument('--steps', type=int, choices=range(6), default=5)
    cli.add_argument('--scaling', choices=('power2', 'none'), default='power2')
    args = cli.parse_args()
    report = dict(options=sys.argv[1:], slurm_job=os.environ.get('SLURM_JOB_ID'),
                  python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                  script_sha256=sha(Path(__file__)), status='ERROR')
    start = time.perf_counter()
    try:
        passed = run(args, report)
        report['status'] = 'PASS_OFFLINE' if passed else 'FAILED_ORIGINAL_RESIDUAL'
        return 0 if passed else 3
    except Exception as err:
        report['error'] = f'{type(err).__name__}: {err}'
        return 2
    finally:
        report['seconds'] = time.perf_counter() - start
        with args.output.open('x') as f:
            json.dump(report, f, indent=2, allow_nan=False)
            f.write('\n')


if __name__ == '__main__':
    sys.exit(main())
