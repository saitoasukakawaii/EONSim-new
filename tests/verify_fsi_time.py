"""Monolithic FSI time refinement and variable-step history on real Tet4 solves."""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_domains import generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True)
    p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--checks',choices=['all','convergence','state'],default='all')
    p.add_argument('--alpha',action='store_true')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    base=json.loads(generate(a.work).read_text())
    def run(command,log=None):
        r=subprocess.run(list(map(str,command)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
        if log:log.write_text(r.stdout)
        if r.returncode: raise RuntimeError(r.stdout[-8000:])
        return r.stdout
    def solve(body,h,label,scheme=None,ranks=1,extra=(),schedule=None,nonlinear=False,retries=0,rho=.5,events=None):
        if scheme is None:scheme='generalized_alpha' if a.alpha else 'bdf2'
        cfg=copy.deepcopy(base)
        if body=='rigid': cfg['fsi']=dict(body='rigid',mass=2,damping=.3,stiffness=5,pressure=1)
        cfg['fsi'].update(dt=h,steps=round(.04/h),stabilization_tau=.05)
        if nonlinear:cfg['fsi'].update(material='neo_hookean',pressure=20)
        cfg['solver']=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30)
        cfg['time']=dict(scheme=scheme)
        if scheme=='generalized_alpha':cfg['time']['rho_infinity']=rho
        cfg['time_control']={}
        if events:cfg['time_control']['events']=events
        if schedule: cfg['time_control']['step_sizes']=schedule
        if retries:cfg['time_control'].update(max_retries=retries,minimum_dt=1e-10,reduction=.5)
        out=a.work/f'{label}.vtu';cfg['output']=str(out.resolve())
        case=a.work/f'{label}.json';case.write_text(json.dumps(cfg))
        part=a.work/f'part-{body}-{ranks}'
        if not part.exists():run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra],a.work/f'{label}.log')
        for name in ('body_balance','power_balance'):
            errors=list(map(float,re.findall(r'\b(?:stage_)?'+name+r'=(\S+)',text)))
            assert errors and max(abs(x) for x in errors)<2e-9,(name,errors)
        values={}
        for solid in ((False,True) if body=='elastic' else (False,)):
            for rank in range(ranks):
                suffix=('_solid' if solid else '')+(f'_rank{rank}' if ranks>1 else '')+'.vtu'
                tree=ET.parse(out.with_name(out.stem+suffix))
                fields={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
                for i,node in enumerate(fields['mesh_node_id']):
                    if int(fields['owner'][i])!=rank:continue
                    names=('velocity','displacement') if solid else ('velocity','pressure','mesh_displacement')
                    if scheme=='generalized_alpha':names+=(('algorithmic_acceleration',) if solid else ('mesh_velocity','fluid_algorithmic_acceleration','mesh_algorithmic_acceleration'))
                    for name in names:
                        width=1 if name=='pressure' else 3
                        values[(solid,int(node),name)]=fields[name][width*i:width*(i+1)]
        return values,text
    def error(x,y,name=None):
        assert {k for k in x if name is None or k[2]==name}=={k for k in y if name is None or k[2]==name}
        pairs=[(v,w) for key in x if name is None or key[2]==name for v,w in zip(x[key],y[key])]
        assert pairs
        return math.sqrt(sum((v-w)**2 for v,w in pairs)/len(pairs))
    evidence=[]
    for body in ('elastic','rigid'):
        if a.checks!='state':reference,_=solve(body,.00003125,f'{body}-reference',scheme='bdf2')
        for rho in ((0.,.5,1.) if a.alpha else (.5,)):
            previous={}
            for h in (() if a.checks=='state' else (.001,.0005,.00025)):
                actual,_=solve(body,h,f'{body}-{rho}-{h}',rho=rho)
                row=dict(body=body,rho=rho,h=h,scheme='generalized_alpha' if a.alpha else 'bdf2')
                for name in ('velocity','pressure','mesh_displacement'):
                    value=error(actual,reference,name);assert value>0 and math.isfinite(value)
                    row[name]=value
                    if name in previous:
                        order=math.log(previous[name]/value,2);row[name+'_order']=order
                        assert order>1.7,row
                    previous[name]=value
                evidence.append(row);print(row,flush=True)
        if a.checks=='convergence':continue
        schedule=[.003,.005]*5
        baseline,_=solve(body,.004,f'{body}-variable',schedule=schedule)
        for ranks in (1,2,4):
            full,_=solve(body,.004,f'{body}-r{ranks}',ranks=ranks,schedule=schedule)
            assert error(full,baseline)<2e-9
            checkpoint=a.work/f'checkpoint-{body}-{ranks}'
            solve(body,.004,f'{body}-partial{ranks}',ranks=ranks,schedule=schedule,extra=['-checkpoint',checkpoint,'-stop_after',3])
            resumed,_=solve(body,.004,f'{body}-resumed{ranks}',ranks=ranks,schedule=schedule,extra=['-restart',checkpoint])
            assert error(full,resumed)<2e-9
    if a.alpha and a.checks!='convergence':
        for body in ('elastic','rigid'):
            for ranks in (1,2,4):
                checkpoint=a.work/f'event-{body}-{ranks}'
                full,_=solve(body,.004,f'event-full-{body}-{ranks}',ranks=ranks,events=[.008])
                solve(body,.004,f'event-part-{body}-{ranks}',ranks=ranks,events=[.008],extra=['-checkpoint',checkpoint,'-stop_after',2])
                resumed,text=solve(body,.004,f'event-resume-{body}-{ranks}',ranks=ranks,events=[.008],extra=['-restart',checkpoint])
                assert 'time_order=1' in text.split('fsi_step=3',1)[1].splitlines()[0]
                assert error(full,resumed)<2e-9
    if a.checks!='convergence':
        checkpoint=a.work/'nonlinear-retry-checkpoint'
        solve('elastic',.004,'nonlinear-start',nonlinear=True,
              extra=['-checkpoint',checkpoint,'-stop_after',2])
        retried,text=solve('elastic',.004,'nonlinear-retry',nonlinear=True,retries=16,
                           extra=['-restart',checkpoint,'-snes_max_it',2,'-stop_after',3])
        rejected_times=list(map(float,re.findall(r'step_retry=\d+ time=(\S+)',text)))
        assert rejected_times and min(rejected_times)>=.008,rejected_times
        # Replay the actual binary step, rather than subtract rounded timestamps:
        # mesh acceleration contains a second difference on a very small retry.
        schedule=[.004,.004]+list(map(float,re.findall(r'accepted_dt=(\S+)',text)))
        assert len(schedule)==3,schedule
        reference,_=solve('elastic',.004,'nonlinear-trajectory',nonlinear=True,schedule=schedule,extra=['-stop_after',3])
        assert error(retried,reference)<2e-9
    if evidence:(a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
