"""Uniform-flow preservation, analytic mesh velocity and ALE history restart."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True)
    p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--alpha',action='store_true')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    mesh=a.work/'cube.msh';write_mesh(mesh,2)
    def run(command):
        r=subprocess.run(list(map(str,command)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout[-6000:])
        return r.stdout
    def solve(mode,scheme,h,label,ranks=1,extra=(),schedule=None,rho=.5,events=None,amplitude=.1,retries=0):
        case=a.work/f'{label}.json';out=a.work/f'{label}.vtu'
        cfg=dict(mesh=str(mesh.resolve()),output=str(out.resolve()),time=dict(scheme=scheme),
                 motion=dict(mode=mode,amplitude=amplitude,speed=.2,dt=h,steps=round(.5/h)),
                 solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13))
        if scheme=='generalized_alpha':cfg['time']['rho_infinity']=rho
        cfg['time_control']={}
        if schedule:cfg['time_control']['step_sizes']=schedule
        if events:cfg['time_control']['events']=events
        if retries:cfg['time_control'].update(max_retries=retries,minimum_dt=1e-8)
        case.write_text(json.dumps(cfg));part=a.work/f'parts{ranks}'
        if not part.exists():run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra])
        (a.work/f'{label}.log').write_text(text)
        errors=list(map(float,re.findall(r'velocity_max_error=(\S+)',text)))
        assert errors and max(errors)<1e-10
        assert min(map(float,re.findall(r'min_volume=(\S+)',text)))>0
        values={};center_velocity=None
        for rank in range(ranks):
            path=out if ranks==1 else out.with_name(out.stem+f'_rank{rank}.vtu')
            tree=ET.parse(path)
            fields={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
            points=list(map(float,tree.find('.//Points/DataArray').text.split()))
            for i,node in enumerate(fields['mesh_node_id']):
                if int(fields['owner'][i])!=rank:continue
                values[int(node)]=[fields['pressure'][i]]+sum([fields[n][3*i:3*i+3] for n in ('velocity','mesh_displacement','mesh_velocity')],[])
                if scheme=='generalized_alpha':
                    values[int(node)]+=sum([fields[n][3*i:3*i+3] for n in ('fluid_algorithmic_acceleration','mesh_algorithmic_acceleration')],[])
                assert abs(fields['pressure'][i])<1e-10
                ref=[points[3*i+c]-fields['mesh_displacement'][3*i+c] for c in range(3)]
                if sum(abs(x-.5) for x in ref)<1e-12:center_velocity=fields['mesh_velocity'][3*i]
        assert center_velocity is not None
        return values,center_velocity
    evidence=[]
    methods=[('generalized_alpha',rho) for rho in (0.,.5,1.)] if a.alpha else [('be',.5),('bdf2',.5)]
    for scheme,rho in methods:
        previous=0
        for h in ((.0625,.03125,.015625) if a.alpha else (.1,.05,.025)):
            _,velocity=solve('uniform',scheme,h,f'{scheme}-{rho}-{h}',rho=rho)
            error=abs(velocity-.1*math.cos(.5));row=dict(scheme=scheme,rho=rho,h=h,mesh_velocity_error=error)
            if previous:
                order=math.log(previous/error,2);row['order']=order
                assert order>(.8 if scheme=='be' else 1.8),row
            previous=error;evidence.append(row);print(row,flush=True)
    def compare(x,y):
        assert x.keys()==y.keys()
        assert max(abs(v-w) for node in x for v,w in zip(x[node],y[node]))<2e-10
    for mode in ('uniform','shear'):
        scheme='generalized_alpha' if a.alpha else 'bdf2'
        schedule=[.08,.12]*3
        base,_=solve(mode,scheme,.1,f'{mode}-base',schedule=schedule)
        for ranks in (1,2,4):
            full,_=solve(mode,scheme,.1,f'{mode}-{ranks}',ranks,schedule=schedule);compare(base,full)
            checkpoint=a.work/f'checkpoint-{mode}-{ranks}'
            solve(mode,scheme,.1,f'{mode}-partial-{ranks}',ranks,extra=['-checkpoint',checkpoint,'-stop_after',2],schedule=schedule)
            resumed,_=solve(mode,scheme,.1,f'{mode}-resumed-{ranks}',ranks,extra=['-restart',checkpoint],schedule=schedule)
            compare(full,resumed)
    if a.alpha:
        for ranks in (1,2,4):
            checkpoint=a.work/f'event-{ranks}'
            full,_=solve('uniform','generalized_alpha',.1,f'event-full-{ranks}',ranks,events=[.2])
            solve('uniform','generalized_alpha',.1,f'event-part-{ranks}',ranks,events=[.2],extra=['-checkpoint',checkpoint,'-stop_after',2])
            resumed,_=solve('uniform','generalized_alpha',.1,f'event-resumed-{ranks}',ranks,events=[.2],extra=['-restart',checkpoint])
            compare(full,resumed)
            text=(a.work/f'event-resumed-{ranks}.log').read_text()
            assert 'time_order=1' in text.split('ale_step=3',1)[1].splitlines()[0]
    if a.alpha:
        for ranks in (1,2,4):
            # The center's endpoint moves past x=1, but its alpha stage remains
            # inside the cube. A half step is admissible and must recover.
            retry,_=solve('uniform','generalized_alpha',.1,f'geometry-retry-{ranks}',ranks,
                          schedule=[.01,.49],rho=1,amplitude=1.1,retries=2,extra=['-stop_after',2])
            text=(a.work/f'geometry-retry-{ranks}.log').read_text()
            assert 'reason=Invalid generalized-alpha ALE endpoint geometry' in text,text
            direct,_=solve('uniform','generalized_alpha',.1,f'geometry-direct-{ranks}',ranks,
                           schedule=[.01,.245],rho=1,amplitude=1.1,extra=['-stop_after',2])
            compare(retry,direct)
            checkpoint=a.work/f'geometry-checkpoint-{ranks}'
            solve('uniform','generalized_alpha',.1,f'geometry-part-{ranks}',ranks,
                  schedule=[.01,.49],rho=1,amplitude=1.1,extra=['-checkpoint',checkpoint,'-stop_after',1])
            snapshot=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.rglob('*') if p.is_file()}
            before=snapshot()
            try:
                solve('uniform','generalized_alpha',.1,f'geometry-fail-{ranks}',ranks,
                      schedule=[.01,.49],rho=1,amplitude=1.1,extra=['-checkpoint',checkpoint,'-restart',checkpoint])
            except RuntimeError as error:
                assert 'Invalid generalized-alpha ALE endpoint geometry' in str(error)
            else:raise AssertionError('Inverted endpoint was accepted')
            assert snapshot()==before
        bad_ranks=0
        for rank in range(4):
            tree=ET.parse(a.work/f'geometry-retry-4_rank{rank}.vtu')
            xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
            disp=list(map(float,tree.find('.//PointData/DataArray[@Name="mesh_displacement"]').text.split()))
            xyz=[x-d for x,d in zip(xyz,disp)]
            for i in range(len(xyz)//3):
                if sum(abs(xyz[3*i+j]-.5) for j in range(3))<1e-12:xyz[3*i]+=1.1*math.sin(.5)
            cells=list(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            bad=False
            for k in range(0,len(cells),4):
                u,v,w=[[xyz[3*cells[k+i]+j]-xyz[3*cells[k]+j] for j in range(3)] for i in (1,2,3)]
                determinant=u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0])
                bad|=determinant<=0
            bad_ranks+=bad
        assert 0<bad_ranks<4,bad_ranks
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
