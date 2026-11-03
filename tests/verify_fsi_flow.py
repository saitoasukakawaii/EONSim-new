"""Periodic prescribed volume flux and independent moving-domain mass diagnostics."""
import argparse
import copy
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from verify_fsi_inlet import Runner, error, generate


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    a=p.parse_args(); run=Runner(a.executable,a.mpiexec,a.work)
    base=json.loads(generate(run.work,periodic_flow=True).read_text())
    base['fsi'].update(steps=20)
    base['fsi']['inlet']['ramp_time']=.004
    base['fsi']['inlet']['flow_rate']['period']=.02
    report={}
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
