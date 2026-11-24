"""Verify tag-resolved RCR circuits and shared wall constraints on the elastic T-junction."""
import argparse
import copy
import json
import re
from pathlib import Path

from verify_fsi_inlet import Runner, check_rcr_history, error


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


def verify_interface_constraints(run,config):
    cfg=copy.deepcopy(config)
    cfg['fsi'].update(steps=3,output_interval=3)
    dom=cfg['fsi']['domains']
    solid_tag,fluid_tag=dom['solid_interface'],dom['fluid_interface']
    dom['solid_constraints'].append(dict(tag=solid_tag,components=[1]))
    fields,_,_=run.solve('interface-slide',cfg,2)
    ids=[n for (solid,n,name) in fields if solid and name=='velocity' and (False,n,'velocity') in fields]
    assert ids
    names=[(True,'velocity'),(True,'displacement'),(False,'velocity'),(False,'mesh_displacement')]
    for solid,name in names:
        assert all(abs(fields[solid,n,name][1])<1e-14 for n in ids)
    transverse=max(abs(fields[True,n,'displacement'][j]) for n in ids for j in (0,2))
    assert transverse>1e-10
    checkpoint=run.work/'sliding-interface-checkpoint'
    run.solve('slide-start',cfg,2,['-checkpoint',checkpoint,'-stop_after',1])
    resumed,_,_=run.solve('slide-resume',cfg,2,['-restart',checkpoint])
    restart_error=error(fields,resumed)
    assert restart_error<2e-9
    changed=copy.deepcopy(cfg)
    changed['fsi']['domains']['solid_constraints'][-1]['components']=[0,1]
    run.solve('slide-changed',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    dom['fluid_constraints'].append(dict(tag=fluid_tag,components=[0,1,2]))
    dom['mesh_constraints'].append(dict(tag=fluid_tag,components=[0,1,2]))
    run.solve('incompatible-interface-master',cfg,2,fail='Interface constraints conflict with free structure component')
    dom['solid_constraints'][-1]['components']=[0,1,2]
    one,_,_=run.solve('interface-clamped-one',cfg)
    two,rows,_=run.solve('interface-clamped-two',cfg,2)
    assert error(one,two)<2e-9
    assert all(abs(v)<1e-14 for n in ids for solid,name in names for v in two[solid,n,name])
    volume_error=max(abs(r['endpoint_volume']-rows[0]['endpoint_volume']) for r in rows)
    flux_error=max(abs(r['endpoint_inlet_flow']-r['endpoint_outlet_flow']) for r in rows)
    assert volume_error<1e-12 and flux_error<2e-12
    return dict(partially_free_displacement=transverse,sliding_restart_error=restart_error,clamped_mpi_error=error(one,two),
                clamped_volume_change=volume_error,clamped_flux_error=flux_error)


def verify_branched_outlets(exe,mpi,work):
    import generate_branched
    cfg=json.loads(generate_branched.generate(work).read_text())
    geometry=json.loads((work/'geometry.json').read_text())
    run=Runner(exe,mpi,work,interface_area=geometry['interface_area'])
    constraints=verify_interface_constraints(run,cfg)
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
    return dict(interface_constraints=constraints,mpi=error(one,two),symmetric_field_error=symmetric_error,exchanged_field_error=mirror_error,
                restart_field_error=error(two,resumed),jacobian_relative_error=max(ratios),hybrid_field_error=error(hybrid,fd),
                circuit_residual=circuit,final_flows=[rows[-1]['endpoint_rcr_flow_2'],rows[-1]['endpoint_rcr_flow_3']],
                final_pressures=[rows[-1]['endpoint_rcr_pressure_2'],rows[-1]['endpoint_rcr_pressure_3']])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',required=True)
    parser.add_argument('--mpiexec',required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    report=verify_branched_outlets(args.executable,args.mpiexec,args.work)
    (args.work/'metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
