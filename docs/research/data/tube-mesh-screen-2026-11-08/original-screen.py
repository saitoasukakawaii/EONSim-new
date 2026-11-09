"""A-priori mesh interpolation screening; no PDE solve or accuracy acceptance."""
import hashlib,json,math,shutil,sys
from pathlib import Path

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
import numpy as np
from scipy.special import jv
import study_rigid_tube as tube
from analyze_womersley import Mesh,tetra_rule
from womersley_reference import velocity_amplitude

work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'tube-interpolation-screen-20261108';out.mkdir()
shape,weight=tetra_rule(4);reports=[]
definitions=[(48,8,16,0),(48,8,16,1),(48,12,24,0),(48,16,32,0),(96,8,16,0),(48,4,8,2)]
for sectors,radial,axial,level in definitions:
    directory=out/f's{sectors}-r{radial}-a{axial}-l{level}';directory.mkdir()
    if (sectors,radial,axial,level)==(48,4,8,2):
        shutil.copy2(work/'womersley-a2-s48-l2-n200/fluid.msh',directory/'fluid.msh')
    else:
        tube.generate(directory/'base',sectors=sectors,radial=radial,axial=axial,radius=1,length=2)
        data=tube.read_mesh(directory/'base/fluid.msh')
        for _ in range(level):data=tube.refine(*data)
        tube.write_mesh(directory/'fluid.msh',*data)
        del data
    mesh=Mesh(directory/'fluid.msh')
    edges=np.array([np.sum((mesh.points[:,a]-mesh.points[:,b])**2,axis=1) for a in range(4) for b in range(a+1,4)])
    quality=12*(3*mesh.volumes)**(2/3)/edges.sum(axis=0)
    h=(6*mesh.volumes)**(1/3);viscous=4/h**2
    sensitivity={}
    for n in (100,200,400):
        effective=2/3*(2*math.pi/4)/n;time_term=2/effective
        sensitivity[n]=float(mesh.volumes@(time_term**2/(time_term**2+viscous**2))/mesh.volume)
    interpolation={}
    for alpha in (1.,2.):
        exact=lambda r:velocity_amplitude(r,alpha,1.,1.,.01,bessel=jv)
        values=exact(np.linalg.norm(mesh.xyz[:,1:],axis=1));error=reference=0.
        for begin in range(0,len(mesh.cells),2048):
            end=min(begin+2048,len(mesh.cells));cells=mesh.cells[begin:end]
            coordinates=np.einsum('qa,cad->cqd',shape,mesh.points[begin:end])
            numerical=np.einsum('qa,ca->cq',shape,values[cells])
            analytical=exact(np.linalg.norm(coordinates[:,:,1:],axis=2))
            error+=float(mesh.volumes[begin:end]@np.sum(weight*abs(numerical-analytical)**2,axis=1))
            reference+=float(mesh.volumes[begin:end]@np.sum(weight*abs(analytical)**2,axis=1))
        interpolation[alpha]=math.sqrt(error/reference)
    report=dict(seed=[sectors,radial,axial],red_level=level,nodes=len(mesh.ids),tetrahedra=len(mesh.cells),
        relative_nodal_interpolation_l2=interpolation,
        tetrahedron_mean_ratio=dict(minimum=float(quality.min()),percentile_5=float(np.quantile(quality,.05)),median=float(np.median(quality))),
        volume_mean_tau_time_fraction_alpha2_zero_advection=sensitivity,
        mesh_sha256=hashlib.sha256((directory/'fluid.msh').read_bytes()).hexdigest())
    reports.append(report);(directory/'screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
result=dict(quadrature_order=4,reports=reports,
    scope='A-priori nodal interpolants only, not numerical solutions, best approximations, geometry error bounds or predicted runtime.',
    tau_fraction_definition='Volume mean of a_time^2/(a_time^2+a_visc^2), a_time=2/(2*dt/3), a_visc=4/(6*volume)^(2/3), zero advection. Not a field-error estimate.',
    analysis_sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
        'scripts/study_rigid_tube.py','scripts/analyze_womersley.py','scripts/womersley_reference.py')})
(out/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
shutil.copy2(__file__,out/'original-screen.py')
