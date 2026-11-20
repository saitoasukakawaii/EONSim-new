"""Recompute static wall, coupled hydrostatic and ALE volume measurements."""
import argparse
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/'scripts'))
import audit_hydrostatic_mass as mass
import study_hydrostatic_fsi as fsi
import study_lame_wall as wall
import study_rigid_tube as tube


def section_change(a,b):
    """Largest difference between the two axial piecewise-linear area traces."""
    def samples(row):
        sections=row['slices'] if 'slices' in row else row['sections']
        return ([s['x'] for s in sections],
                [s['linear_area_strain']/row['exact_linear_area_strain'] for s in sections])
    def value(x,levels,values):
        i=max(0,min(len(levels)-2,bisect_right(levels,x)-1))
        f=(x-levels[i])/(levels[i+1]-levels[i])
        return values[i]+f*(values[i+1]-values[i])
    x,y=samples(a)
    X,Y=samples(b)
    if (x[0],x[-1])!=(X[0],X[-1]):
        raise ValueError('Wall length differs')
    return max(abs(value(t,x,y)-value(t,X,Y)) for t in sorted(set(x+X)))


def solid_comparison(root,left,right,ranks,scale):
    a,b=root/left,root/right
    if (a/'wall.msh').read_bytes()!=(b/'wall.msh').read_bytes():
        raise ValueError('Solid comparison meshes differ')
    nodes,_,_=tube.read_mesh(a/'wall.msh')
    ua,ub=wall.displacements(a,1,nodes),wall.displacements(b,ranks,nodes)
    return max(abs(y-scale*x) for n in nodes for x,y in zip(ua[n],ub[n]))


def coupled_mpi(root,serial,parallel,ranks):
    a,b=root/serial,root/parallel
    if (a/'case.json').read_bytes()!=(b/'case.json').read_bytes():
        raise ValueError('Coupled MPI inputs differ')
    n=json.loads((a/'case.json').read_text())['fsi']['steps']
    result={}
    for solid,meshname in [(False,'fluid.msh'),(True,'solid.msh')]:
        if (a/meshname).read_bytes()!=(b/meshname).read_bytes(): raise ValueError('MPI meshes differ')
        mesh=tube.read_mesh(a/meshname)
        stem=f'tube_step{n}'+('_solid' if solid else '')
        u,v=(fsi.recovered_state(d,stem,mesh,solid,k) for d,k in ((a,1),(b,ranks)))
        domain='solid' if solid else 'fluid'
        for field in ('displacement','velocity'):
            result[domain+'_'+field]=max(abs(x-y) for i in u for x,y in zip(getattr(u[i],field),getattr(v[i],field)))
        if not solid:
            result['fluid_pressure']=max(abs(u[i].pressure-v[i].pressure) for i in u)
    return result


def replay(root,external=False):
    spec=json.loads((root/'dataset.json').read_text())
    solid=root/'static'
    coupled=root/'coupled'
    s={name:wall.analyze(solid/name,n) for name,n in spec['static'].items()}
    f={name:fsi.analyze(coupled/name,n) for name,n in spec['coupled'].items()}
    ref='s96-w8-a12'
    primary='s48-w4-r4-a6-dt05'
    comparisons=dict(
        last_two_static_area_change=section_change(s[ref],s['s192-w12-a16']),
        static_mpi2_max_displacement_difference=solid_comparison(solid,ref,ref+'-mpi2',2,1),
        static_mpi4_max_displacement_difference=solid_comparison(solid,ref,ref+'-mpi4',4,1),
        double_pressure_max_displacement_difference=solid_comparison(solid,ref,ref+'-double',1,2),
        coupled_dt_area_change=section_change(f[primary],f['s48-w4-r4-a6-dt025']),
        coupled_half_pressure_area_compliance_change=section_change(f[primary],f[primary+'-half']),
        coupled_48_to_72_area_change=section_change(f[primary],f['s72-w6-r5-a8-dt05']),
        coupled_vs_isolated_48_area_change=section_change(s['s48-w4-a6'],f[primary]),
        coupled_mpi2_differences=coupled_mpi(coupled,primary,primary+'-mpi2',2))
    result=dict(static=s,coupled=f,comparisons=comparisons,
                mass={name:mass.audit(coupled/name) for name in spec['mass']})
    if external:
        from compare_svfsi_wall import compare
        result['svfsi']={name:compare(coupled/case,root/'svfsi'/name,name in spec.get('settling',[]))
                         for name,case in spec['svfsi'].items()}
    return result


def check(a,b,path='results'):
    if isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys():
        for k in a: check(a[k],b[k],path+'.'+k)
    elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        for i,(x,y) in enumerate(zip(a,b)): check(x,y,f'{path}[{i}]')
    elif isinstance(a,float) and isinstance(b,(float,int)):
        if not math.isclose(a,b,rel_tol=2e-9,abs_tol=5e-13): raise ValueError(f'{path}: {a} differs from {b}')
    elif a!=b:
        raise ValueError('Mismatch at '+path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path,help='Extracted raw archive')
    p.add_argument('--output',type=Path)
    p.add_argument('--verify',action='store_true')
    p.add_argument('--external',action='store_true',help='Also read the pinned svFSI result VTUs with Python VTK')
    a=p.parse_args()
    if a.verify:
        for key,sha in json.loads((HERE/'manifest.json').read_text())['files'].items():
            if hashlib.sha256((a.root/key).read_bytes()).hexdigest()!=sha:
                raise ValueError('Hash differs for '+key)
    values=replay(a.root,a.external)
    if a.verify:
        expected=json.loads((HERE/'results.json').read_text())
        if not a.external: expected.pop('svfsi')
        check(values,expected)
        print('Archived values reproduced.',file=sys.stderr)
    output=json.dumps(values,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if a.output: a.output.write_text(output)
    else: print(output,end='')


if __name__=='__main__':
    main()
