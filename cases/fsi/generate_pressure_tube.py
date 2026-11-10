"""Conforming pressure-driven linear elastic tube for quantitative comparison.

Both open caps carry the same mean-plus-sinusoidal pressure. Solid ends and ALE
caps are clamped; the outer wall has zero traction. This is a compliance case,
separate from the prescribed-flow tube and the rigid Womersley case.
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import study_rigid_tube as tube


def generate(directory,sectors=12,radial=2,axial=12,level=0,steps_per_cycle=100,cycles=6,length=12):
    directory=Path(directory)
    if level not in (0,1,2,3) or steps_per_cycle<4 or cycles<1:
        raise ValueError('Invalid refinement/time parameters')
    if not math.isfinite(length) or length<=0:
        raise ValueError('Length must be finite and positive')
    directory.mkdir(parents=True,exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Pressure tube generation requires an empty directory')
    base=tube.generate(directory/'base',sectors=sectors,radial=radial,axial=axial,radius=1,thickness=.2,length=length)
    cfg=json.loads(base.read_text())
    for domain in ('fluid','solid'):
        mesh=tube.read_mesh(directory/'base'/f'{domain}.msh')
        for _ in range(level):
            mesh=tube.refine(*mesh)
        region=cfg['fsi']['domains'][domain+'_region']
        tube.write_mesh(directory/f'{domain}.msh',*mesh,region=region)
    f=cfg['fsi']
    f.pop('inlet');f.pop('stabilization_tau')
    f.update(material='linear',young=1000,poisson=.3,density=1,solid_density=1,viscosity=1,
             pressure=.02,pressure_time=dict(amplitude=.01,period=2*math.pi),
             dt=2*math.pi/steps_per_cycle,steps=cycles*steps_per_cycle,output_interval=1,checkpoint_interval=steps_per_cycle)
    f['domains']['pressure_tags']=[1,2]
    cfg['time']=dict(scheme='generalized_alpha',rho_infinity=.5)
    cfg['output']='solution.vtu'
    path=directory/'case.json';path.write_text(json.dumps(cfg,indent=2)+'\n')
    geometry=json.loads((directory/'base/geometry.json').read_text())
    geometry.update(red_refinements=level,young=1000,poisson=.3,
                    infinite_plane_strain_inner_wall_compliance=(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1)))
    (directory/'geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sectors',type=int,default=12);p.add_argument('--radial',type=int,default=2)
    p.add_argument('--axial',type=int,default=12);p.add_argument('--level',type=int,default=0)
    p.add_argument('--steps-per-cycle',type=int,default=100);p.add_argument('--cycles',type=int,default=6)
    p.add_argument('--length',type=float,default=12,help='Tube length; adjust --axial separately to retain axial mesh spacing')
    a=p.parse_args();print(generate(a.output,a.sectors,a.radial,a.axial,a.level,a.steps_per_cycle,a.cycles,a.length))
