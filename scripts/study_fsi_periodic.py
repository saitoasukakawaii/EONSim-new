"""Bounded full-field periodic study with physical checkpoint continuation.

Run in the locked PETSc environment. Not part of the default CTest matrix.
"""
import argparse
import csv
import math
import hashlib
import shutil
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner,generate
from fsi_field_cycles import series,compare_series,read_snapshot,pressure_drop
from fsi_cycle_metrics import compare_cycles,volume_budget


def save_receipt(receipt,cfg,metrics,checkpoint,converged):
    generation=(checkpoint/'current').read_text().split()[1]
    temporary=receipt.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(converged=converged,config=cfg,metrics=metrics,
                                        checkpoint_generation=generation),indent=2)+'\n')
    temporary.replace(receipt)


def preserve_attempt(work,label):
    """Keep existing solver outputs before replaying an incomplete attempt."""
    leftovers=[p for p in work.iterdir() if p.name.startswith(label+'.') or p.name.startswith(label+'_')]
    if leftovers:
        archive=work/'failed-attempts'/label
        index=0
        while (archive/str(index)).exists():index+=1
        destination=archive/str(index);destination.mkdir(parents=True)
        for old_file in leftovers:shutil.move(str(old_file),destination/old_file.name)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--n',type=int,default=2)
    p.add_argument('--ranks',type=int,default=2);p.add_argument('--dt',type=float,default=.001)
    p.add_argument('--minimum-cycles',type=int,default=3)
    p.add_argument('--cycles',type=int,default=60);p.add_argument('--scheme',default='generalized_alpha',choices=['be','bdf2','generalized_alpha'])
    p.add_argument('--tau',type=float,default=.05);p.add_argument('--tolerance',type=float,default=1e-3)
    p.add_argument('--phases',type=int,default=20)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--automatic-tau',action='store_true')
    a=p.parse_args();period=.1
    if not (math.isfinite(a.dt) and a.dt>0 and a.cycles>=a.minimum_cycles>=3 and a.n>=2 and a.ranks>0 and math.isfinite(a.tau) and a.tau>0 and math.isfinite(a.tolerance) and a.tolerance>0):raise ValueError('Invalid study parameters')
    steps=round(period/a.dt)
    if a.phases<16 or abs(steps*a.dt-period)>1e-12 or steps%a.phases:raise ValueError('Require at least 16 exactly aligned phases per cycle')
    run=Runner(a.executable,a.mpiexec,a.work,timeout=7200)
    checkpoint=run.work/'checkpoint';receipt=run.work/'periodic-result.json'
    definition=dict(executable_sha256=hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),n=a.n,ranks=a.ranks,dt=a.dt,scheme=a.scheme,tau=None if a.automatic_tau else a.tau,
                    tolerance=a.tolerance,phases=a.phases,fluid_scales={'velocity':.01,'pressure':.1,'mesh_displacement':1e-4},
                    solid_scales={'velocity':.01,'displacement':1e-4})
    root=Path(__file__).resolve().parents[1]
    inputs=('scripts/study_fsi_periodic.py','scripts/fsi_field_cycles.py','scripts/fsi_cycle_metrics.py',
            'cases/fsi/generate_wall.py','cases/poisson/generate_mesh.py','tests/verify_fsi_inlet.py')
    definition['source_sha256']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in inputs}
    definition_path=run.work/'study-definition.json'
    all_rows=[];fluid=[];solid=[];metrics=[];streak=0;start=1
    resume_source=checkpoint
    if a.resume:
        definition['mesh_sha256']={name:hashlib.sha256((run.work/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')}
        if json.loads(definition_path.read_text())!=definition:raise ValueError('Study definition changed during resume')
        saved=json.loads(receipt.read_text());cfg=saved['config']
        metrics=saved['metrics'];start=metrics[-1]['cycle']+1
        streak=metrics[-1]['consecutive_passes']
        generation=saved['checkpoint_generation']
        resume_source=checkpoint/generation
        manifest=(resume_source/'manifest').read_text().split()
        if int(manifest[1])!=a.ranks or int(manifest[2])!=(start-1)*steps:
            raise ValueError('Checkpoint is not at last recorded complete cycle; preserve interrupted outputs')
        for cycle in range(1,start):
            stem=f'cycle{cycle}'+(f'_restart{(cycle-1)*steps}' if cycle>1 else '')
            with (run.work/(stem+'.csv')).open() as f:all_rows += [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
            fluid+=series(run.work/(stem+'.pvd'));solid+=series(run.work/(stem+'_solid.pvd'))
        volume_budget(all_rows)  # Validate persisted accepted history before another solver launch.
        if abs(all_rows[-1]['time']-(start-1)*period)>1e-10:raise ValueError('Accepted history does not reach recorded cycle')
        if saved['converged'] and start-1>=a.minimum_cycles:return
    else:
        if any(run.work.iterdir()):raise ValueError('Fresh study requires an empty work directory')
        cfg=json.loads(generate(run.work,n=a.n,periodic_flow=True).read_text())
        cfg['fsi'].update(dt=a.dt,output_interval=steps//a.phases,stabilization_tau=a.tau)
        if a.automatic_tau:cfg['fsi'].pop('stabilization_tau')
        cfg['time']=dict(scheme=a.scheme)
        definition['mesh_sha256']={name:hashlib.sha256((run.work/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')}
        definition_path.write_text(json.dumps(definition,indent=2)+'\n')
    cfg['fsi']['steps']=a.cycles*steps
    cfg['fsi']['checkpoint_interval']=steps
    for cycle in range(start,a.cycles+1):
        label=f'cycle{cycle}'
        extra=['-checkpoint',checkpoint,'-stop_after',cycle*steps]
        if cycle>1:extra+=['-restart',resume_source if cycle==start else checkpoint]
        preserve_attempt(run.work,label)
        _,rows,_=run.solve(label,cfg,a.ranks,extra)
        all_rows+=rows
        stem=label+(f'_restart{(cycle-1)*steps}' if cycle>1 else '')
        fluid+=series(run.work/(stem+'.pvd'));solid+=series(run.work/(stem+'_solid.pvd'))
        if max(abs(r['stage_mass_residual']) for r in rows)>1e-9:raise ValueError('Stage continuity failed')
        if max(abs(r['stage_mass_residual']+r['stage_divergence']) for r in rows)>1e-12:raise ValueError('Surface/divergence disagreement')
        if max(abs(r['endpoint_inlet_flow']-r['target_endpoint_flow']) for r in rows)>1e-12:raise ValueError('Inlet flux mismatch')
        if cycle<3:
            metrics.append(dict(cycle=cycle,consecutive_passes=0,status='insufficient cycle history'))
            save_receipt(receipt,cfg,metrics,checkpoint,False)
            continue
        end=rows[-1]['time']
        result=dict(cycle=cycle,fluid=compare_series(fluid,period,end,{'velocity':.01,'pressure':.1,'mesh_displacement':1e-4}),
                    solid=compare_series(solid,period,end,{'velocity':.01,'displacement':1e-4},True))
        result['observations']={name:compare_cycles([r['time'] for r in all_rows],[r[name] for r in all_rows],period,end,scale)
             for name,scale in [('area_displacement_y',1e-4),('endpoint_volume',1e-4),('endpoint_outlet_flow',.01)]}
        pressure=[(t,pressure_drop(read_snapshot(path,False,True))['pressure_drop'])
                  for t,path in fluid if end-2*period-period/a.phases-1e-10<=t<=end+1e-10]
        result['observations']['pressure_drop']=compare_cycles([t for t,_ in pressure],[v for _,v in pressure],period,end,.1)
        # Also check every actual field phase, including the accepted endpoint;
        # a denser interpolated scalar grid need not include those exact peaks.
        def pressure_at(time):
            found=[value for t,value in pressure if abs(t-time)<1e-10]
            if len(found)!=1:raise ValueError('Missing exact pressure phase')
            return found[0]
        exact_pressure=max(abs(pressure_at(end-period+j*period/a.phases)-pressure_at(end-2*period+j*period/a.phases))/.1 for j in range(1,a.phases+1))
        result['observations']['pressure_drop']['relative_max']=max(result['observations']['pressure_drop']['relative_max'],exact_pressure)
        result['mass_budget']=volume_budget(all_rows)
        passed=max([*result['fluid'].values(),*result['solid'].values(),*[v['relative_max'] for v in result['observations'].values()]])<=a.tolerance
        streak=streak+1 if passed else 0
        result['consecutive_passes']=streak;metrics.append(result)
        save_receipt(receipt,cfg,metrics,checkpoint,streak>=3 and cycle>=a.minimum_cycles)
        print(json.dumps(result),flush=True)
        if streak>=3 and cycle>=a.minimum_cycles:return
    raise RuntimeError('Maximum cycles reached without full-field periodic convergence')


if __name__=='__main__':main()
