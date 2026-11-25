"""Audit fixed temporal scales in cellwise PSPG on two 3D meshes against their own DAE."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys

import numpy as np
from axisymmetric import TubeParameters


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(root, reference_scripts):
    sys.path.append(str(reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    from study_lame_wall import bore_section
    from study_rigid_tube import read_mesh

    data=[]
    for complete in sorted((root/'time-scale').glob('*.ok')):
        key=complete.stem
        grid=key.split('-t')[0]
        ref_path=complete.with_name(key+'-ref.json')
        ref=json.loads(ref_path.read_text())
        case=root/'spatial'/(grid+'-n32')/'reference'
        for filename,value in ref['case_sha256'].items():
            if value!=digest(case/filename):
                raise ValueError('DAE source mesh or input changed')
        baseline=json.loads((case/'case.json').read_text())
        directory=complete.with_name(key+'-eon')
        comparison=json.loads((directory/'comparison.json').read_text())
        if comparison['executable_sha256']!=digest(root/'time-scale-eonsim'):
            raise ValueError('EONSim executable differs from the completed experiment')
        mesh=read_mesh(case/'solid.msh')
        rings={}
        for node in {n for tag,face in mesh[2] if tag==13 for n in face}:
            rings.setdefault(mesh[0][node][0],[]).append(node)
        if sorted(rings)!=ref['x']:
            raise ValueError('Solid bore stations differ from the DAE')
        for run in comparison['cases']:
            n,pressure=run['steps'],run['pressure']
            path=directory/f'n{n}-p{pressure:g}'
            cfg=json.loads((path/'case.json').read_text())
            expected=json.loads(json.dumps(baseline))
            expected['fsi'].update(steps=n,dt=1/n,output_interval=n//2,pressure=pressure,
                                   pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.),grad_div_viscosity=0.,
                                   stabilization_time_scale=ref['stabilization_time_scale'])
            expected['solver']['absolute_tolerance']*=pressure/ref['pressure']
            if cfg!=expected or any(digest(path/name)!=ref['case_sha256'][name] for name in ('fluid.msh','solid.msh')):
                raise ValueError('Unmatched physical mesh or transient deck')
            log=(path/'solve.log').read_text()
            if ([int(v) for v in re.findall(r'^fsi_step=(\d+) ',log,re.M)]!=list(range(1,n+1))
                    or log.count('status=success')!=1):
                raise ValueError('Incomplete nonlinear trajectory')
            with (path/'tube.csv').open() as f:
                hist=list(csv.DictReader(f))
            if (len(hist)!=n or any(int(s['step'])!=k or abs(float(s['time'])-k/n)>1e-13
                    for k,s in enumerate(hist,1))):
                raise ValueError('Accepted integration times differ')
            run['hashes']={name:digest(path/name) for name in ('case.json','tube.csv','solve.log')}
            for sample in run['samples']:
                stem=f"tube_step{round(n*sample['time'])}_solid"
                field=recovered_state(path,stem,mesh,True,1)
                ds={node:v.displacement for node,v in field.items()}
                area=[bore_section(mesh[0],ds,rings[x])['linear_area_strain'] for x in ref['x']]
                if not np.allclose(area,sample['sections'],rtol=1e-12,atol=1e-18):
                    raise ValueError('Displacement-derived linearized area differs')
                run['hashes'][stem+'.vtu']=digest(path/(stem+'.vtu'))
        data.append(dict(grid=grid,reference=ref,comparison=comparison,reference_sha256=digest(ref_path)))
    return data


def tables(data):
    rows=[]
    for study in data:
        ref=study['reference']
        comp=study['comparison']
        if (ref['fixed_tau'] is not None or ref['stabilization_time_scale']!=comp['stabilization_time_scale']
                or ref['grad_div_viscosity']!=0 or ref['manufactured_max_error']>1e-8):
            raise ValueError('DAE coefficient or manufactured verification differs')
        finest=max(ref['runs'],key=lambda s:s['steps'])
        if finest['steps']!=comp['reference_steps'] or comp['reference_step_doubling_delta']>1e-4:
            raise ValueError('Insufficient reference time resolution')
        scale=ref['pressure']
        exact=TubeParameters().lame_area_strain(scale)
        for run in comp['cases']:
            for observed, reference in zip(run['samples'],finest['samples']):
                if observed['time']!=reference['time'] or len(observed['sections'])!=len(ref['x']):
                    raise ValueError('Mismatched stations or time')
                areas=np.array(observed['sections'])
                target=np.array(reference['section_area_strain'])*run['pressure']/scale
                errors=(areas-target)/(exact*run['pressure']/scale)
                if not np.allclose(errors,observed['normalized_differences'],rtol=2e-10,atol=1e-13):
                    raise ValueError('Replayed section difference disagrees with original comparison')
                j=int(np.argmax(abs(errors)))
                rows.append(dict(grid=study['grid'],unknowns=ref['unknowns'],cell_scale_s=ref['stabilization_time_scale'],
                                 tau_min=ref['pspg_coefficient_range'][0],tau_max=ref['pspg_coefficient_range'][1],
                                 n=run['steps'],peak_pa=run['pressure'],time_s=observed['time'],
                                 left_area_pct=100*areas[0],middle_area_pct=100*areas[len(areas)//2],
                                 ref_left_pct=100*target[0],max_section_gap_pct_static=100*abs(errors[j]),worst_x=ref['x'][j]))
    if len({(r['grid'],r['cell_scale_s']) for r in rows})!=4:
        raise ValueError('Expected both independent time scales on both source meshes')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--runs',type=Path)
    source.add_argument('--archive',type=Path)
    p.add_argument('--reference-scripts',type=Path)
    p.add_argument('--write-archive',type=Path)
    p.add_argument('--csv',type=Path,required=True)
    a=p.parse_args()
    if a.runs and not a.reference_scripts:
        p.error('The original field reader is required for raw validation')
    data=pack(a.runs,a.reference_scripts) if a.runs else json.loads(lzma.decompress(a.archive.read_bytes()))
    rows=tables(data)
    with a.csv.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    if a.write_archive:
        a.write_archive.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
    print(len(rows)//2,'accepted nonlinear trajectories on',len(data),'fixed spatial operators')


if __name__=='__main__':
    main()
