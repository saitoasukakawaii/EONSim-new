"""Same-mesh unloaded vibration: temporal order, energy, MPI and restart."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/poisson'))
from generate_mesh import write_mesh


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--executable', required=True)
    p.add_argument('--mpiexec', required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--alpha',action='store_true')
    a = p.parse_args(); a.work.mkdir(parents=True, exist_ok=True)
    mesh = a.work/'cube.msh'; write_mesh(mesh, 2)
    def run(command,log=None):
        result = subprocess.run(list(map(str, command)), text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        if log:log.write_text(result.stdout)
        if result.returncode: raise RuntimeError(result.stdout[-6000:])
        return result.stdout
    def solve(scheme, h, label, ranks=1, extra=(), schedule=None,rho=.5,events=None,nonlinear=False,retries=0):
        case=a.work/f'{label}.json'; out=a.work/f'{label}.vtu'
        config=dict(mesh=str(mesh.resolve()), output=str(out.resolve()),
                    solid=dict(mode='unload', young=100, poisson=.3, density=1, traction=1,
                               dt=h, steps=round(.1/h)), time=dict(scheme=scheme),
                    solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13))
        if scheme=='generalized_alpha':config['time']['rho_infinity']=rho
        if nonlinear:config['solid']['material']='neo_hookean'
        config['time_control']={}
        if schedule:config['time_control']['step_sizes']=schedule
        if events:config['time_control']['events']=events
        if retries:config['time_control'].update(max_retries=retries,minimum_dt=1e-10,reduction=.5)
        case.write_text(json.dumps(config))
        part=a.work/f'parts{ranks}'
        if not part.exists(): run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra],a.work/f'{label}.log')
        result={}
        for rank in range(ranks):
            path=out if ranks==1 else out.with_name(out.stem+f'_rank{rank}.vtu')
            fields={x.attrib['Name']:list(map(float,x.text.split())) for x in ET.parse(path).findall('.//PointData/DataArray')}
            for i,node in enumerate(fields['mesh_node_id']):
                if int(fields['owner'][i])==rank:
                    names=('displacement','velocity','acceleration')+(('algorithmic_acceleration',) if scheme=='generalized_alpha' else ())
                    result[int(node)]={name:fields[name][3*i:3*i+3] for name in names}
        energies=list(map(float,re.findall(r'\btotal_energy=(\S+)',text)))
        assert energies and all(math.isfinite(v) and v>=0 for v in energies)
        return result, energies
    def error(first,second,name):
        assert first.keys()==second.keys()
        return math.sqrt(sum((x-y)**2 for node in first for x,y in zip(first[node][name],second[node][name]))/len(first))
    reference,_=solve('bdf2',.0000390625,'reference')
    evidence=[]
    methods=[('generalized_alpha',rho) for rho in (0.,.5,1.)] if a.alpha else [('be',.5),('bdf2',.5)]
    for scheme,rho in methods:
        previous={}
        for h in (.00125,.000625,.0003125):
            actual,energies=solve(scheme,h,f'{scheme}-{rho}-{h}',rho=rho)
            row=dict(scheme=scheme,rho=rho,h=h,initial_energy=energies[0],final_energy=energies[-1])
            for name in ('displacement','velocity','acceleration'):
                value=error(actual,reference,name); assert math.isfinite(value) and value>0
                row[name]=value
                if name in previous:
                    order=math.log(previous[name]/value,2); row[name+'_order']=order
                    assert order>(.8 if scheme=='be' else 1.7), row
                previous[name]=value
            assert energies[-1]<=energies[0]*(1+1e-8)
            if scheme=='generalized_alpha' and rho==1:
                assert max(abs(value-energies[1]) for value in energies[1:])<1e-11
            evidence.append(row); print(row,flush=True)
    if a.alpha:
        damped=[]
        for rho in (0.,.5,1.):
            _,energies=solve('generalized_alpha',.01,f'damping-{rho}',rho=rho)
            damped.append(energies[-1])
        assert damped[0]<damped[1]<damped[2],damped
        evidence.append(dict(high_frequency_energy=damped,rho=[0,.5,1],h=.01))
    scheme='generalized_alpha' if a.alpha else 'bdf2'
    baseline,_=solve(scheme,.005,'variable',schedule=[.004,.006]*10)
    for ranks in (1,2,4):
        full,_=solve(scheme,.005,f'variable-r{ranks}',ranks,schedule=[.004,.006]*10)
        checkpoint=a.work/f'checkpoint{ranks}'
        solve(scheme,.005,f'partial-r{ranks}',ranks,extra=['-checkpoint',checkpoint,'-stop_after',5],schedule=[.004,.006]*10)
        resumed,_=solve(scheme,.005,f'resumed-r{ranks}',ranks,extra=['-restart',checkpoint],schedule=[.004,.006]*10)
        for name in next(iter(full.values())):
            assert error(full,resumed,name)<2e-9
            assert error(full,baseline,name)<2e-9
    if a.alpha:
        full,_=solve(scheme,.005,'event',events=[.025])
        checkpoint=a.work/'event-checkpoint'
        solve(scheme,.005,'event-partial',events=[.025],extra=['-checkpoint',checkpoint,'-stop_after',5])
        resumed,_=solve(scheme,.005,'event-resumed',events=[.025],extra=['-restart',checkpoint])
        text=(a.work/'event-resumed.log').read_text()
        assert re.findall(r'time_order=(\d+)',text)[0]=='1'
        for name in next(iter(full.values())):assert error(full,resumed,name)<2e-9
        checkpoint=a.work/'retry-checkpoint'
        solve(scheme,.005,'retry-start',nonlinear=True,extra=['-checkpoint',checkpoint,'-stop_after',2])
        retried,_=solve(scheme,.005,'retried',nonlinear=True,retries=16,extra=['-restart',checkpoint,'-snes_max_it',1,'-stop_after',3])
        text=(a.work/'retried.log').read_text()
        rejected_times=list(map(float,re.findall(r'step_retry=\d+ time=(\S+)',text)))
        assert rejected_times and min(rejected_times)>=.01
        time=float(re.findall(r'solid_step=3 time=(\S+)',text)[0])
        direct,_=solve(scheme,.005,'retry-reference',nonlinear=True,schedule=[.005,.005,time-.01],extra=['-stop_after',3])
        for name in next(iter(direct.values())):assert error(retried,direct,name)<2e-9
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__': main()
