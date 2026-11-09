"""Offline first-harmonic/interpolation/axial localization of existing fields."""
import hashlib,json,math,sys
from pathlib import Path

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
import numpy as np
from scipy.special import jv
from analyze_womersley import Study,tetra_rule
from womersley_reference import velocity_amplitude

work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'womersley-localization-2189a8c.json'
assert not out.exists()
shape,weight=tetra_rule(6);reports=[]
for name in ('womersley-a2-s48-l0-n100','womersley-a2-s48-l1-n100','womersley-a2-s48-l0-n200'):
    study=Study(work/name);mesh=study.mesh;d=study.definition
    states=study.cycle(5);theta=2*np.pi*np.arange(1,len(states)+1)/len(states)
    coefficient=2*(np.sin(theta)+1j*np.cos(theta))/len(states)
    amplitude=np.einsum('m,mnc->nc',coefficient,states)
    exact=lambda r:velocity_amplitude(r,d['alpha'],d['radius'],d['viscosity'],d['pressure_amplitude']/d['length'],bessel=jv)
    nodal=np.zeros_like(amplitude[:,:3]);nodal[:,0]=exact(np.linalg.norm(mesh.xyz[:,1:],axis=1))
    center=mesh.points.mean(axis=1);bands=np.minimum(7,np.floor(center[:,0]*8/d['length']).astype(int))
    lo=bands*d['length']/8;hi=(bands+1)*d['length']/8
    assert np.all(mesh.points[:,:,0].min(axis=1)>=lo-1e-12)
    assert np.all(mesh.points[:,:,0].max(axis=1)<=hi+1e-12)
    cells=mesh.cells
    inverse=np.linalg.inv(np.transpose(mesh.points[:,1:]-mesh.points[:,:1],(0,2,1)))
    local_p=amplitude[cells,3]
    gradp=np.einsum('ci,ci->c',local_p[:,1:]-local_p[:,:1],inverse[:,:,0])
    errors=np.zeros(len(cells));interpolation=np.zeros_like(errors);reference=np.zeros_like(errors)
    for begin in range(0,len(cells),1024):
        end=min(begin+1024,len(cells));ix=cells[begin:end]
        positions=np.einsum('qa,cad->cqd',shape,mesh.points[begin:end])
        value=np.einsum('qa,cad->cqd',shape,amplitude[ix,:3])
        interpolated=np.einsum('qa,ca->cq',shape,nodal[ix,0])
        target=exact(np.linalg.norm(positions[:,:,1:],axis=2))
        errors[begin:end]=np.sum(weight*(abs(value[:,:,0]-target)**2+np.sum(abs(value[:,:,1:])**2,axis=2))/2,axis=1)
        interpolation[begin:end]=np.sum(weight*abs(interpolated-target)**2/2,axis=1)
        reference[begin:end]=np.sum(weight*abs(target)**2/2,axis=1)
    denominator=float(mesh.volumes@reference)
    remainder=0.
    for phase,state in zip(theta,states):
        modeled=amplitude[:,:3].real*np.sin(phase)+amplitude[:,:3].imag*np.cos(phase)
        remainder+=mesh.squared(state[:,:3]-modeled)/len(states)
    difference=amplitude[:,:3]-nodal
    rows=[]
    for band in range(8):
        chosen=bands==band;volume=mesh.volumes[chosen];scale=float(volume@reference[chosen])
        g=complex(volume@gradp[chosen]/volume.sum()/(-d['pressure_amplitude']/d['length']))
        rows.append(dict(x_interval=[band*d['length']/8,(band+1)*d['length']/8],
            velocity_first_harmonic_relative_l2=math.sqrt(float(volume@errors[chosen])/scale),
            analytic_nodal_interpolation_relative_l2=math.sqrt(float(volume@interpolation[chosen])/scale),
            mean_axial_pressure_gradient_over_exact=[g.real,g.imag]))
    report=dict(study=name,cycle=5,definition=d,quadrature_order=6,
        first_harmonic_relative_l2=math.sqrt(float(mesh.volumes@errors)/denominator),
        analytic_nodal_interpolation_relative_l2=math.sqrt(float(mesh.volumes@interpolation)/denominator),
        numerical_minus_analytic_nodal_relative_l2=math.sqrt((mesh.squared(difference.real)+mesh.squared(difference.imag))/(2*denominator)),
        nonfirst_harmonic_relative_l2=math.sqrt(remainder/denominator),axial_bands=rows,
        interpretation='Localization only. Nodal interpolation is not the best-approximation projection. No causal attribution or new solve.')
    reports.append(report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('definition','axial_bands')}),flush=True)
out.write_text(json.dumps(dict(reports=reports,analysis_sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
    'scripts/analyze_womersley.py','scripts/womersley_reference.py')},helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2,allow_nan=False)+'\n')
