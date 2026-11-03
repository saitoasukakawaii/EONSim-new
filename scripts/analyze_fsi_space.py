"""Compare complete periodic cycles on nested structured reference meshes."""
import argparse
import json
import math
from pathlib import Path
from fsi_field_cycles import read_snapshot,series,pressure_drop
from fsi_space_metrics import interpolation,distance


def last_cycle(work,solid):
    receipt=json.loads((work/'periodic-result.json').read_text())
    if not receipt['converged']:raise ValueError('Spatial comparison requires converged periodic receipt')
    cycle=receipt['metrics'][-1]['cycle'];steps=round(.1/receipt['config']['fsi']['dt'])
    stem=f'cycle{cycle}_restart{(cycle-1)*steps}'+('_solid' if solid else '')
    entries=series(work/(stem+'.pvd'))
    result=[]
    for j in range(1,21):
        time=(cycle-1)*.1+j*.005
        found=[path for t,path in entries if abs(t-time)<1e-10]
        if len(found)!=1:raise ValueError('Missing complete common phase grid')
        result.append(found[0])
    return result


def compare(coarse,fine,n):
    result={}
    for solid in (False,True):
        a=last_cycle(coarse,solid);b=last_cycle(fine,solid)
        fields=['velocity','displacement'] if solid else ['velocity','pressure','mesh_displacement']
        stencil=interpolation(read_snapshot(a[0],solid,True),read_snapshot(b[0],solid),n)
        values=[]
        for left,right in zip(a,b):
            values.append(distance(read_snapshot(left,solid,True),read_snapshot(right,solid),stencil,fields))
        for field in fields:result[('solid_' if solid else 'fluid_')+field]=math.sqrt(sum(r[field]**2 for r in values)/len(values))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--coarse',type=Path,required=True);p.add_argument('--medium',type=Path,required=True);p.add_argument('--fine',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    first=compare(a.coarse,a.medium,2);last=compare(a.medium,a.fine,4)
    result=dict(difference_2_4=first,difference_4_8=last,observed_orders={k:math.log(first[k]/last[k],2) for k in first})
    result['pressure_cycles']={str(work):[pressure_drop(read_snapshot(path,False,True)) for path in last_cycle(work,False)] for work in (a.coarse,a.medium,a.fine)}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if any(last[k]>=first[k] for k in first):raise RuntimeError('Spatial differences are not decreasing')


if __name__=='__main__':main()
