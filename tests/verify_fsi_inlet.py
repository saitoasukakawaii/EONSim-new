"""Nonzero inlet, accepted observations and endpoint/history contracts."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_wall import generate


class Runner:
    def __init__(self,exe,mpi,work,timeout=600):
        self.timeout=timeout;self.exe=str(Path(exe).resolve());self.mpi=mpi;self.work=Path(work).resolve();self.work.mkdir(parents=True,exist_ok=True)
    def command(self,args,label,fail=None):
        r=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=self.timeout)
        (self.work/(label+'.log')).write_text(r.stdout)
        if fail: assert r.returncode!=0 and fail in r.stdout,r.stdout[-5000:]
        else: assert r.returncode==0,r.stdout[-5000:]
        return r.stdout
    def solve(self,label,cfg,ranks=1,extra=(),fail=None):
        cfg=copy.deepcopy(cfg);cfg['output']=str(self.work/(label+'.vtu'))
        case=self.work/(label+'.json');case.write_text(json.dumps(cfg))
        part=self.work/f'part-{ranks}'
        if not part.exists():self.command([self.exe,'-case',case,'-prepare',part,'-parts',ranks],label+'-prepare')
        log=self.command([self.mpi,'-n',ranks,self.exe,'-case',case,'-partition',part,*extra],label,fail)
        if fail:return {},[],log
        fields={}
        for solid in (False,True):
            for rank in range(ranks):
                suffix=('_solid' if solid else '')+(f'_rank{rank}' if ranks>1 else '')+'.vtu'
                tree=ET.parse(self.work/(label+suffix))
                arrays={a.attrib['Name']:(int(a.attrib.get('NumberOfComponents',1)),list(map(float,a.text.split()))) for a in tree.findall('.//PointData/DataArray')}
                used=set(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
                xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
                for i in used:
                    node=int(arrays['mesh_node_id'][1][i]);fields[(solid,node,'coordinates')]=xyz[3*i:3*i+3]
                    for name,(width,values) in arrays.items():
                        if name in ('owner','mesh_node_id','algebra_node_id'):continue
                        key=(solid,node,name);value=values[width*i:width*(i+1)]
                        if key in fields:assert max(abs(v-w) for v,w in zip(fields[key],value))<2e-9
                        fields[key]=value
        hist=self.work/(label+'.csv')
        if '-restart' in extra:
            candidates=list(self.work.glob(label+'_restart*.csv'));assert len(candidates)==1;hist=candidates[0]
        rows=[]
        if cfg['fsi'].get('output_interval',0):
            with hist.open() as source:rows=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(source)]
            assert len(rows)==len(re.findall('fsi_step=',log))
            for row in rows:
                assert all(math.isfinite(v) for v in row.values()),row
                assert abs(row['reference_interface_area']-1)<1e-12,row
                assert abs(row['evaluation_body_balance'])<2e-9,row
                assert abs(row['evaluation_power_balance'])<2e-9,row
                assert min(row[k] for k in row if k.endswith('_j'))>0,row
        return fields,rows,log


def error(a,b):
    assert a.keys()==b.keys()
    return max(abs(v-w) for k in a for v,w in zip(a[k],b[k]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    a=p.parse_args();run=Runner(a.executable,a.mpiexec,a.work)
    base=json.loads(generate(run.work).read_text());base['fsi'].update(steps=20,output_interval=1,stabilization_tau=.05)
    base['solver'].update(relative_tolerance=1e-11,absolute_tolerance=1e-13)
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg=copy.deepcopy(base);cfg['time']=dict(scheme=scheme)
        cfg['time_control']=dict(step_sizes=[.0015,.0025]*10)
        one,rows,_=run.solve(scheme+'-one',cfg)
        two,_,_=run.solve(scheme+'-two',cfg,2)
        assert error(one,two)<2e-9
        assert max(abs(r['area_displacement_y']) for r in rows)>1e-6
        # Check every accepted endpoint, including startup; fixed inlet coordinates.
        for row in rows:
            tree=ET.parse(run.work/f'{scheme}-one_step{int(row["step"])}.vtu')
            xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
            velocity=list(map(float,tree.find('.//PointData/DataArray[@Name="velocity"]').text.split()))
            x=min(1,row['time']/.02);scale=x**3*(10-15*x+6*x*x)
            for i in range(len(xyz)//3):
                if abs(xyz[3*i])<1e-12 and xyz[3*i+1]<=1:
                    assert abs(velocity[3*i]-.1*(1-xyz[3*i+1])*scale)<1e-12
                    assert max(abs(v) for v in velocity[3*i+1:3*i+3])<1e-12
        for stop in (3,13):
            checkpoint=run.work/f'{scheme}-checkpoint{stop}'
            run.solve(f'{scheme}-part{stop}',cfg,2,['-checkpoint',checkpoint,'-stop_after',stop])
            resumed,_,_=run.solve(f'{scheme}-resume{stop}',cfg,2,['-restart',checkpoint])
            assert error(two,resumed)<2e-9
        changed=copy.deepcopy(cfg);changed['fsi']['inlet']['value'][0]=.2;changed['fsi']['inlet']['gradient'][0][1]=-.2
        run.solve(scheme+'-mismatch',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    for material in ('linear','neo_hookean'):
        cfg=copy.deepcopy(base);cfg['fsi']['material']=material
        _,_,log=run.solve('jac-'+material,cfg,2,['-stop_after',3,'-snes_test_jacobian'])
        ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)))
        assert ratios and max(ratios)<1e-6,ratios
    for label,change,message in [
        ('pressure-tag',lambda c:c['fsi']['inlet'].update(tag=2),'Invalid FSI inlet'),
        ('moving-trace',lambda c:c['fsi']['inlet'].update(value=[.2,0,0]),'conflicts with homogeneous/interface'),
        ('negative-ramp',lambda c:c['fsi']['inlet'].update(ramp_time=-1),'Invalid FSI inlet'),
        ('absent-tag',lambda c:c['fsi']['inlet'].update(tag=99),'boundary tag missing')]:
        cfg=copy.deepcopy(base);change(cfg);run.solve(label,cfg,2,fail=message)
    cfg=copy.deepcopy(base);cfg['fsi']['inlet']['ramp_time']=0
    run.solve('zero-ramp',cfg,2,['-stop_after',3])
    for scheme in ('bdf2','generalized_alpha'):
        cfg=copy.deepcopy(base);cfg['time']=dict(scheme=scheme)
        cfg['fsi'].update(material='neo_hookean',dt=.004,steps=10)
        cfg['fsi']['inlet'].update(value=[2,0,0],gradient=[[0,-2,0],[0,0,0],[0,0,0]])
        checkpoint=run.work/('inlet-retry-'+scheme)
        run.solve('inlet-start-'+scheme,cfg,2,['-checkpoint',checkpoint,'-stop_after',2])
        cfg['time_control']=dict(max_retries=16,minimum_dt=1e-10,reduction=.5)
        actual,rows,text=run.solve('inlet-retry-'+scheme,cfg,2,['-restart',checkpoint,'-snes_max_it',2,'-stop_after',3])
        assert 'step_retry=' in text and len(rows)==1
        cfg['time_control']['step_sizes']=[.004,.004,rows[0]['accepted_dt']]
        replay,_,_=run.solve('inlet-replay-'+scheme,cfg,2,['-stop_after',3])
        assert error(actual,replay)<2e-9
    # Real alpha stage converges, but its extrapolated endpoint inverts the ALE mesh.
    # A failed continuation must leave every checkpoint file byte-identical.
    import hashlib
    endpoint=Runner(a.executable,a.mpiexec,run.work/'endpoint')
    cfg=json.loads(generate(endpoint.work).read_text())
    cfg['fsi']=dict(body='rigid',dt=.5,steps=5,pressure=-10,pressure_time=dict(amplitude=20,period=2),output_interval=1)
    cfg['time']=dict(scheme='generalized_alpha',rho_infinity=1)
    cfg['solver']=dict(relative_tolerance=1e-10,absolute_tolerance=1e-12,maximum_iterations=60)
    cfg['output']=str(endpoint.work/'endpoint.vtu')
    case=endpoint.work/'case.json';case.write_text(json.dumps(cfg));part=endpoint.work/'part';checkpoint=endpoint.work/'checkpoint'
    endpoint.command([endpoint.exe,'-case',case,'-prepare',part,'-parts',2],'prepare')
    cmd=[endpoint.mpi,'-n',2,endpoint.exe,'-case',case,'-partition',part]
    endpoint.command(cmd+['-checkpoint',checkpoint,'-stop_after',3],'accepted')
    digest=lambda:{str(p.relative_to(checkpoint)):hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.rglob('*') if p.is_file()}
    before=digest()
    cfg['output']=str(endpoint.work/'failed.vtu');case.write_text(json.dumps(cfg))
    endpoint.command(cmd+['-restart',checkpoint,'-checkpoint',checkpoint],'inverted',fail='Invalid FSI endpoint geometry')
    assert digest()==before
    with (endpoint.work/'failed_restart3.csv').open() as f:assert not list(csv.DictReader(f))
    assert not (endpoint.work/'failed_restart3.pvd').exists()
    cfg['output']=str(endpoint.work/'recovered.vtu')
    cfg['time_control']=dict(max_retries=16,minimum_dt=.0001,reduction=.5);case.write_text(json.dumps(cfg))
    text=endpoint.command(cmd+['-restart',checkpoint,'-stop_after',4],'retried')
    assert 'step_retry=' in text
    with (endpoint.work/'recovered_restart3.csv').open() as f:row=list(csv.DictReader(f))
    assert len(row)==1 and int(row[0]['step'])==4 and float(row[0]['endpoint_min_fluid_j'])>0
    cfg['time_control']['step_sizes']=[.5,.5,.5,float(row[0]['accepted_dt'])];case.write_text(json.dumps(cfg))
    endpoint.command(cmd+['-stop_after',4],'replay')
    with (endpoint.work/'recovered.csv').open() as f:replayed=list(csv.DictReader(f))[-1]
    for key in ('endpoint_position','endpoint_velocity'):
        assert abs(float(row[0][key])-float(replayed[key]))<2e-9
    print('FSI inlet three schemes, startup/endpoints, MPI, histories, diagnostics and Jacobians passed')


if __name__=='__main__':main()
