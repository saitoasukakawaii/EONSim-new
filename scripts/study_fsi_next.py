"""Bounded FSI accuracy and paired Release solver experiments; no speedup promise."""
import argparse
import copy
import json
import math
from pathlib import Path
import statistics
import sys
import time
import re
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner,error
from generate_wall import generate as wall
from generate_domains import generate as piston


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--study',choices=['accuracy','performance','inlet-time'],required=True)
    a=p.parse_args();a.work=a.work.resolve();a.work.mkdir(parents=True,exist_ok=True)
    evidence=[]
    if a.study=='accuracy':
        runs={}
        for n in (2,4,8):
            run=Runner(a.executable,a.mpiexec,a.work/f'n{n}',timeout=2400);cfg=json.loads(piston(run.work,n).read_text())
            cfg['fsi'].update(material='neo_hookean',pressure=20,pressure_time=dict(amplitude=2,period=.1,ramp_time=.05),dt=.002,steps=100,output_interval=10000)
            cfg['time']=dict(scheme='bdf2');cfg['solver'].update(relative_tolerance=1e-11,absolute_tolerance=1e-13)
            _,rows,_=run.solve('spatial',cfg);runs[n]=rows
            record=dict(n=n,dt=.002,final=rows[-1],min_fluid_j=min(r['endpoint_min_fluid_j'] for r in rows),min_solid_j=min(r['endpoint_min_solid_j'] for r in rows));evidence.append(record);print(record,flush=True)
        def distance(coarse,fine):
            # Interpolate onto the coarser actual accepted timestamps.
            import bisect
            times=[r['time'] for r in fine];diff=[]
            for r in coarse:
                i=min(len(fine)-1,bisect.bisect_left(times,r['time']));j=max(0,i-1)
                w=0 if i==j else (r['time']-times[j])/(times[i]-times[j])
                val=(1-w)*fine[j]['area_displacement_x']+w*fine[i]['area_displacement_x']
                diff.append((r['area_displacement_x']-val)**2)
            return math.sqrt(sum(diff)/len(diff))
        space=distance(runs[4],runs[8]);assert space>0
        # Require time contamination below a quarter of the last spatial difference.
        previous=runs[8];h=.002
        for level in range(1,7):
            h/=2;cfg['fsi'].update(dt=h,steps=round(.2/h))
            _,fine,_=run.solve('time-half'+str(level),cfg)
            temporal=distance(previous,fine);record=dict(time_dt=h,time_difference=temporal,spatial_difference=space,ratio=temporal/space)
            evidence.append(record);print(record,flush=True)
            if temporal<space/4:break
            previous=fine
        else:raise RuntimeError('Time contamination still exceeds spatial study criterion')
        # If dt changed, spatial comparison must use that converged coarse dt too.
        if level>1:
            resolved={8:previous}
            for n in (2,4):
                small=Runner(a.executable,a.mpiexec,a.work/f'n{n}',timeout=2400)
                small_cfg=json.loads((small.work/'spatial.json').read_text())
                small_cfg['fsi'].update(dt=2*h,steps=round(.2/(2*h)))
                _,resolved[n],_=small.solve('resolved-spatial',small_cfg)
            space=distance(resolved[4],resolved[8]);assert temporal<space/4
            evidence.append(dict(resolved_dt=2*h,temporal_difference=temporal,spatial_difference=space,ratio=temporal/space))
            runs=resolved
        evidence.append(dict(spatial_difference_2_4=distance(runs[2],runs[4]),spatial_difference_4_8=space))
    elif a.study=='inlet-time':
        run=Runner(a.executable,a.mpiexec,a.work);cfg=json.loads(wall(run.work).read_text());cfg['fsi'].update(dt=.0000625,steps=640,output_interval=0,stabilization_tau=.05)
        cfg['time']=dict(scheme='bdf2');cfg['solver'].update(relative_tolerance=1e-11,absolute_tolerance=1e-13)
        reference,_,_=run.solve('reference',cfg)
        for scheme in ('be','bdf2','generalized_alpha'):
            cfg['time']=dict(scheme=scheme);last=None
            for h in (.001,.0005,.00025):
                cfg['fsi'].update(dt=h,steps=round(.04/h));actual,_,_=run.solve(f'{scheme}-{h}',cfg)
                keys=[k for k in actual if k[2] in ('velocity','mesh_displacement','displacement')]
                e=math.sqrt(sum((v-w)**2 for k in keys for v,w in zip(actual[k],reference[k]))/sum(len(actual[k]) for k in keys))
                row=dict(scheme=scheme,h=h,error=e)
                if last:row['order']=math.log(last/e,2);assert row['order']>(.85 if scheme=='be' else 1.7),row
                last=e;evidence.append(row);print(row,flush=True)
    else:
        for n in (4,8):
            run=Runner(a.executable,a.mpiexec,a.work/f'n{n}',timeout=2400);cfg=json.loads(wall(run.work,n,True).read_text())
            cfg['fsi'].update(dt=.004,steps=5,output_interval=0)
            cfg['solver'].update(relative_tolerance=1e-10,absolute_tolerance=1e-12)
            baselines={};medians={}
            def measure(ranks,recipe,repeat):
                extra=['-solver_report','-device_enable','none']
                if recipe!='direct':extra+=['-pc_recipe',recipe]
                start=time.perf_counter();fields,_,log=run.solve(f'r{ranks}-{recipe}-{repeat}',cfg,ranks,extra);wall_seconds=time.perf_counter()-start
                if ranks not in baselines:baselines[ranks]=fields
                delta=max(error(baselines[ranks],fields),error(baselines[1],fields));assert delta<2e-9,delta
                reports=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in log.splitlines() if line.startswith('solver_report ')]
                assert len(reports)==5
                row=dict(n=n,ranks=ranks,recipe=recipe,repeat=repeat,wall_seconds=wall_seconds,field_max_error=delta,dofs=int(reports[0]['dofs']))
                for key in ('solve_seconds','assembly_seconds','ghost_seconds','linear_iterations'):row[key]=sum(float(r[key]) for r in reports)
                for key in ('peak_rss_max_bytes','peak_rss_sum_bytes'):row[key]=max(float(r[key]) for r in reports)
                evidence.append(row);print(row,flush=True)
                return row
            recipes=['direct','physics','hybrid']
            for recipe in recipes:measure(1,recipe,'warmup')
            for repeat in range(3):
                for recipe in (recipes if repeat%2==0 else list(reversed(recipes))):measure(1,recipe,repeat)
            for recipe in ('physics','hybrid'):medians[recipe]=statistics.median(r['solve_seconds'] for r in evidence if r['n']==n and r['ranks']==1 and r['recipe']==recipe and r['repeat']!='warmup')
            selected=min(medians,key=medians.get)
            if n==8:
                for ranks in (2,4):
                    for recipe in ('direct',selected):measure(ranks,recipe,'warmup')
                    for repeat in range(3):
                        for recipe in (['direct',selected] if repeat%2==0 else [selected,'direct']):measure(ranks,recipe,repeat)
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
