"""Temporal refinement against a fine-step solution of the same spatial problem."""
import argparse
import json
import math
import re
from pathlib import Path
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
    a = p.parse_args(); a.work.mkdir(parents=True, exist_ok=True)
    mesh = a.work / 'cube.msh'; write_mesh(mesh, 2)
    def solve(scheme, h, label, ranks=1, extra=(), schedule=None, events=None, retries=0, failure=None):
        case = a.work / f'{label}.json'; output = a.work / f'{label}.vtu'
        config = dict(mesh=str(mesh.resolve()), output=str(output.resolve()),
                      fluid=dict(mode='transient', density=10, viscosity=1, dt=h, stabilization_tau=.05,
                                 steps=round(.2/h), boundaries=[
                                     dict(tag=1,type='pressure',value=1),
                                     dict(tag=2,type='pressure',value=0),
                                     *[dict(tag=tag,type='velocity',value=[0,0,0]) for tag in (3,4)],
                                     *[dict(tag=tag,type='velocity',value=[0,0,0],components=[2]) for tag in (5,6)]]),
                      solver=dict(relative_tolerance=1e-11, absolute_tolerance=1e-13, maximum_iterations=50),
                      time=dict(scheme=scheme))
        config['time_control']={}
        if retries: config['time_control'].update(max_retries=retries,minimum_dt=1e-6,reduction=.5)
        if schedule is not None: config['time_control']['step_sizes']=schedule
        if events is not None: config['time_control']['events']=events
        case.write_text(json.dumps(config))
        part=a.work/f'parts{ranks}'
        if not part.exists():
            prepared=subprocess.run([a.executable,'-case',str(case),'-prepare',str(part),'-parts',str(ranks)],
                                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
            if prepared.returncode: raise RuntimeError(prepared.stdout)
        command = [a.mpiexec, '-n', str(ranks), a.executable, '-case', str(case), '-partition', str(part), *map(str,extra)]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
        (a.work / f'{label}.log').write_text(run.stdout)
        if failure:
            assert run.returncode and failure in run.stdout and 'status=success' not in run.stdout, run.stdout[-6000:]
            return None,run.stdout
        if run.returncode: raise RuntimeError(run.stdout[-6000:])
        result = {}
        for rank in range(ranks):
            path=output if ranks==1 else output.with_name(output.stem+f'_rank{rank}.vtu')
            arrays={x.attrib['Name']:list(map(float,x.text.split())) for x in ET.parse(path).findall('.//PointData/DataArray')}
            for i, node in enumerate(arrays['mesh_node_id']):
                if int(arrays['owner'][i])==rank:
                    result[int(node)]={name: arrays[name][i*width:(i+1)*width] for name,width in (('velocity',3),('pressure',1))}
        return result,run.stdout
    reference,_=solve('bdf2',.000625,'reference')
    evidence=[]
    def error(first,second,name):
        assert first.keys()==second.keys()
        return math.sqrt(sum((x-y)**2 for node in first for x,y in zip(first[node][name],second[node][name]))/len(first))
    for scheme in ('be','bdf2'):
        previous={}
        for h in (.02,.01,.005):
            actual,_=solve(scheme,h,f'{scheme}-{h}')
            row=dict(scheme=scheme,h=h)
            for name in ('velocity','pressure'):
                value=error(actual,reference,name)
                assert math.isfinite(value) and value>0
                row[name]=value
                if name in previous:
                    order=math.log(previous[name]/value,2); row[name+'_order']=order
                    assert order>(1.7 if scheme=='bdf2' else .8), row
                previous[name]=value
            evidence.append(row); print(row,flush=True)
    baseline,_=solve('bdf2',.01,'variable',schedule=[.008,.012]*10)
    checkpoint=a.work/'checkpoint'
    solve('bdf2',.01,'partial',extra=['-checkpoint',checkpoint,'-stop_after',5],schedule=[.008,.012]*10)
    resumed,_=solve('bdf2',.01,'resumed',extra=['-restart',checkpoint],schedule=[.008,.012]*10)
    solve('bdf2',.01,'wrong-schedule',extra=['-restart',checkpoint],schedule=[.01],failure='Checkpoint mesh/partition/physics mismatch')
    solve('be',.01,'wrong-scheme',extra=['-restart',checkpoint],schedule=[.008,.012]*10,failure='Checkpoint mesh/partition/physics mismatch')
    for name in ('velocity','pressure'): assert error(baseline,resumed,name)<2e-10
    for ranks in (2,4):
        parallel,_=solve('bdf2',.01,f'variable-r{ranks}',ranks=ranks,schedule=[.008,.012]*10)
        for name in ('velocity','pressure'): assert error(baseline,parallel,name)<2e-9
    # A declared discontinuity invalidates BDF history at its accepted time.
    # Save exactly at that event; restart must perform the same BE startup.
    event_result,event_log=solve('bdf2',.01,'event',events=[.055])
    checkpoint=a.work/'event-checkpoint'
    solve('bdf2',.01,'event-partial',events=[.055],extra=['-checkpoint',checkpoint,'-stop_after',6])
    resumed,tail=solve('bdf2',.01,'event-resumed',events=[.055],extra=['-restart',checkpoint])
    records=re.findall(r'fluid_step=(\d+) time=(\S+).*time_order=(\d+)',event_log)
    assert abs(float(records[5][1])-.055)<1e-14 and records[6][2]=='1'
    assert re.findall(r'time_order=(\d+)',tail)[0]=='1'
    for name in ('velocity','pressure'): assert error(event_result,resumed,name)<2e-10
    _,short_log=solve('bdf2',.01,'short-final',schedule=[.013])
    times=list(map(float,re.findall(r'fluid_step=\d+ time=(\S+)',short_log)))
    assert len(times)==16 and abs(times[-1]-.2)<1e-14 and abs(times[-1]-times[-2]-.005)<1e-14
    checkpoint=a.work/'retry-checkpoint'
    solve('bdf2',.01,'retry-start',extra=['-checkpoint',checkpoint,'-stop_after',2])
    retried,retry_log=solve('bdf2',.01,'retried',extra=['-restart',checkpoint,'-snes_max_it',2],retries=10)
    rejected_times=list(map(float,re.findall(r'step_retry=\d+ time=(\S+)',retry_log)))
    assert rejected_times and min(rejected_times)>=.02
    accepted_times=[.02]+list(map(float,re.findall(r'fluid_step=\d+ time=(\S+)',retry_log)))
    schedule=[.01,.01]+[b-a for a,b in zip(accepted_times,accepted_times[1:])]
    direct,_=solve('bdf2',.01,'retry-trajectory',schedule=schedule)
    for name in ('velocity','pressure'): assert error(retried,direct,name)<2e-9
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__': main()
