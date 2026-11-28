"""Apply the captured C correction to both the job 409 matrix and its reassembly."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
from scipy.sparse import csr_matrix

from tube_protocol import select

DATA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATA/'fsi-scalable-04'))
from refine_system import FIELDS, WIDE, read_layout, sha, vector


def raw_matrix(p):
    with p.open('rb') as s:
        kind, rows, cols, nnz = map(int,np.fromfile(s,'>i4',4))
    if (kind,rows,cols) != (1211216,924953,924953) or p.stat().st_size != 16+4*rows+12*nnz:
        raise ValueError('Invalid C snapshot format')
    sizes = np.memmap(p,mode='r',dtype='>i4',offset=16,shape=rows)
    if np.any(sizes<=0) or sizes.sum()!=nnz:
        raise ValueError('Invalid C row lengths')
    ind = np.memmap(p,mode='r',dtype='>i4',offset=16+4*rows,shape=nnz)
    val = np.memmap(p,mode='r',dtype='>f8',offset=16+4*(rows+nnz),shape=nnz)
    return np.r_[0,sizes.cumsum(dtype=np.int64)],ind,val


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('probe',type=Path)
    cli.add_argument('output',type=Path)
    args = cli.parse_args()
    base = Path.home()/'workspace/fsi-scalable-03-runs'
    archive = base/'C-first-64'
    case = args.probe.resolve(strict=True)
    runs = json.loads((case/'first.json').read_text())
    old = json.loads((DATA/'fsi-scalable-03/log-index.json').read_text())
    for n in ('rhs.petsc','operator.petsc'):
        key = '$HOME/workspace/fsi-scalable-03-runs/C-first-64/'+n
        if sha(archive/n) != old[key]['sha256'] or sha(case/n) != runs['artifacts'][n]:
            raise ValueError('Captured operator or RHS changed')
    if sha(case/'rhs.petsc') != sha(archive/'rhs.petsc') or sha(case/'iterate.petsc') != runs['artifacts']['iterate.petsc']:
        raise ValueError('RHS or returned iterate differs')
    if np.finfo(WIDE).nmant<=52:
        raise ValueError('Extended accumulation unavailable')
    b = vector(archive/'rhs.petsc')
    x = vector(case/'iterate.petsc')
    if b.shape!=x.shape or not np.isfinite(x).all() or not np.isfinite(b).all():
        raise ValueError('Invalid vector')
    ptr,ind,val = raw_matrix(archive/'operator.petsc')
    other,other_ind,other_val = raw_matrix(case/'operator.petsc')
    if not np.array_equal(ptr,other):
        raise ValueError('Row structure differs')
    field,_,_ = read_layout(base/'C-layout',len(b))
    bw,xw = b.astype(WIDE),x.astype(WIDE)
    # archived, reassembled, and their action difference, in the same promoted arithmetic
    r = np.zeros((3,len(b)),dtype=WIDE)
    fp = np.zeros((2,len(b)))
    backward = np.zeros(2)
    changed = changed_rows = 0
    abs_max = rel_max = 0.
    for i in range(0,len(b),4096):
        j = min(i+4096,len(b))
        s = slice(ptr[i],ptr[j])
        if not np.array_equal(ind[s],other_ind[s]):
            raise ValueError('Column identity differs')
        cols = ind[s].astype(np.int32)
        if cols.min()<0 or cols.max()>=len(b):
            raise ValueError('Invalid column')
        offsets = (ptr[i:j+1]-ptr[i]).astype(np.int32)
        a,z = val[s].astype(float),other_val[s].astype(float)
        diff = np.abs(a-z)
        if not np.isfinite(diff).all():
            raise ValueError('Nonfinite matrix')
        changed += int(np.count_nonzero(diff))
        changed_rows += int(np.count_nonzero(np.add.reduceat(diff>0,offsets[:-1],dtype=np.int64)))
        abs_max = max(abs_max,float(diff.max()))
        scale = np.maximum(abs(a),abs(z))
        rel_max = max(rel_max,float(np.divide(diff,scale,out=np.zeros_like(scale),where=scale!=0).max()))
        for q,values in enumerate((a,z)):
            mat = csr_matrix((values,cols,offsets),shape=(j-i,len(b)))
            fp[q,i:j] = b[i:j]-mat@x
            wide = mat.astype(WIDE)
            residual = bw[i:j]-wide@xw
            r[q,i:j] = residual
            den = abs(wide)@abs(xw) + abs(bw[i:j])
            if np.any((den==0)&(residual!=0)):
                raise ValueError('Invalid zero component denominator')
            backward[q] = max(backward[q],float(np.divide(abs(residual),den,out=np.zeros_like(den),where=den!=0).max()))
        r[2,i:j] = r[1,i:j]-r[0,i:j]
    policy = select('CALIBRATED-v2','fixed-1e-8')
    if policy['hash']!=runs['protocol_hash']:
        raise ValueError('Reproduce with the protocol at the run commit')
    limit = max(policy['atol'],policy['rtol']*float(np.sqrt(bw@bw)))
    result = dict(archive_job=409, job=runs['job'], audit_job=os.getenv('SLURM_JOB_ID'), receipt_sha256=sha(case/'first.json'),
                  protocol_hash=policy['hash'], profile=policy['profile'], limit=limit,
                  artifacts=runs['artifacts'], archive_sha256=sha(archive/'operator.petsc'),
                  same_csr_structure=True, differing_coefficients=changed, affected_rows=changed_rows,
                  maximum_abs_coefficient_difference=abs_max, maximum_relative_coefficient_difference=rel_max)
    for q,n in enumerate(('archive','reassembled','difference_of_actions')):
        row = dict(norm=float(np.sqrt(r[q]@r[q])), fields={name:float(np.sqrt(r[q,field==k]@r[q,field==k]))
                                                            for k,name in enumerate(FIELDS)})
        if q<2:
            row.update(fp64_csr_norm=float(np.linalg.norm(fp[q])),max_componentwise_backward_error=float(backward[q]))
            row['passes_saved_equation'] = max(row['norm'],row['fp64_csr_norm'])<=limit
        result[n] = row
    if not math.isfinite(limit):
        raise ValueError('Invalid threshold')
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
