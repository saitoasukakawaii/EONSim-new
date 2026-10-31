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
    a = p.parse_args(); a.work.mkdir(parents=True, exist_ok=True)
    mesh = a.work/'cube.msh'; write_mesh(mesh, 2)
    def run(command):
        result = subprocess.run(list(map(str, command)), text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        if result.returncode: raise RuntimeError(result.stdout[-6000:])
        return result.stdout
    def solve(scheme, h, label, ranks=1, extra=(), schedule=None):
        case=a.work/f'{label}.json'; out=a.work/f'{label}.vtu'
        config=dict(mesh=str(mesh.resolve()), output=str(out.resolve()),
                    solid=dict(mode='unload', young=100, poisson=.3, density=1, traction=1,
                               dt=h, steps=round(.1/h)), time=dict(scheme=scheme),
                    solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13))
        if schedule: config['time_control']=dict(step_sizes=schedule)
        case.write_text(json.dumps(config))
        part=a.work/f'parts{ranks}'
        if not part.exists(): run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra])
        (a.work/f'{label}.log').write_text(text)
        result={}
        for rank in range(ranks):
            path=out if ranks==1 else out.with_name(out.stem+f'_rank{rank}.vtu')
            fields={x.attrib['Name']:list(map(float,x.text.split())) for x in ET.parse(path).findall('.//PointData/DataArray')}
            for i,node in enumerate(fields['mesh_node_id']):
                if int(fields['owner'][i])==rank:
                    result[int(node)]={name:fields[name][3*i:3*i+3] for name in ('displacement','velocity','acceleration')}
        energies=list(map(float,re.findall(r'\btotal_energy=(\S+)',text)))
        assert energies and all(math.isfinite(v) and v>=0 for v in energies)
        return result, energies
    def error(first,second,name):
        assert first.keys()==second.keys()
        return math.sqrt(sum((x-y)**2 for node in first for x,y in zip(first[node][name],second[node][name]))/len(first))
    reference,_=solve('bdf2',.0000390625,'reference')
    evidence=[]
    for scheme in ('be','bdf2'):
        previous={}
        for h in (.00125,.000625,.0003125):
            actual,energies=solve(scheme,h,f'{scheme}-{h}')
            row=dict(scheme=scheme,h=h,initial_energy=energies[0],final_energy=energies[-1])
            for name in ('displacement','velocity','acceleration'):
                value=error(actual,reference,name); assert math.isfinite(value) and value>0
                row[name]=value
                if name in previous:
                    order=math.log(previous[name]/value,2); row[name+'_order']=order
                    assert order>(1.7 if scheme=='bdf2' else .8), row
                previous[name]=value
            assert energies[-1]<=energies[0]*(1+1e-8)
            evidence.append(row); print(row,flush=True)
    baseline,_=solve('bdf2',.005,'variable',schedule=[.004,.006]*10)
    for ranks in (1,2,4):
        full,_=solve('bdf2',.005,f'variable-r{ranks}',ranks,schedule=[.004,.006]*10)
        checkpoint=a.work/f'checkpoint{ranks}'
        solve('bdf2',.005,f'partial-r{ranks}',ranks,extra=['-checkpoint',checkpoint,'-stop_after',5],schedule=[.004,.006]*10)
        resumed,_=solve('bdf2',.005,f'resumed-r{ranks}',ranks,extra=['-restart',checkpoint],schedule=[.004,.006]*10)
        for name in ('displacement','velocity','acceleration'):
            assert error(full,resumed,name)<2e-9
            assert error(full,baseline,name)<2e-9
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__': main()
