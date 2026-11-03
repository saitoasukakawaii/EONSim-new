"""Three-scheme temporal order on a complete driven cycle, fixed spatial operator.

This transient order experiment does not certify periodic steady state. The
steady spatial study separately requires a temporal-contamination estimate.
"""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner,generate
from fsi_field_cycles import read_snapshot,difference,series


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--coarse',action='store_true')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    def solve(label,scheme,steps_per_cycle):
        run=Runner(a.executable,a.mpiexec,a.work/label,timeout=7200)
        cfg=json.loads(generate(run.work,n=2,periodic_flow=True).read_text())
        cfg['fsi'].update(dt=.1/steps_per_cycle,steps=2*steps_per_cycle,output_interval=steps_per_cycle//20,stabilization_tau=.05)
        cfg['time']=dict(scheme=scheme)
        cfg['solver'].update(relative_tolerance=1e-11,absolute_tolerance=1e-13)
        expected={**cfg,'output':str(run.work/'flow.vtu')}
        if (run.work/'flow.json').exists() and json.loads((run.work/'flow.json').read_text())==expected and (run.work/'flow.log').exists() and 'status=success' in (run.work/'flow.log').read_text():
            print('reuse identical completed case',label,flush=True)
        else:run.solve('flow',cfg,2)
        return run.work
    reference_steps=1280 if a.coarse else 10240
    reference=solve('reference' if a.coarse else 'reference-10240','bdf2',reference_steps)
    summary=[]
    for scheme in ('be','bdf2','generalized_alpha'):
        previous={}
        for steps in ((40,80,160) if a.coarse else ((1280,2560,5120) if scheme=='be' else (160,320,640))):
            work=solve(f'{scheme}-{steps}',scheme,steps)
            result=dict(scheme=scheme,dt=.1/steps,errors={},orders={})
            for solid in (False,True):
                suffix='_solid' if solid else ''
                fields={'velocity':1.,'displacement':1.} if solid else {'velocity':1.,'pressure':1.,'mesh_displacement':1.}
                ref=series(reference/('flow'+suffix+'.pvd'));current=series(work/('flow'+suffix+'.pvd'))
                errors=[]
                for t,path in current:
                    if t<=.1+1e-12:continue
                    matches=[rp for rt,rp in ref if abs(rt-t)<1e-12]
                    if len(matches)!=1:raise ValueError('Reference phase missing')
                    errors.append(difference(read_snapshot(path,solid),read_snapshot(matches[0],solid),fields))
                if len(errors)!=20:raise ValueError('Complete 20-phase cycle required')
                for name in fields:
                    key=('solid_' if solid else 'fluid_')+name
                    error=math.sqrt(sum(e[name]**2 for e in errors)/len(errors))
                    result['errors'][key]=error
                    if key in previous:
                        order=math.log(previous[key]/error,2);result['orders'][key]=order
                    previous[key]=error
            summary.append(result)
            (a.work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(result),flush=True)
    if not a.coarse:
        previous_reference=solve('reference-5120','bdf2',5120)
        ratios={}
        for solid in (False,True):
            suffix='_solid' if solid else ''
            fields={'velocity':1.,'displacement':1.} if solid else {'velocity':1.,'pressure':1.,'mesh_displacement':1.}
            coarse_ref=series(previous_reference/('flow'+suffix+'.pvd'));fine_ref=series(reference/('flow'+suffix+'.pvd'))
            values=[]
            for t,path in coarse_ref:
                if t<=.1+1e-12:continue
                match=[p for rt,p in fine_ref if abs(rt-t)<1e-12]
                if len(match)!=1:raise ValueError('Reference phase missing')
                values.append(difference(read_snapshot(path,solid),read_snapshot(match[0],solid),fields))
            for name in fields:
                key=('solid_' if solid else 'fluid_')+name
                delta=math.sqrt(sum(v[name]**2 for v in values)/len(values))
                ratios[key]=delta/min(r['errors'][key] for r in summary)
        (a.work/'reference-contamination.json').write_text(json.dumps(ratios,indent=2)+'\n')
        if max(ratios.values())>.1:raise RuntimeError('Reference refinement difference exceeds 10% of candidate error')
    failures=[r for r in summary if any(order<(.85 if r['scheme']=='be' else 1.7) for field,order in r['orders'].items() if field!='fluid_pressure')]
    if failures:raise RuntimeError('Temporal order criterion failed; retain raw evidence')


if __name__=='__main__':main()
