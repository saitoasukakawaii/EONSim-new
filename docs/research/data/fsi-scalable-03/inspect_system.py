"""Audit a saved PETSc real-double, 32-bit-index AIJ system without changing the solve."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix


def vector(path):
    with path.open('rb') as stream:
        kind, length = np.fromfile(stream, dtype='>i4', count=2)
        if kind != 1211214 or path.stat().st_size != 8 + 8*int(length):
            raise ValueError(f'Invalid PETSc vector {path}')
        return np.fromfile(stream, dtype='>f8').astype(np.float64)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', type=Path)
    args = cli.parse_args()
    root = args.directory
    with (root/'operator.petsc').open('rb') as stream:
        kind, rows, cols, nnz = map(int,np.fromfile(stream, dtype='>i4', count=4))
        if kind != 1211216 or rows != cols or nnz <= 0:
            raise ValueError('Expected one square AIJ matrix')
        sizes = np.fromfile(stream, dtype='>i4', count=rows)
        indices = np.fromfile(stream, dtype='>i4', count=nnz).astype(np.int32)
        values = np.fromfile(stream, dtype='>f8', count=nnz).astype(np.float64)
        if (sizes.sum()!=nnz or len(values)!=nnz or stream.read(1) or indices.min()<0
                or indices.max()>=cols or not np.isfinite(values).all()):
            raise ValueError('Invalid matrix or multiple snapshots')
    mat = csr_matrix((values,indices,np.r_[0,sizes.cumsum()]),shape=(rows,cols))
    rhs = vector(root/'rhs.petsc')
    if rhs.shape!=(rows,) or not np.isfinite(rhs).all():
        raise ValueError('Invalid right-hand side')
    target = max(1e-23,1e-10*np.linalg.norm(rhs))
    report = dict(rows=rows, nnz=nnz, rhs_nonzero=int(np.count_nonzero(rhs)),
                  rhs_norm=float(np.linalg.norm(rhs)), tolerance=float(target))
    if (root/'iterate.petsc').is_file():
        x = vector(root/'iterate.petsc')
        if x.shape!=(cols,) or not np.isfinite(x).all():
            raise ValueError('Invalid iterate')
        wide = np.longdouble
        if np.finfo(wide).nmant <= np.finfo(np.float64).nmant:
            raise ValueError('Extended precision unavailable')
        residual = mat.astype(wide) @ x.astype(wide) - rhs.astype(wide)
        scale = abs(mat) @ np.abs(np.spacing(x))
        report.update(extended_mantissa_bits=np.finfo(wide).nmant+1,
                      csr_residual=float(np.linalg.norm(mat@x-rhs)),
                      extended_residual=float(np.sqrt(residual@residual)),
                      one_ulp_envelope_norm=float(np.linalg.norm(scale)))
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
