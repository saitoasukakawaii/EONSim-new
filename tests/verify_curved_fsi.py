"""Check flux, frame invariance and restarts on a curved elastic tube with a fixed RCR outlet."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

from verify_fsi_inlet import Runner, check_rcr_history, error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_curved import basis, generate
from study_rigid_tube import cross, read_mesh, sub

DIRECTION=(1.,2.,-3.)
ORIGIN=(1.25,-2.5,.6)


def rotate(v, axes):
    return [sum(component*direction[j] for component,direction in zip(v,axes)) for j in range(3)]


def reference_nodes(fields):
    nodes={}
    for (solid,node,name),x in fields.items():
        if name=='coordinates':
            displacement=fields[solid,node,'displacement' if solid else 'mesh_displacement']
            nodes[solid,node]=[v-d for v,d in zip(x,displacement)]
    return nodes


def frame_difference(reference, moved, direction, origin):
    axes=basis(direction)
    def key(x):return tuple(round(value,10) for value in x)
    lookup={(solid,key(x)):node for (solid,node),x in reference_nodes(moved).items()}
    sources=[(s,n,x) for (s,n),x in reference_nodes(reference).items()]
    if len(lookup)!=len(sources):raise ValueError('Changed or duplicate reference node')
    mapping={}
    for s,n,x in sources:
        position=[v+t for v,t in zip(rotate(x,axes),origin)]
        mapping[s,n]=lookup[s,key(position)]
    if len(set((s,mapped) for (s,_),mapped in mapping.items()))!=len(sources):
        raise ValueError('Rotation does not establish a bijection of nodes')
    expected={(s,mapping[s,n],name) for s,n,name in reference}
    if set(moved)!=expected:raise ValueError('Changed field support after rigid rotation')
    differences={}
    for (s,n,name),v in reference.items():
        if name=='coordinates':continue
        if len(v)==3:target=rotate(v,axes)
        elif len(v)==1:target=v
        else:raise ValueError('Unexpected FSI field tensor rank')
        obs=moved[s,mapping[s,n],name]
        delta=max(abs(x-y) for x,y in zip(target,obs))
        differences[name]=max(differences.get(name,0.),delta)
    if not all(math.isfinite(d) and d<3e-9 for d in differences.values()):
        raise ValueError(f'Rotated vector or scalar field differs: {differences}')
    return differences


def face_flux(directory, field, geometry):
    nodes,_,faces=read_mesh(directory/'fluid.msh')
    def key(x):return tuple(round(v,10) for v in x)
    ids={key(x):n for (solid,n),x in reference_nodes(field).items() if not solid}
    velocity={i:field[False,ids[key(x)],'velocity'] for i,x in nodes.items()}
    normals={1:geometry['inward_direction'],2:geometry['outlet_direction']}
    flux={1:0.,2:0.}
    for tag,tri in faces:
        if tag not in normals:continue
        a,b,c=(nodes[i] for i in tri)
        area=cross(sub(b,a),sub(c,a));mag=math.hypot(*area)
        cosine=sum(u*v for u,v in zip(area,normals[tag]))/mag
        if abs(abs(cosine)-1)>1e-12:raise ValueError('Misaligned curved-tube cap')
        signed_area=[v*(.5 if cosine>0 else -.5) for v in area]
        flux[tag]+=sum(sum(u*v for u,v in zip(signed_area,velocity[i])) for i in tri)/3
    return flux


def pair(exe,mpi,work,mesh,steps,ranks,extended=False):
    fields=[];histories=[];reports=[];runners=[];configs=[]
    for label,direction,origin,rank_count in [('base',(1.,0.,0.),(0.,0.,0.),1),('rotated',DIRECTION,ORIGIN,ranks)]:
        directory=Path(work)/label
        cfg=json.loads(generate(directory,sectors=mesh[0],radial=mesh[1],axial=mesh[2],
                                direction=direction,origin=origin).read_text())
        geometry=json.loads((directory/'geometry.json').read_text())
        run=Runner(exe,mpi,directory,timeout=3600,interface_area=geometry['interface_area'])
        q=cfg['fsi']['inlet']['flow_rate']
        if label=='base':
            del q['direction'];q['axis']=0
        else:q['direction']=[x*1e100 for x in DIRECTION]
        cfg['fsi'].update(steps=steps,output_interval=steps)
        f,h,_=run.solve('curved',cfg,rank_count)
        model=cfg['fsi']['domains']['rcr_outlet']
        defect=check_rcr_history(run,'curved',model,h)
        flux=face_flux(directory,f,geometry)
        expected=[h[-1]['endpoint_inlet_flow'],h[-1]['endpoint_rcr_flow']]
        if max(abs(x-y) for x,y in zip(flux.values(),expected))>2e-12:
            raise ValueError('Reconstructed inlet or outlet flux differs from its history')
        reports.append(dict(ranks=rank_count,geometry=geometry,cap_flow=flux,
                            maximum_circuit_defect=defect,min_fluid_j=min(r['endpoint_min_fluid_j'] for r in h),
                            min_solid_j=min(r['endpoint_min_solid_j'] for r in h),
                            maximum_mass_defect=max(abs(r['stage_mass_residual']) for r in h),
                            maximum_support_energy=max(r['endpoint_support_spring_energy'] for r in h)))
        fields.append(f);histories.append(h);runners.append(run);configs.append(cfg)
    field_errors=frame_difference(*fields,DIRECTION,ORIGIN)
    keys=('stage_inlet_flow','endpoint_inlet_flow','stage_rcr_flow','endpoint_rcr_flow','stage_rcr_pressure',
          'endpoint_rcr_pressure','endpoint_capacitor_pressure','stage_volume','endpoint_volume',
          'endpoint_support_spring_energy','stage_support_dissipation','endpoint_min_fluid_j','endpoint_min_solid_j')
    history_errors={k:max(abs(a[k]-b[k]) for a,b in zip(*histories)) for k in keys}
    if max(history_errors.values())>2e-10:raise ValueError(f'Frame-dependent scalar history: {history_errors}')
    result=dict(steps=steps,meshes=reports,field_errors=field_errors,history_errors=history_errors,
                executable_sha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest())
    if extended:
        # Legacy cardinal axis and an equivalent scaled direction share a checkpoint identity.
        checkpoint=Path(work).resolve()/'axis-checkpoint'
        base=configs[0];runners[0].solve('start-axis',base,1,['-checkpoint',checkpoint,'-stop_after',steps//2])
        equivalent=copy.deepcopy(base)
        flow=equivalent['fsi']['inlet']['flow_rate'];del flow['axis'];flow['direction']=[2.,0.,0.]
        resumed,tail,_=runners[0].solve('finish-direction',equivalent,1,['-restart',checkpoint])
        delta=error(fields[0],resumed)
        if delta>2e-9 or abs(tail[-1]['endpoint_rcr_pressure']-histories[0][-1]['endpoint_rcr_pressure'])>1e-12:
            raise ValueError('Changing from a legacy axis to its equivalent direction changed the restart')
        result['axis_restart_field_error']=delta
        for label,changes,message in (
                ('dual',dict(axis=0),'excludes axis'),('zero',dict(direction=[0,0,0]),'must be nonzero'),
                ('width',dict(direction=[1,2]),'requires three components'),
                ('reverse',dict(direction=[-x for x in DIRECTION]),'oppose the outward normal'),
                ('tilt',dict(direction=[1,0,0]),'outside circle plane')):
            invalid=copy.deepcopy(configs[1]);invalid['fsi']['inlet']['flow_rate'].update(changes)
            runners[1].solve('invalid-'+label,invalid,ranks,fail=message)
        if steps>=16 and min(r['endpoint_inlet_flow'] for r in histories[1])>=0:
            raise ValueError('Expected actual inlet reversal')
    return result


def sampled_inlet(exe,mpi,work,mesh=(8,1,3),ranks=2):
    """Drive an oblique cap across a knot, a reversal, and the periodic seam."""
    directory=Path(work)
    cfg=json.loads(generate(directory,sectors=mesh[0],radial=mesh[1],axial=mesh[2],
                            direction=DIRECTION,origin=ORIGIN).read_text())
    geometry=json.loads((directory/'geometry.json').read_text())
    run=Runner(exe,mpi,directory,interface_area=geometry['interface_area'])
    unit=1/1024
    increments=(2,3,2,3,2,3,1,2,3,2,3,2,3)
    f=cfg['fsi']
    f.update(steps=len(increments),dt=sum(increments)*unit/len(increments),output_interval=len(increments))
    cfg['time_control']=dict(step_sizes=[v*unit for v in increments])
    q=f['inlet']['flow_rate']
    del q['mean'],q['amplitude']
    q.update(period=16*unit,samples=[[t*unit,value] for t,value in
             [(0,.001),(2,.010),(5,.004),(9,-.003),(13,.0018)]])
    f['inlet']['ramp_time']=4*unit

    def expected(time):
        x=(time/unit)%16
        if x<=2:value=.001+.0045*x
        elif x<=5:value=.010-.002*(x-2)
        elif x<=9:value=.004-.00175*(x-5)
        elif x<=13:value=-.003+.0012*(x-9)
        else:value=.0018-.0008*(x-13)/3
        ramp=min(time/(4*unit),1.)
        return ramp**3*(10-15*ramp+6*ramp**2)*value

    report={}
    model=f['domains']['rcr_outlet']
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time']=dict(scheme=scheme,rho_infinity=.5) if scheme=='generalized_alpha' else dict(scheme=scheme)
        count=1 if scheme=='be' else ranks
        fields,rows,_=run.solve('samples-'+scheme,cfg,count)
        assert len(rows)==len(increments)
        endpoint=stage=0.
        for i,row in enumerate(rows):
            t=row['time'];old=t-row['accepted_dt']
            assert t==sum(increments[:i+1])*unit
            weight=2/3 if i and scheme=='generalized_alpha' else 1.
            target=expected(t)
            endpoint=max(endpoint,abs(row['endpoint_inlet_flow']-target),abs(row['target_endpoint_flow']-target))
            stage=max(stage,abs(row['stage_inlet_flow']-((1-weight)*expected(old)+weight*target)))
        assert min(row['endpoint_inlet_flow'] for row in rows)<0
        caps=face_flux(directory,fields,geometry)
        cap_error=max(abs(caps[1]-expected(rows[-1]['time'])),abs(caps[2]-rows[-1]['endpoint_rcr_flow']))
        assert max(stage,endpoint,cap_error)<2e-12
        report[scheme]=dict(ranks=count,stage_error=stage,endpoint_error=endpoint,final_cap_error=cap_error,
                            circuit_residual=check_rcr_history(run,'samples-'+scheme,model,rows))
    checkpoint=directory/'waveform-checkpoint'
    run.solve('samples-start',cfg,ranks,['-checkpoint',checkpoint,'-stop_after',6])
    explicit=copy.deepcopy(cfg)
    explicit['fsi']['inlet']['flow_rate']['samples'].append([16*unit,.001])
    resumed,_,_=run.solve('samples-resume',explicit,ranks,['-restart',checkpoint])
    report['equivalent_closure_restart_error']=error(fields,resumed)
    assert report['equivalent_closure_restart_error']<2e-9
    changed=copy.deepcopy(cfg)
    changed['fsi']['inlet']['flow_rate']['samples'][2][1]+=.0003
    run.solve('samples-changed',changed,ranks,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    constant=copy.deepcopy(cfg)
    del constant['time_control']
    constant['fsi'].update(steps=3,dt=2*unit,output_interval=3)
    source=constant['fsi']['inlet'];source['ramp_time']=0.
    source['flow_rate']['samples']=[[0.,.001]]
    measured,_,_=run.solve('samples-constant',constant)
    del source['flow_rate']['samples']
    source['flow_rate'].update(mean=.001,amplitude=0.)
    original,_,_=run.solve('sinusoid-constant',constant)
    report['constant_wave_field_error']=error(measured,original)
    assert report['constant_wave_field_error']<2e-9
    for label,changes,reason in (
            ('dual',dict(amplitude=0.),'excludes mean and amplitude'),
            ('empty',dict(samples=[]),'requires time/flow pairs'),
            ('width',dict(samples=[[0,0,0]]),'requires time/flow pairs'),
            ('start',dict(samples=[[unit,0]]),'from zero'),
            ('duplicate',dict(samples=[[0,0],[unit,1],[unit,2]]),'increasing times'),
            ('outside',dict(samples=[[0,0],[17*unit,1]]),'within one period'),
            ('finite',dict(samples=[[0,'.inf']]),'finite flows'),
            ('closure',dict(samples=[[0,0],[16*unit,.1]]),'two ends')):
        invalid=copy.deepcopy(cfg)
        invalid['fsi']['inlet']['flow_rate'].update(changes)
        path=directory/('invalid-'+label+'.json')
        path.write_text(json.dumps(invalid))
        run.command([run.exe,'-case',path,'-prepare',directory/('invalid-parts-'+label),'-parts',1],
                    'reject-samples-'+label,fail=reason)
    return report


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--executable',type=Path,required=True);cli.add_argument('--mpiexec',required=True)
    cli.add_argument('--work',type=Path,required=True);cli.add_argument('--ranks',type=int,default=2)
    cli.add_argument('--mesh',type=int,nargs=3,default=(12,2,6))
    cli.add_argument('--steps',type=int,help='Harmonic fixture, default 20')
    cli.add_argument('--sampled',action='store_true',help='Use the nonuniform periodic inlet and its fixed 13-step schedule')
    args=cli.parse_args()
    if args.sampled:
        if args.steps is not None:cli.error('The sampled fixture prescribes a fixed variable-step schedule')
        result=sampled_inlet(args.executable,args.mpiexec,args.work,args.mesh,args.ranks)
    else:
        result=pair(args.executable,args.mpiexec,args.work,args.mesh,20 if args.steps is None else args.steps,args.ranks,True)
    (args.work/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(result if args.sampled else (result['field_errors'],result['axis_restart_field_error']),flush=True)


if __name__=='__main__':main()
