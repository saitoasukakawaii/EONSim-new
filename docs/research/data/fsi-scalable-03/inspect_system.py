"""Audit a saved PETSc real-double, 32-bit-index AIJ system without changing the solve."""
import argparse
import csv
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
    cli.add_argument('--layout',type=Path,help='owner row shards reconstructed by export_layout')
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
    residual = None
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
    if args.layout:
        with (args.layout/'port.csv').open() as stream:
            port, = csv.DictReader(stream)
        port_row = int(port['pressure_row'])
        if int(port['rows'])!=rows or not 0<=port_row<rows:
            raise ValueError('Saved matrix and reconstructed port layout differ')
        groups = {name:[] for name in ('mesh','pressure','structure','velocity')}
        seen = np.zeros(rows,dtype=bool)
        pieces = sorted(args.layout.glob('rows-*.csv'))
        for piece in pieces:
            with piece.open() as stream:
                for entry in csv.DictReader(stream):
                    i = int(entry['row'])
                    if not 0<=i<rows or seen[i]:
                        raise ValueError('Duplicate or invalid owned row')
                    seen[i] = True
                    groups[entry['field']].append(i)
        if not seen.all() or port_row not in groups['pressure']:
            raise ValueError('Incomplete physical row coverage or port is not a pressure row')
        report['fields'] = {}
        for name, ids in groups.items():
            field = dict(rows=len(ids),rhs_norm=float(np.linalg.norm(rhs[ids])))
            if residual is not None:
                field['extended_residual_norm'] = float(np.sqrt(residual[ids]@residual[ids]))
            report['fields'][name] = field
        report['port'] = dict(port,rhs=float(rhs[port_row]),diagonal=float(mat[port_row,port_row]))
        report['layout_shards'] = len(pieces)
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
