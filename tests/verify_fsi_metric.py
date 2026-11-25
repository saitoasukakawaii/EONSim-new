"""Current regular-Tet4 stabilization on an elastic wall with time changes, MPI and restart."""
import argparse
import copy
import json
from pathlib import Path

from verify_fsi_inlet import Runner, error, generate


def verify(executable, mpi, work):
    cfg=json.loads(generate(work,periodic_flow=True).read_text())
    flow=cfg['fsi']
    flow.pop('stabilization_tau',None)
    flow.update(stabilization_model='regular_tet',dt=.004,steps=6,output_interval=6)
    flow['inlet']['ramp_time']=.008
    run=Runner(executable,mpi,work)
    result={}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg['time']=dict(scheme=scheme)
        if scheme=='generalized_alpha':cfg['time']['rho_infinity']=.5
        one,rows,_=run.solve(scheme,cfg)
        explicit=copy.deepcopy(cfg)
        explicit['fsi']['stabilization_time_scale']=flow['dt']
        two,paired,_=run.solve(scheme+'-per-rank',explicit,2)
        maximum=error(one,two)
        flux=max(abs(r['stage_mass_residual']) for r in rows+paired)
        if len(rows)!=6 or len(paired)!=6 or maximum>=2e-9 or flux>=2e-10:
            raise ValueError('Fixed physical step/metric, MPI or mass check failed')
        result[scheme]=dict(field_difference=maximum,stage_mass_residual=flux)
    cfg['time_control']=dict(step_sizes=[.004,.004,.003,.005,.003,.005])
    baseline,_,_=run.solve('variable',cfg,2)
    checkpoint=work/'metric-checkpoint'
    run.solve('part',cfg,2,['-stop_after',3,'-checkpoint',checkpoint])
    resumed,_,_=run.solve('restart',cfg,2,['-restart',checkpoint])
    result['variable_restart_difference']=error(baseline,resumed)
    if result['variable_restart_difference']>=2e-9:raise ValueError('Metric restart changed the endpoint')
    for name,change in (('model',dict(stabilization_model='volume')),('time',dict(stabilization_time_scale=.004))):
        changed=copy.deepcopy(cfg)
        changed['fsi'].update(change)
        run.solve('restart-'+name,changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    for name,change,reason in (
            ('tau',dict(stabilization_tau=.025),'computes both'),('div',dict(grad_div_viscosity=0.),'computes both'),
            ('unknown',dict(stabilization_model='other'),'requires volume or regular_tet')):
        invalid=copy.deepcopy(cfg)
        invalid['fsi'].update(change)
        case=work/('invalid-'+name+'.json')
        case.write_text(json.dumps(invalid))
        run.command([run.exe,'-case',case,'-prepare',work/('invalid-part-'+name),'-parts',1],'check-'+name,fail=reason)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',required=True)
    parser.add_argument('--mpiexec',required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    report=verify(args.executable,args.mpiexec,args.work)
    (args.work/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report,flush=True)


if __name__=='__main__':main()
