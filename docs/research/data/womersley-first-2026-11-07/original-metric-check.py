import json,math,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.special import jv
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
from analyze_womersley import Mesh,metrics,tetra_rule
from womersley_reference import velocity_amplitude
base=Path('/home/tfblab633/EONSim-prod48-20261107')
mesh=Mesh(base/'steady-schur-pilot/s48-r4-a8/fluid.msh')
shape,w=tetra_rule(4)
moment_error=0.
for i in range(6):
    for j in range(6-i):
        for k in range(6-i-j):
            for l in range(6-i-j-k):
                p=np.array((i,j,k,l))
                exact=6*math.prod(math.factorial(int(n)) for n in p)/math.factorial(int(p.sum())+3)
                moment_error=max(moment_error,abs(float(w@np.prod(shape**p,axis=1))-exact))
assert moment_error<2e-14
assert abs(mesh.squared(np.ones(len(mesh.ids)))-mesh.volume)<1e-12
assert abs(mesh.squared(mesh.xyz[:,0])-mesh.volume*4/3)<1e-11
library_error=max(abs(velocity_amplitude(r,a)-velocity_amplitude(r,a,bessel=jv)) for a in (1,2,4) for r in np.linspace(0,1,101))
assert library_error<2e-16
d=dict(alpha=2.,radius=1.,viscosity=1.,pressure_amplitude=.02,length=2.)
m=8;theta=2*np.pi*np.arange(1,m+1)/m
amplitude=velocity_amplitude(np.linalg.norm(mesh.xyz[:,1:],axis=1),2,bessel=jv)
states=np.zeros((m,len(mesh.ids),4))
states[:,:,0]=np.sin(theta[:,None])*amplitude.real+np.cos(theta[:,None])*amplitude.imag
states[:,:,1]=.0001*np.cos(2*theta[:,None])*mesh.xyz[:,0]
states[:,:,3]=.02*np.sin(theta[:,None])*(1-mesh.xyz[:,0]/2)
reported=metrics(SimpleNamespace(mesh=mesh,definition=d),states,4)
error=reference=0.
for start in range(0,len(mesh.cells),512):
    end=min(start+512,len(mesh.cells))
    xyz=np.einsum('qa,cad->cqd',shape,mesh.points[start:end])
    exact_amp=velocity_amplitude(np.linalg.norm(xyz[:,:,1:],axis=2),2,bessel=jv)
    for phase,values in zip(theta,states):
        approximate=np.einsum('qa,cad->cqd',shape,values[mesh.cells[start:end],:3])
        exact=np.sin(phase)*exact_amp.real+np.cos(phase)*exact_amp.imag
        approximate[:,:,0]-=exact
        error+=np.sum(mesh.volumes[start:end]*np.sum(np.sum(approximate**2,axis=2)*w,axis=1))/m
        reference+=np.sum(mesh.volumes[start:end]*np.sum(exact**2*w,axis=1))/m
direct=math.sqrt(error/reference)
assert abs(direct-reported['velocity_relative_l2_error'])<2e-13
assert reported['pressure_rms_over_amplitude']<1e-15
result=dict(tetrahedron_moment_max_error=moment_error,bessel_series_vs_scipy_max_error=library_error,
            direct_space_time_l2=direct,harmonic_mass_l2=reported['velocity_relative_l2_error'],
            pressure_exact_error=reported['pressure_rms_over_amplitude'])
(base/'womersley-metric-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
