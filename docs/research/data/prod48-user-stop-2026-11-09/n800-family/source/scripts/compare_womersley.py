"""Cycle field differences on the finer nested tube mesh.

Same seed and polygon are mandatory. Only red-refined meshes are compared by
interpolation, so every fine element lies within a coarse element and the P1
mass norm of the difference is exact. No subtraction of scalar error norms.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from analyze_womersley import Study


def interpolation(coarse,fine):
    if np.array_equal(coarse.ids,fine.ids) and np.array_equal(coarse.xyz,fine.xyz) and np.array_equal(coarse.cells,fine.cells):
        return None
    points=coarse.points
    inverse=np.linalg.inv(np.transpose(points[:,1:]-points[:,:1],(0,2,1)))
    center=points.mean(axis=1)
    radius=float(np.max(np.linalg.norm(points-center[:,None,:],axis=2)))
    tree=cKDTree(center)
    _,nearest=tree.query(fine.xyz,k=min(24,len(center)))
    nearest=np.asarray(nearest).reshape(len(fine.ids),-1)
    indices=np.empty((len(fine.ids),4),dtype=np.int64)
    weights=np.empty((len(fine.ids),4))
    for i,x in enumerate(fine.xyz):
        for candidates in (nearest[i],None):
            if candidates is None:
                candidates=np.asarray(tree.query_ball_point(x,radius*(1+1e-12)),dtype=int)
            bary=np.einsum('cij,cj->ci',inverse[candidates],x-points[candidates,0])
            bary=np.column_stack((1-bary.sum(axis=1),bary))
            valid=np.flatnonzero((bary.min(axis=1)>=-1e-9)&(bary.max(axis=1)<=1+1e-9))
            if len(valid):
                q=valid[0]
                indices[i]=coarse.cells[candidates[q]]
                weights[i]=bary[q]
                break
        else:
            raise ValueError('Fine node lies outside the coarse polygon')
    # The independent affine patch must reproduce coordinates, including faces.
    reconstructed=np.einsum('na,nad->nd',weights,coarse.xyz[indices])
    if np.max(abs(reconstructed-fine.xyz))>1e-11:
        raise ValueError('Invalid interpolation affine patch')
    return indices,weights


def compare(a,b,cycle_a=None,cycle_b=None):
    da,db=a.definition,b.definition
    fixed=('seed','alpha','period','radius','length','density','viscosity','pressure_amplitude')
    if any(da[k]!=db[k] for k in fixed) or da['level']>db['level']:
        raise ValueError('Need the same seed/reference and a non-coarser target red mesh')
    ca=cycle_a or a.receipt['step']//da['steps_per_cycle']
    cb=cycle_b or b.receipt['step']//db['steps_per_cycle']
    m=math.gcd(da['phases'],db['phases'])
    if m<4:
        raise ValueError('Insufficient common phase samples')
    stencil=interpolation(a.mesh,b.mesh)
    n_a,n_b=da['steps_per_cycle'],db['steps_per_cycle']
    sums=dict(velocity=0.,pressure=0.);maximum=dict(velocity=0.,pressure=0.)
    for phase in range(1,m+1):
        x=a.state((ca-1)*n_a+phase*n_a//m)
        y=b.state((cb-1)*n_b+phase*n_b//m)
        if stencil is not None:
            indices,weights=stencil
            x=np.einsum('na,nad->nd',weights,x[indices])
        for name,sl in (('velocity',slice(0,3)),('pressure',slice(3,4))):
            squared=b.mesh.squared(x[:,sl]-y[:,sl])/b.mesh.volume
            sums[name]+=squared/m
            maximum[name]=max(maximum[name],math.sqrt(squared))
    _,ref_squared=b.mesh.reference(db,4)
    scales=dict(velocity=math.sqrt(ref_squared/(2*b.mesh.volume)),pressure=db['pressure_amplitude']/math.sqrt(6))
    return dict(coarse_definition=da,fine_definition=db,coarse_cycle=ca,fine_cycle=cb,common_phases=m,
        reference_scales=scales,rms={k:math.sqrt(v) for k,v in sums.items()},maximum_phase_rms=maximum,
        relative_rms={k:math.sqrt(v)/scales[k] for k,v in sums.items()},
        relative_maximum_phase_rms={k:v/scales[k] for k,v in maximum.items()},
        norm='Exact P1 volume L2 on the nested target mesh, cycle RMS and maximum phase separately',
        scope='Field difference only; interpretation requires the recorded parameter differences')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coarse',type=Path,required=True)
    parser.add_argument('--fine',type=Path,required=True)
    parser.add_argument('--coarse-cycle',type=int)
    parser.add_argument('--fine-cycle',type=int)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=compare(Study(args.coarse),Study(args.fine),args.coarse_cycle,args.fine_cycle)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    main()
