"""Periodic prescribed volume flux and independent moving-domain mass diagnostics."""
import argparse
import copy
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from verify_fsi_inlet import Runner, check_rcr_history, error, generate


def reflected_field_error(left, right):
    """Match independent mesh IDs by reference position and transform all vectors under y reflection."""
    def index(fields):
        nodes={}
        for (solid,node,key),pos in fields.items():
            if key!='coordinates':continue
            disp=fields[solid,node,'displacement' if solid else 'mesh_displacement']
            ref=tuple(round(x-d,12) for x,d in zip(pos,disp))
            assert (solid,*ref) not in nodes
            nodes[solid,*ref]=node
        return nodes
    a,b=index(left),index(right)
    assert a.keys()==b.keys() and left.keys()==right.keys()
    node_map={(solid,n):b[solid,x,-y,z] for (solid,x,y,z),n in a.items()}
    worst=0.
    for (solid,node,key),value in left.items():
        other=right[solid,node_map[solid,node],key]
        reflected=[v if j!=1 else -v for j,v in enumerate(value)]
        worst=max(worst,max(abs(u-v) for u,v in zip(other,reflected)))
    return worst


def verify_branched_outlets(exe,mpi,work):
    import generate_branched
    cfg=json.loads(generate_branched.generate(work).read_text())
    geometry=json.loads((work/'geometry.json').read_text())
    run=Runner(exe,mpi,work,interface_area=geometry['interface_area'])
    cfg['fsi'].update(steps=12,output_interval=12)
    models=cfg['fsi']['domains']['rcr_outlets']
    def check(label,model_list,rows,restart=None):
        circuit=max(check_rcr_history(run,label,p,rows,restart=restart,sole_pressure=False) for p in model_list)
        for row in rows:
            for stage in ('stage','endpoint'):
                total=sum(row[f"{stage}_rcr_flow_{p['tag']}"] for p in model_list)
                assert abs(total-row[stage+'_outlet_flow'])<2e-12
            assert abs(row['stage_mass_residual'])<2e-9
        return circuit
    symmetric,rows,_=run.solve('symmetric',cfg,1)
    circuit=check('symmetric',models,rows)
    assert max(abs(r['stage_rcr_flow_2']-r['stage_rcr_flow_3']) for r in rows)<2e-12
    assert rows[-1]['endpoint_rcr_flow_2']>1e-6
    assert max(abs(r['endpoint_wall_flux']) for r in rows)>1e-5
    symmetric_error=reflected_field_error(symmetric,symmetric)
    assert symmetric_error<2e-9, symmetric_error

    cfg['time_control']=dict(step_sizes=[.01,.01,.008,.012]*3)
    harder=dict(proximal_resistance=12.,distal_resistance=32.,compliance=.00625)
    models[0].update(harder)
    one,one_rows,_=run.solve('unequal-one',cfg)
    two,rows,_=run.solve('unequal-two',cfg,2)
    assert error(one,two)<2e-9
    check('unequal-two',models,rows)
    assert abs(rows[-1]['endpoint_rcr_pressure_2']-rows[-1]['endpoint_rcr_pressure_3'])>1e-6
    swapped=copy.deepcopy(cfg)
    a,b=swapped['fsi']['domains']['rcr_outlets']
    a['tag'],b['tag']=b['tag'],a['tag']
    right,pair,_=run.solve('swapped-two',swapped,2)
    mirror_error=reflected_field_error(two,right)
    assert mirror_error<2e-9, mirror_error
    for r,s in zip(rows,pair):
        for t,u in [(2,3),(3,2)]:
            for field in ('stage_rcr_flow','stage_rcr_pressure','stage_capacitor_rate','endpoint_capacitor_pressure'):
                assert abs(r[f'{field}_{t}']-s[f'{field}_{u}'])<2e-9
    # Reordering the declarations leaves the same physical checkpoint and DoF numbering.
    checkpoint=work/'checkpoint'
    run.solve('checkpoint',cfg,2,['-checkpoint',checkpoint,'-stop_after',5])
    shuffled=copy.deepcopy(cfg)
    shuffled['fsi']['domains']['rcr_outlets'].reverse()
    resumed,tail,_=run.solve('resume',shuffled,2,['-restart',checkpoint])
    check('resume',models,tail,restart=5)
    assert error(two,resumed)<2e-9 and len(tail)==7
    for full,saved in zip(rows[5:],tail):
        for key in full:
            if 'rcr' in key or 'capacitor' in key:assert abs(full[key]-saved[key])<2e-9
    changed=copy.deepcopy(shuffled)
    changed['fsi']['domains']['rcr_outlets'][0]['distal_pressure']+=.04
    run.solve('changed-model',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')

    fd,_,log=run.solve('branch-fd',cfg,2,['-snes_test_jacobian','-stop_after',2])
    ratios=[float(v) for v in re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)]
    assert ratios and max(ratios)<1e-6
    hybrid,_,_=run.solve('branch-hybrid',cfg,2,['-pc_recipe','hybrid','-stop_after',2])
    assert error(hybrid,fd)<2e-8
    for mode,why in [('duplicate','Duplicate RCR outlet tag'),('empty','nonempty sequence'),
                     ('mixed','Specify one RCR outlet syntax'),('moving','stationary fluid exterior')]:
        bad=copy.deepcopy(cfg)
        dom=bad['fsi']['domains']
        if mode=='duplicate':dom['rcr_outlets'][1]['tag']=2
        if mode=='empty':dom['rcr_outlets']=[]
        if mode=='mixed':dom['rcr_outlet']=models[0]
        if mode=='moving':dom['mesh_constraints']=[bc for bc in dom['mesh_constraints'] if bc['tag']!=3]
        run.solve('invalid-'+mode,bad,2,fail=why)
    return dict(mpi=error(one,two),symmetric_field_error=symmetric_error,exchanged_field_error=mirror_error,
                restart_field_error=error(two,resumed),jacobian_relative_error=max(ratios),hybrid_field_error=error(hybrid,fd),
                circuit_residual=circuit,final_flows=[rows[-1]['endpoint_rcr_flow_2'],rows[-1]['endpoint_rcr_flow_3']],
                final_pressures=[rows[-1]['endpoint_rcr_pressure_2'],rows[-1]['endpoint_rcr_pressure_3']])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    a=p.parse_args(); run=Runner(a.executable,a.mpiexec,a.work)
    base=json.loads(generate(run.work,periodic_flow=True).read_text())
    base['fsi'].update(steps=20)
    base['fsi']['inlet']['ramp_time']=.004
    base['fsi']['inlet']['flow_rate']['period']=.02
    from verify_curved_fsi import pair as curved_pair
    report={"branched_outlets":verify_branched_outlets(a.executable,a.mpiexec,run.work/"branched"),
            "oriented_circular_inlet":curved_pair(a.executable,a.mpiexec,run.work/"curved",(8,1,3),3,2)}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg=copy.deepcopy(base);cfg['time']=dict(scheme=scheme)
        one,rows,_=run.solve(scheme+'-one',cfg)
        two,other,_=run.solve(scheme+'-two',cfg,2)
        assert error(one,two)<2e-9
        previous_q=0
        for index,r in enumerate(rows):
            t=r['time']; x=min(1,t/.004)
            target=x**3*(10-15*x+6*x*x)*(.01+.005*math.sin(2*math.pi*t/.02))
            assert abs(r['endpoint_inlet_flow']-target)<1e-12
            af=2/3 if scheme=='generalized_alpha' and index else 1
            assert abs(r['stage_inlet_flow']-((1-af)*previous_q+af*target))<1e-12
            previous_q=target
            tree=ET.parse(run.work/f'{scheme}-one_step{int(r["step"])}.vtu')
            xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
            arrays={n.attrib['Name']:list(map(float,n.text.split())) for n in tree.findall('.//PointData/DataArray')}
            solid=ET.parse(run.work/f'{scheme}-one_step{int(r["step"])}_solid.vtu')
            sv=list(map(float,solid.find('.//PointData/DataArray[@Name="velocity"]').text.split()))
            sd=list(map(float,solid.find('.//PointData/DataArray[@Name="displacement"]').text.split()))
            used=set(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            for i in used:
                ref=[xyz[3*i+c]-arrays['mesh_displacement'][3*i+c] for c in range(3)]
                if abs(ref[1])<1e-12 or min(abs(ref[2]),abs(ref[2]-1))<1e-12:
                    assert max(abs(v) for v in arrays['velocity'][3*i:3*i+3])<1e-12
                if abs(ref[1]-1)<1e-12:
                    assert max(abs(arrays['velocity'][3*i+c]-sv[3*i+c]) for c in range(3))<1e-12
                    assert max(abs(arrays['mesh_displacement'][3*i+c]-sd[3*i+c]) for c in range(3))<1e-12
            assert abs(r['endpoint_inlet_flow']-r['target_endpoint_flow'])<1e-12,r
            assert abs(r['stage_mass_residual']+r['stage_divergence'])<1e-12,r
            assert abs(r['stage_mass_residual'])<1e-9,r
        assert max(abs(r['area_displacement_y']) for r in rows)>1e-8
        report[scheme]={k:max(abs(r[k]) for r in rows) for k in ('stage_mass_residual','secant_mass_residual','area_displacement_y')}
        checkpoint=run.work/(scheme+'-checkpoint')
        run.solve(scheme+'-part',cfg,2,['-checkpoint',checkpoint,'-stop_after',7])
        resumed,tail,_=run.solve(scheme+'-resume',cfg,2,['-restart',checkpoint])
        assert error(two,resumed)<2e-9
        for expected,actual in zip(other[7:],tail):
            assert max(abs(expected[k]-actual[k]) for k in expected if k not in ('snes_iterations','residual'))<2e-9
        changed=copy.deepcopy(cfg);changed['fsi']['inlet']['flow_rate']['amplitude']*=2
        run.solve(scheme+'-mismatch',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    cfg=copy.deepcopy(base);cfg['fsi']['material']='neo_hookean'
    _,_,log=run.solve('jacobian',cfg,2,['-stop_after',3,'-snes_test_jacobian'])
    ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)))
    assert ratios and max(ratios)<1e-6,ratios
    for label,change,message in [
        ('period',lambda c:c['fsi']['inlet']['flow_rate'].update(period=0),'Invalid FSI flow_rate'),
        ('axis',lambda c:c['fsi']['inlet']['flow_rate'].update(axis=3),'Invalid FSI flow_rate'),
        ('bounds',lambda c:c['fsi']['inlet']['flow_rate'].update(upper=[0,0,1]),'Invalid FSI flow_rate rectangle'),
        ('affine',lambda c:c['fsi']['inlet'].update(value=[1,0,0]),'excludes affine inlet'),
        ('outside',lambda c:c['fsi']['inlet']['flow_rate'].update(upper=[0,.5,1]),'outside rectangle')]:
        bad=copy.deepcopy(base);change(bad);run.solve('invalid-'+label,bad,2,fail=message)
    # Real nonlinear failure, not an injected rejection: resume from the same accepted history.
    cfg=copy.deepcopy(base);cfg['fsi'].update(material='neo_hookean',dt=.004,steps=10)
    cfg['fsi']['inlet']['flow_rate'].update(mean=.2,amplitude=.1)
    cfg['time']=dict(scheme='generalized_alpha')
    checkpoint=run.work/'retry-checkpoint'
    run.solve('retry-start',cfg,2,['-checkpoint',checkpoint,'-stop_after',2])
    cfg['time_control']=dict(max_retries=16,minimum_dt=1e-10,reduction=.5)
    actual,rows,log=run.solve('retry',cfg,2,['-restart',checkpoint,'-snes_max_it',2,'-stop_after',3])
    assert 'step_retry=' in log and len(rows)==1
    cfg['time_control']['step_sizes']=[.004,.004,rows[0]['accepted_dt']]
    replay,_,_=run.solve('retry-replay',cfg,2,['-stop_after',3])
    assert error(actual,replay)<2e-9
    coarse=Runner(a.executable,a.mpiexec,run.work/'coarse')
    coarse_cfg=json.loads(generate(coarse.work,n=1,periodic_flow=True).read_text())
    coarse.solve('zero-profile',coarse_cfg,2,fail='zero discrete profile flux')
    immediate=copy.deepcopy(base);immediate['fsi']['inlet']['ramp_time']=0
    _,immediate_rows,_=run.solve('zero-ramp',immediate,2,['-stop_after',3])
    assert all(abs(r['endpoint_inlet_flow']-(.01+.005*math.sin(2*math.pi*r['time']/.02)))<1e-12 for r in immediate_rows)
    report['jacobian_relative_error']=max(ratios)
    report['retry_accepted_dt']=rows[0]['accepted_dt']
    (run.work/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
