"""Assemble captured native local contributions using the FSILS global node map."""
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import ArpackNoConvergence, eigsh, norm


def read_system(stage, iteration):
    def read(stream, dtype, count):
        v = np.fromfile(stream,dtype,count=count)
        if v.size!=count or not np.isfinite(v).all():
            raise ValueError('Incomplete or nonfinite native snapshot')
        return v

    rows, cols, values, scaled = [], [], [], []
    for rank in range(32):
        stem = f'ms-{iteration}-{rank:03}'
        with (stage/(stem+'.raw')).open('rb') as f:
            n,g,nz,owned,dof = map(int,read(f,'<i4',5))
            if not 0 < owned <= n <= g or dof!=3:
                raise ValueError('Unexpected FSILS dimensions')
            ids, perm = read(f,'<i4',n)-1,read(f,'<i4',n)-1
            if set(perm)!=set(range(n)) or min(ids)<0 or max(ids)>=g or len(set(ids))!=n:
                raise ValueError('Invalid native global-to-local mapping')
            ptr, col = read(f,'<i4',n+1)-1,read(f,'<i4',nz)-1
            if ptr[0]!=0 or ptr[-1]!=nz or min(np.diff(ptr))<1 or min(col)<0 or max(col)>=n:
                raise ValueError('Invalid native CSR')
            mask=read(f,'<f8',n*3).reshape(n,3)
            b=read(f,'<f8',n*3).reshape(n,3)
            v=read(f,'<f8',nz*9)
            # Shared Dirichlet face weights are communicated before this
            # product and may exceed one. PRECONDRCS normalizes after summing.
            if f.read(1) or np.any(mask<0):
                raise ValueError('Invalid boundary mask or trailing bytes')
        with (stage/(stem+'.returned')).open('rb') as f:
            steps, = read(f,'<i4',1)
            start,end = read(f,'<f8',2)
            x=read(f,'<f8',n*3).reshape(n,3)
            w=read(f,'<f8',nz*9)
            if f.read(1):
                raise ValueError('Trailing bytes in result')
        if rank==0:
            global_nodes=g
            rhs,solution,mask_sum,mask_votes=np.zeros((4,g,3))
            count=np.zeros(g,dtype=int)
            owner=np.zeros(g,dtype=int)
            copies=[]
            native=dict(iterations=int(steps),initial_norm=float(start),final_norm=float(end))
        if g!=global_nodes or steps!=native['iterations']:
            raise ValueError('Inconsistent rank dimensions or convergence status')
        keep=perm<owned
        np.add.at(owner,ids[keep],1)
        np.add.at(count,ids,1)
        np.add.at(mask_sum,ids,mask)
        np.add.at(mask_votes,ids,mask>0.5)
        rhs[ids[keep]]=b[keep]
        solution[ids[keep]]=x[keep]
        copies.append((ids,b,x))
        row=3*np.repeat(ids,np.diff(ptr)); column=3*ids[col]
        rows.append(np.repeat(row[:,None]+np.arange(3),3,axis=1).ravel())
        cols.append(np.tile(column[:,None]+np.arange(3),(1,3)).ravel())
        values.append(v); scaled.append(w)
    if not np.all(owner==1):
        raise ValueError('FSILS owner coverage differs from global nodes')
    # Native COMMU(R) precedes FSILS_SOLVE. Sum element contributions but
    # take each already-communicated RHS and returned vector only once.
    ghost = dict(rhs=max(float(np.abs(b-rhs[ids]).max()) for ids,b,x in copies),
                 solution=max(float(np.abs(x-solution[ids]).max()) for ids,b,x in copies))
    ij = np.concatenate(rows),np.concatenate(cols)
    a,p=(coo_matrix((np.concatenate(v),ij),shape=(3*g,3*g)).tocsr() for v in (values,scaled))
    free=(mask_sum.ravel()>0.5)  # Same post-MPI normalization as PRECONDRCS.
    mixed=(mask_votes!=0)&(mask_votes!=count[:,None])
    return a,p,rhs.ravel(),solution.ravel(),free,native,ghost,int(mixed.sum())


