"""Check MPI ownership and adaptive retry of two coupled circuits in the elastic T-junction."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'cases/fsi')]
from verify_fsi_inlet import Runner,check_rcr_history,error
from generate_branched import generate


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for key in ('work','mpiexec','executable'):cli.add_argument('--'+key,type=Path,required=True)
    cli.add_argument('--ranks',nargs='+',type=int,default=[2,4,8])
    a=cli.parse_args()
    cfg=json.loads(generate(a.work).read_text())
    cfg['fsi'].update(steps=4,output_interval=4)
    models=cfg['fsi']['domains']['rcr_outlets']
    models[0].update(proximal_resistance=12.,distal_resistance=32.,compliance=.00625)
    geo=json.loads((a.work/'geometry.json').read_text())
    run=Runner(a.executable,str(a.mpiexec.resolve()),a.work,interface_area=geo['interface_area'])
    reference,_,_=run.solve('one',cfg)
    report=dict(ranks={},retry={})
    for ranks in a.ranks:
        name='direct-'+str(ranks)
        values,rows,_=run.solve(name,cfg,ranks)
        diff=error(reference,values)
        if diff>2e-9:raise ValueError('Ranks disagree')
        circuit=max(check_rcr_history(run,name,m,rows,sole_pressure=False) for m in models)
        report['ranks'][ranks]=dict(node_field_difference=diff,circuit_residual=circuit)
    cfg['fsi'].update(steps=6,dt=.01,output_interval=6)
    cfg['fsi']['inlet']['flow_rate'].update(mean=.035,amplitude=.005)
    for scheme in ('bdf2','generalized_alpha'):
        cfg['time']=dict(scheme=scheme)
        cfg.pop('time_control',None)
        checkpoint=a.work.resolve()/('checkpoint-'+scheme)
        run.solve('save-'+scheme,cfg,2,['-stop_after',2,'-checkpoint',checkpoint])
        cfg['time_control']=dict(max_retries=18,minimum_dt=1e-11,reduction=.5)
        fields,rows,log=run.solve('retry-'+scheme,cfg,2,['-restart',checkpoint,'-stop_after',3,'-snes_max_it',2])
        if len(rows)!=1 or 'step_retry=' not in log:raise ValueError('No accepted candidate after a real retry')
        dt=rows[0]['accepted_dt']
        cfg['time_control']['step_sizes']=[.01,.01,dt]
        replay,other,_=run.solve('explicit-'+scheme,cfg,2,['-stop_after',3])
        delta=max(abs(rows[0][k]-other[-1][k]) for k in rows[0] if 'rcr' in k or 'capacitor' in k)
        if max(delta,error(fields,replay))>2e-9:raise ValueError('Replaying the accepted schedule changed the solution')
        report['retry'][scheme]=dict(retries=log.count('step_retry='),accepted_dt=dt,field_error=error(fields,replay),
                                     maximum_circuit_difference=delta)
    (a.work/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
