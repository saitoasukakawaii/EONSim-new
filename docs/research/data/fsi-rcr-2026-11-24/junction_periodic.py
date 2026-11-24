"""Measure pressure-driven exchange between two RCR terminals of the 3D T-junction."""
import argparse
import cmath
import fcntl
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests'),str(ROOT/'cases/fsi')]
from branch_external import observations
from generate_branched import generate
from study_rigid_tube import read_mesh
from verify_fsi_inlet import Runner, check_rcr_history


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cap_and_volume(mesh,fields):
    nodes=mesh[0]
    xyz={tuple(round(v,12) for v in x):i for i,x in nodes.items()}
    state={}
    for solid,i,key in fields:
        if solid or key!='coordinates':continue
        d=fields[False,i,'mesh_displacement']
        point=tuple(round(x-y,12) for x,y in zip(fields[False,i,key],d))
        j=xyz[point]
        state[j]=SimpleNamespace(displacement=d,velocity=fields[False,i,'velocity'])
    if state.keys()!=nodes.keys():raise ValueError('Missing active fluid nodes in the final VTU')
    return observations(mesh,state)


def fourier(rows,field,hz):
    return 2j/len(rows)*sum(r[field]*cmath.exp(-2j*math.pi*hz*r['time']) for r in rows)


def configure(directory,grid,hz,n,cycles,elastic,tau):
    cfg=json.loads(generate(directory,grid).read_text())
    geo=json.loads((directory/'geometry.json').read_text())
    f=cfg['fsi']
    f.update(material='linear',dt=1/(hz*n),steps=n*cycles,output_interval=n*cycles,
             pressure_face_history=True,stabilization_tau=tau)
    f['inlet']['ramp_time']=0.
    f['inlet']['flow_rate'].update(mean=0.,amplitude=0.,period=1/hz)
    if not elastic:
        f['domains']['solid_constraints'].extend(dict(tag=t,components=[0,1,2]) for t in (14,15))
    models=f['domains']['rcr_outlets']
    for model,rp,rd,c,p in zip(models,(3.,12.),(8.,32.),(.025,.0125),(.02,-.02)):
        model.update(proximal_resistance=rp,distal_resistance=rd,compliance=c,distal_pressure=0.,
                     initial_capacitor_pressure=0.,distal_pressure_time=dict(amplitude=p,period=1/hz))
    return cfg,geo


def run_case(exe,mpi,directory,grid,hz,n,cycles,elastic,tau):
    cfg,geo=configure(directory,grid,hz,n,cycles,elastic,tau)
    models=cfg['fsi']['domains']['rcr_outlets']
    runner=Runner(exe,mpi,directory,timeout=14400,interface_area=geo['interface_area'],singleton=True)
    fields,rows,_=runner.solve('coupled',cfg)
    if len(rows)!=cycles*n:raise ValueError('Incomplete transient')
    closure=max(check_rcr_history(runner,'coupled',m,rows,sole_pressure=False) for m in models)
    mesh=read_mesh(directory/'fluid.msh')
    vtu=cap_and_volume(mesh,fields)
    flux_error=max(abs(a-b) for a,b in zip(vtu['flux'],[0.,*[rows[-1]['endpoint_rcr_flow_'+str(t)] for t in (2,3)]]))
    volume_error=abs(vtu['volume_gain']-(rows[-1]['endpoint_volume']-geo['reference_fluid_volume']))
    ports=[]
    for t in (2,3):
        port={}
        for field in ('rcr_flow','rcr_pressure','capacitor_pressure','distal_pressure'):
            key='endpoint_'+field+'_'+str(t)
            z=fourier(rows[-n:],key,hz)
            prev=fourier(rows[-2*n:-n],key,hz)
            signal=[r[key] for r in rows[-n:]]
            port[field]=dict(phasor=[z.real,z.imag],cycle_change=abs(z-prev)/abs(z),
                             mean=math.fsum(signal)/n,minimum=min(signal),maximum=max(signal))
        ports.append(port)
    scale=max(abs(complex(*p['rcr_flow']['phasor'])) for p in ports)
    mass=max(abs(r['endpoint_rcr_flow_2']+r['endpoint_rcr_flow_3']) for r in rows)/scale
    volume=max(abs(r['endpoint_volume']-geo['reference_fluid_volume']) for r in rows)
    if (flux_error>1e-10*scale+1e-15 or volume_error>1e-11 or
            any(p['rcr_flow']['minimum']>=0. or p['rcr_flow']['maximum']<=0. for p in ports) or
            (not elastic and (mass>1e-7 or volume>1e-10))):
        raise ValueError(f'Cap flux, sign or volume discrepancy: {flux_error}, {volume_error}, {mass}, {volume}')
    files=['fluid.msh','solid.msh','coupled.json','coupled.csv','coupled_pressure_faces.csv','coupled.vtu','coupled_solid.vtu']
    return dict(refinement=grid,frequency_hz=hz,samples=n,cycles=cycles,elastic=elastic,fixed_pspg=tau,ports=ports,
                last_vtu=vtu,history_vtu_flow_error=flux_error,history_vtu_volume_error=volume_error,
                max_net_outflow_over_amplitude=mass,max_volume_change=volume,stage_closure=closure,
                executable_sha256=digest(exe),input_output_sha256={f:digest(directory/f) for f in files})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--mpiexec',default='mpiexec')
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--grid',type=int,required=True)
    p.add_argument('--hz',type=float,required=True)
    p.add_argument('--tau',type=float,default=.01)
    p.add_argument('--samples',type=int,default=32)
    p.add_argument('--cycles',type=int,default=10)
    p.add_argument('--elastic',action='store_true')
    a=p.parse_args()
    if a.samples<8 or a.cycles<2 or a.hz<=0 or a.grid<1 or not math.isfinite(a.tau) or a.tau<=0:p.error('Use at least two resolved cycles')
    a.work.mkdir(parents=True,exist_ok=True)
    request=dict(refinement=a.grid,frequency_hz=a.hz,samples=a.samples,cycles=a.cycles,
                 elastic=a.elastic,fixed_pspg=a.tau,executable_sha256=digest(a.executable))
    result=a.work/'result.json'
    marker=a.work/'request.json'
    with (a.work/'request.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if marker.exists() and json.loads(marker.read_text())!=request:
            raise ValueError('Use a separate directory for each junction input and executable')
        if result.exists():
            report=json.loads(result.read_text())
            if (any(report.get(k)!=v for k,v in request.items()) or
                    any(digest(a.work/name)!=expected for name,expected in report['input_output_sha256'].items())):
                raise ValueError('The existing junction result belongs to different inputs or fields')
        else:
            if not marker.exists() and (a.work/'coupled.json').exists():
                raise ValueError('An existing run owns this output directory')
            marker.write_text(json.dumps(request,indent=2)+'\n')
            report=run_case(a.executable.resolve(),a.mpiexec,a.work,a.grid,a.hz,a.samples,a.cycles,a.elastic,a.tau)
            temporary=result.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
            temporary.replace(result)
    print([(v['rcr_flow']['phasor'],v['rcr_flow']['cycle_change']) for v in report['ports']],flush=True)


if __name__=='__main__':
    main()