def compare(stage):
    stage=Path(stage)
    systems=[]
    result={}
    for i in (1,4):
        full,scaled,b,x,free,native,ghost,mixed=read_system(stage,i)
        a=full[free][:,free]
        p=scaled[free][:,free]
        if not a.shape[0] or norm(a)==0 or norm(p)==0:
            raise ValueError('Empty constrained native operator')
        # A returned correction can contain constrained components; measure
        # actual free equations on the full returned vector.
        r=(b-full@x)[free]
        denom=np.abs(b[free])+np.abs(full[free])@np.abs(x)
        if np.any((denom==0)&(r!=0)):
            raise ValueError('Zero component denominator with nonzero residual')
        diagonal=a.diagonal()
        row=dict(native=native,components=len(b),free_components=int(free.sum()),
                 constrained_components=int((~free).sum()),mixed_rank_masks=mixed,ghost_maximum_difference=ghost,
                 unscaled_rhs_norm=float(np.linalg.norm(b[free])),unscaled_residual_norm=float(np.linalg.norm(r)),
                 constrained_solution_max=float(np.abs(x[~free]).max()),matrix_frobenius=float(norm(a)),
                 free_diagonal_range=[float(diagonal.min()),float(diagonal.max())],
                 symmetry_defect=float(norm(a-a.T)/norm(a)),scaled_symmetry_defect=float(norm(p-p.T)/norm(p)),
                 componentwise_backward_error=float(np.divide(np.abs(r),denom,out=np.zeros_like(r),where=denom!=0).max()))
        row['original_relative_residual']=row['unscaled_residual_norm']/row['unscaled_rhs_norm']
        if np.all(diagonal>0):
            scale=diags(1/np.sqrt(diagonal))
            symmetric=scale@((a+a.T)*.5)@scale
            # A Rayleigh witness is sufficient to demonstrate a negative
            # direction. Positive estimates do not certify positive definiteness.
            try:
                vals,vec=eigsh(symmetric,k=1,which='SA',tol=1e-5,maxiter=500,
                               v0=np.random.default_rng(467).normal(size=a.shape[0]))
            except ArpackNoConvergence:
                row['ritz_status']='unresolved within 500 iterations'
            else:
                row['jacobi_scaled_min_ritz']=float(vals[0])
                row['ritz_residual']=float(np.linalg.norm(symmetric@vec[:,0]-vals[0]*vec[:,0]))
        systems.append((free,a,p,b[free],x[free]))
        result[str(i)]=row
    f,a,p,b,x=systems[0]; g,z,q,c,y=systems[1]
    if not np.array_equal(f,g):
        raise ValueError('MS free-component set changed within the time step')
    result['first_to_fourth']=dict(matrix_relative_frobenius=float(norm(z-a)/norm(a)),
                                   scaled_matrix_relative_frobenius=float(norm(q-p)/norm(p)),
                                   rhs_norm_ratio=float(np.linalg.norm(c)/np.linalg.norm(b)),
                                   rhs_difference_norm=float(np.linalg.norm(c-b)),
                                   returned_correction_norm_ratio=float(np.linalg.norm(y)/np.linalg.norm(x)))
    return result


if __name__=='__main__':
    import argparse
    import json
    from native_mesh import digest,save
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('capture',type=Path)
    cli.add_argument('output',type=Path)
    args=cli.parse_args()
    source=args.capture/'ms-snapshot.json'
    receipt=json.loads(source.read_text())
    expected={f'ms-{i}-{rank:03}.{suffix}' for i in (1,4) for rank in range(32)
              for suffix in ('raw','returned')}
    if set(receipt['artifacts'])!=expected or any(digest(args.capture/f)!=v for f,v in receipt['artifacts'].items()):
        raise ValueError('Changed or missing native matrix, RHS or result')
    save(args.output,dict(capture_sha256=digest(source),systems=compare(args.capture)))
