"""Cross-mesh P1 interpolation for the structured reference channel generator.

The norm is reference-volume lumped L2 on the fine mesh, not a continuum error.
"""
import math


def determinant(a,b,c):
    return a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])


def interpolation(coarse,fine,subdivisions):
    if not isinstance(subdivisions,int) or subdivisions<1:raise ValueError('Invalid subdivisions')
    nodes,_,cells=coarse;target,_=fine
    lo=[min(v['reference_position'][c] for v in nodes.values()) for c in range(3)]
    hi=[max(v['reference_position'][c] for v in nodes.values()) for c in range(3)]
    width=[(b-a)/subdivisions for a,b in zip(lo,hi)]
    if subdivisions<1 or min(width)<=0:raise ValueError('Invalid structured reference mesh')
    def bucket(x):return tuple(min(subdivisions-1,max(0,math.floor((x[c]-lo[c])/width[c]+1e-10))) for c in range(3))
    buckets={}
    for cell in cells:
        xyz=[nodes[k]['reference_position'] for k in cell]
        center=[sum(x[c] for x in xyz)/4 for c in range(3)]
        buckets.setdefault(bucket(center),[]).append(cell)
    result={}
    for node,values in target.items():
        x=values['reference_position']
        for cell in buckets.get(bucket(x),[]):
            xyz=[nodes[k]['reference_position'] for k in cell]
            a,b,c=[[v[j]-xyz[0][j] for j in range(3)] for v in xyz[1:]]
            r=[x[j]-xyz[0][j] for j in range(3)];det=determinant(a,b,c)
            if abs(det)<1e-30:raise ValueError('Degenerate reference cell')
            l=[determinant(r,b,c)/det,determinant(a,r,c)/det,determinant(a,b,r)/det];l=[1-sum(l),*l]
            if min(l)>=-1e-9 and max(l)<=1+1e-9:
                result[node]=(cell,l);break
        else:raise ValueError('Fine node is outside coarse reference cells')
    return result


def distance(coarse,fine,stencil,fields):
    nodes=coarse[0];target,weights=fine;volume=sum(weights.values());result={}
    if stencil.keys()!=target.keys():raise ValueError('Incompatible interpolation target')
    for field in fields:
        squared=0.
        for k,v in target.items():
            cell,l=stencil[k]
            interpolated=[sum(w*nodes[n][field][c] for n,w in zip(cell,l)) for c in range(len(v[field]))]
            squared+=weights[k]*sum((a-b)**2 for a,b in zip(interpolated,v[field]))
        result[field]=math.sqrt(squared/volume)
        if not math.isfinite(result[field]):raise ValueError('Nonfinite spatial difference')
    return result
