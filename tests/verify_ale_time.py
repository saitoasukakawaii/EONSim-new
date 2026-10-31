"""Uniform-flow preservation, analytic mesh velocity and ALE history restart."""
import argparse
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
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    mesh=a.work/'cube.msh';write_mesh(mesh,2)
    def run(command):
        r=subprocess.run(list(map(str,command)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout[-6000:])
        return r.stdout
    def solve(mode,scheme,h,label,ranks=1,extra=(),schedule=None):
        case=a.work/f'{label}.json';out=a.work/f'{label}.vtu'
        cfg=dict(mesh=str(mesh.resolve()),output=str(out.resolve()),time=dict(scheme=scheme),
                 motion=dict(mode=mode,amplitude=.1,speed=.2,dt=h,steps=round(.5/h)),
                 solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13))
        if schedule:cfg['time_control']=dict(step_sizes=schedule)
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
                assert abs(fields['pressure'][i])<1e-10
                ref=[points[3*i+c]-fields['mesh_displacement'][3*i+c] for c in range(3)]
                if sum(abs(x-.5) for x in ref)<1e-12:center_velocity=fields['mesh_velocity'][3*i]
        assert center_velocity is not None
        return values,center_velocity
    evidence=[]
    for scheme in ('be','bdf2'):
        previous=0
        for h in (.1,.05,.025):
            _,velocity=solve('uniform',scheme,h,f'{scheme}-{h}')
            error=abs(velocity-.1*math.cos(.5));row=dict(scheme=scheme,h=h,mesh_velocity_error=error)
            if previous:
                order=math.log(previous/error,2);row['order']=order
                assert order>(1.8 if scheme=='bdf2' else .8),row
            previous=error;evidence.append(row);print(row,flush=True)
    def compare(x,y):
        assert x.keys()==y.keys()
        assert max(abs(v-w) for node in x for v,w in zip(x[node],y[node]))<2e-10
    for mode in ('uniform','shear'):
        schedule=[.08,.12]*3
        base,_=solve(mode,'bdf2',.1,f'{mode}-base',schedule=schedule)
        for ranks in (1,2,4):
            full,_=solve(mode,'bdf2',.1,f'{mode}-{ranks}',ranks,schedule=schedule);compare(base,full)
            checkpoint=a.work/f'checkpoint-{mode}-{ranks}'
            solve(mode,'bdf2',.1,f'{mode}-partial-{ranks}',ranks,extra=['-checkpoint',checkpoint,'-stop_after',2],schedule=schedule)
            resumed,_=solve(mode,'bdf2',.1,f'{mode}-resumed-{ranks}',ranks,extra=['-restart',checkpoint],schedule=schedule)
            compare(full,resumed)
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
