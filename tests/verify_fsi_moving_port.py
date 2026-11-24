"""Check current area, flow and pressure on an elastic RCR port with tangential ALE motion."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import re

from verify_curved_fsi import frame_difference, generate, reference_nodes
from verify_fsi_inlet import Runner, check_rcr_history, error
from study_rigid_tube import cross, read_mesh, sub
from generate_branched import generate as make_junction


def release_plane(domains, model, normal_axis, wall_tag):
    model['moving_plane_axis']=normal_axis
    for key,tag in [('mesh_constraints',model['tag']),('solid_constraints',wall_tag)]:
        next(b for b in domains[key] if b['tag']==tag)['components']=[normal_axis]


def circular_case(directory, direction, origin):
    cfg=json.loads(generate(directory,sectors=8,radial=2,axial=3,bend_degrees=0.,
                            direction=direction,origin=origin).read_text())
    geo=json.loads((directory/'geometry.json').read_text())
    f=cfg['fsi']
    f.update(steps=9,dt=.015,output_interval=9)
    f['inlet'].update(ramp_time=.015)
    f['inlet']['flow_rate'].update(mean=.006,amplitude=.012,period=.10)
    dom=f['domains']
    model=dom['rcr_outlet']
    model.update(initial_capacitor_pressure=.3,distal_pressure=.05)
    release_plane(dom,model,next(i for i,v in enumerate(direction) if v),12)
    cfg['time_control']=dict(step_sizes=[.015,.013,.017,.012,.019,.014,.016,.012,.013])
    return cfg,geo


def cap(directory,fields,tag,normal):
    """Integrate the current Tri3 absolute area and signed flux directly from both mesh and VTU."""
    reference,_,faces=read_mesh(directory/'fluid.msh')
    def key(x):return tuple(round(v,10) for v in x)
    mapped={key(x):n for (solid,n),x in reference_nodes(fields).items() if not solid}
    area=flux=reference_flux=reference_area=0.
    for label,tri in faces:
        if label!=tag:continue
        nodes=[mapped[key(reference[i])] for i in tri]
        positions=[fields[False,n,'coordinates'] for n in nodes]
        vel=[fields[False,n,'velocity'] for n in nodes]
        x,y,z=(reference[i] for i in tri)
        a,b,c=positions
        vector=cross(sub(b,a),sub(c,a))
        oriented=sum(v*w for v,w in zip(vector,normal))
        s=.5*abs(oriented)
        s0=.5*math.hypot(*cross(sub(y,x),sub(z,x)))
        u=sum(sum(v*w for v,w in zip(value,normal)) for value in vel)/3
        area+=s;flux+=s*u;reference_flux+=s0*u;reference_area+=s0
        if any(abs(sum(n*(p-v) for n,p,v in zip(normal,point,reference[i])))>1e-12 for point,i in zip(positions,tri)):
            raise ValueError('Out-of-plane mesh motion at a fixed normal component')
    if reference_area<=0:raise ValueError('Missing exterior tag')
    return area,flux,reference_area,reference_flux


def branched(executable, mpi, directory):
    cfg=json.loads(make_junction(directory).read_text())
    geo=json.loads((directory/'geometry.json').read_text())
    run=Runner(executable,mpi,directory,interface_area=geo['interface_area'])
    f=cfg['fsi']
    f.update(steps=6, dt=.016, output_interval=6, pressure_face_history=True)
    dom=f['domains']
    left,right=dom['rcr_outlets']
    left['initial_capacitor_pressure']=.18
    right['initial_capacitor_pressure']=.09
    result={}
    for label in ('one-moving','opposite-normals'):
        if label=='one-moving':
            release_plane(dom,left,1,12)
        else:
            release_plane(dom,right,1,13)
        serial,rows,_=run.solve(label+'-one',cfg)
        parallel,trace,_=run.solve(label+'-two',cfg,2)
        worst=0.
        changes=[]
        for model,normal in [(left,(0.,1.,0.)),(right,(0.,-1.,0.))]:
            tag=model['tag']
            a,q,a0,_=cap(directory,serial,tag,normal)
            changes.append(a/a0-1)
            worst=max(worst,abs(q-rows[-1]['endpoint_rcr_flow_'+str(tag)]),
                      check_rcr_history(run,label+'-two',model,trace,sole_pressure=False))
        if (error(serial,parallel)>2e-9 or worst>2e-10 or abs(changes[0])<1e-6
                or ((abs(changes[1])<1e-6) != (label=='one-moving'))):
            raise ValueError('Mixed stationary/moving daughter circuit or opposite outward signs failed')
        result[label]=dict(mpi_error=error(serial,parallel),raw_flux_or_circuit_error=worst,final_area_changes=changes)
    return result


def retry(run, original):
    cfg=copy.deepcopy(original)
    f=cfg['fsi']
    f.update(dt=.10)
    f['inlet']['flow_rate'].update(mean=.12,amplitude=.03)
    cfg['time_control']=dict(step_sizes=[.004,.004,.10])
    cfg['time']=dict(scheme='generalized_alpha',rho_infinity=.5)
    checkpoint=run.work/'retry-checkpoint'
    run.solve('retry-seed',cfg,2,['-checkpoint',checkpoint,'-stop_after',2])
    cfg['time_control'].update(max_retries=18,minimum_dt=1e-10,reduction=.5)
    actual,rows,log=run.solve('retry',cfg,2,['-restart',checkpoint,'-snes_max_it',3,'-stop_after',3])
    if len(rows)!=1 or 'step_retry=' not in log or rows[0]['accepted_dt']>=f['dt']:
        raise ValueError('Did not exercise a rejected moving-port stage')
    cfg['time_control']['step_sizes']=[.004,.004,rows[0]['accepted_dt']]
    replay,full,_=run.solve('retry-replay',cfg,2,['-stop_after',3])
    gap=error(actual,replay)
    circuit=check_rcr_history(run,'retry',f['domains']['rcr_outlet'],rows,restart=2)
    pressure=abs(rows[0]['endpoint_rcr_pressure']-full[-1]['endpoint_rcr_pressure'])
    if gap>2e-9 or pressure>2e-10:
        raise ValueError('Rejected geometry or capacitor state leaked into the retried step')
    return dict(retries=log.count('step_retry='),accepted_dt=rows[0]['accepted_dt'],field_difference=gap,
                pressure_difference=pressure,circuit_defect=circuit)


def verify(executable,mpi,work):
    direction=(1.,0.,0.)
    origin=(0.,0.,0.)
    base=work/'axis-x'
    cfg,geo=circular_case(base,direction,origin)
    run=Runner(executable,mpi,base,interface_area=geo['interface_area'])
    report={}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time']=dict(scheme=scheme,rho_infinity=.5) if scheme=='generalized_alpha' else dict(scheme=scheme)
        model=cfg['fsi']['domains']['rcr_outlet']
        one,rows,_=run.solve(scheme+'-one',cfg)
        two,parallel,_=run.solve(scheme+'-two',cfg,2)
        residual=check_rcr_history(run,scheme+'-two',model,parallel)
        a,q,a0,q0=cap(base,one,2,direction)
        with (base/(scheme+'-one_pressure_faces.csv')).open() as f:
            faces=list(csv.DictReader(f))
        area_error=abs(a-float(faces[-1]['endpoint_area']))
        flux_error=abs(q-rows[-1]['endpoint_rcr_flow'])
        field_error=error(one,two)
        area_change=abs(a/a0-1)
        if (area_error>2e-12 or flux_error>2e-12 or field_error>2e-9 or area_change<1e-5
                or abs(q-q0)<1e-10 or max(abs(r['stage_mass_residual']+r['stage_divergence']) for r in rows)>2e-11):
            raise ValueError(f'Current surface or distributed solution failed: {(a,q,a0,q0,field_error)}')
        checkpoint=base/('checkpoint-'+scheme)
        silent=copy.deepcopy(cfg)
        silent['fsi'].update(output_interval=0,pressure_face_history=False)
        run.solve('silent-'+scheme,silent,2,['-checkpoint',checkpoint,'-stop_after',4])
        resumed,tail,_=run.solve('resume-'+scheme,cfg,2,['-restart',checkpoint])
        check_rcr_history(run,'resume-'+scheme,model,tail,restart=4)
        restart_error=error(resumed,two)
        pressure_error=max(abs(i['endpoint_rcr_pressure']-j['endpoint_rcr_pressure']) for i,j in zip(tail,parallel[4:]))
        if restart_error>2e-9 or pressure_error>2e-10 or len(tail)!=len(parallel)-4:
            raise ValueError('No-output checkpoint changed subsequent physical or capacitor state')
        report[scheme]=dict(area_change_fraction=area_change,reference_flux_error=abs(q-q0),
                            raw_flux_error=flux_error,raw_area_error=area_error,field_mpi_error=field_error,
                            circuit_defect=residual,restart_error=restart_error,restart_pressure_error=pressure_error)

    _,_,log=run.solve('jacobian',cfg,2,['-snes_test_jacobian','-stop_after',3])
    ratios=[float(v) for v in re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)]
    if not ratios or max(ratios)>1e-6:raise ValueError('Full FSI Jacobian failed')
    report['jacobian_frobenius_ratio']=max(ratios)
    for axis,negative in ((1,True),(2,False)):
        normal=tuple((-1. if negative else 1.) if i==axis else 0. for i in range(3))
        shifted=(.4,-.75,1.2)
        other=work/('axis-'+str(axis))
        rotated,geometry=circular_case(other,normal,shifted)
        rotated['time']=cfg['time']
        run2=Runner(executable,mpi,other,interface_area=geometry['interface_area'])
        fields,trace,_=run2.solve('moved',rotated,2)
        observed=cap(other,fields,2,normal)
        if abs(observed[1]-trace[-1]['endpoint_rcr_flow'])>2e-12:
            raise ValueError('Incorrect outward sign after rotation')
        changes=frame_difference(one,fields,normal,shifted)
        report['axis_'+str(axis)]=dict(max_field_change=max(changes.values()),raw_flux=observed[1])

    for label,change in [('wrong-axis',lambda c:c['rcr_outlet'].update(moving_plane_axis=2)),
                          ('free-normal',lambda c:c['mesh_constraints'].remove(next(b for b in c['mesh_constraints'] if b['tag']==2)))]:
        invalid=copy.deepcopy(cfg)
        change(invalid['fsi']['domains'])
        run.solve(label,invalid,2,fail='fixed normal mesh displacement')
    # Even a fully clamped port records the geometry model in its restart signature.
    clamped=copy.deepcopy(cfg)
    for k,t in [('mesh_constraints',2),('solid_constraints',12)]:
        next(b for b in clamped['fsi']['domains'][k] if b['tag']==t)['components']=[0,1,2]
    checkpoint=base/'fixed-checkpoint'
    fixed=copy.deepcopy(clamped)
    del fixed['fsi']['domains']['rcr_outlet']['moving_plane_axis']
    old,_,_=run.solve('reference-area',fixed,2,['-checkpoint',checkpoint])
    new,_,_=run.solve('fixed-plane',clamped,2)
    report['fully_fixed_equivalence']=error(old,new)
    if report['fully_fixed_equivalence']>2e-9:raise ValueError('Fixed-face equivalence failed')
    run.solve('changed-restart-model',clamped,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    report['retry']=retry(run,cfg)
    report['junction']=branched(executable,mpi,work/'junction')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',required=True)
    parser.add_argument('--mpiexec',required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    data=verify(args.executable,args.mpiexec,args.work.resolve())
    (args.work/'result.json').write_text(json.dumps(data,indent=2)+'\n')
    print(data,flush=True)


if __name__=='__main__':
    main()
