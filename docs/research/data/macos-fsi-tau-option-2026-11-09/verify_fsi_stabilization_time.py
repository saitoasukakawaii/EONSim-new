"""Explicit tau-time control on a spatially nonuniform elastic tube; defaults and restart."""
import argparse,copy,json,subprocess,sys,tempfile
from pathlib import Path
from verify_fsi_lu_reuse import frames,compare,rows
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cases/fsi'))
from generate_pressure_tube import generate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True);p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--baseline',type=Path)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='run-',dir=a.work)).resolve()
    base=json.loads(generate(work/'mesh',sectors=8,radial=1,axial=2,length=2,steps_per_cycle=20,cycles=1).read_text())
    base['mesh']=str(work/'mesh/fluid.msh');base['fsi']['domains']['solid_mesh']=str(work/'mesh/solid.msh')
    base['fsi'].update(dt=.02,steps=8,output_interval=1,pressure_time=dict(amplitude=.05,period=.4,ramp_time=.04))
    base['time']=dict(scheme='be')
    def run(command,log,failure=None):
        result=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
        log.write_text(result.stdout)
        if failure:assert result.returncode!=0 and failure in result.stdout and 'status=success' not in result.stdout,result.stdout
        else:assert result.returncode==0 and 'status=success' in result.stdout,result.stdout
        return result.stdout
    def solve(label,cfg,ranks=1,extra=(),failure=None,executable=None):
        d=work/label;d.mkdir();cfg=copy.deepcopy(cfg);cfg['output']=str(d/'solution.vtu');case=d/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n')
        cmd=[(executable or a.executable).resolve(),'-case',case]
        if ranks>1:
            part=work/f'parts{ranks}'
            if not part.exists():run(cmd+['-prepare',part,'-parts',ranks],d/'prepare.log')
            cmd=[a.mpiexec,'-n',ranks]+cmd+['-partition',part]
        text=run(cmd+['-pc_factor_mat_solver_type','mumps']+list(extra),d/'solve.log',failure)
        return None if failure else (frames(d),rows(text,'fsi_step='))
    original,_=solve('default-be',base)
    control=copy.deepcopy(base);control['fsi']['stabilization_time_scale']=.02
    same,_=solve('same-be-time',control);identity=compare(original,same);assert identity<2e-12
    changed=copy.deepcopy(control);changed['fsi']['stabilization_time_scale']=.005
    altered,_=solve('changed-time',changed)
    effect=max(abs(x-y) for phase,v in same.items() for key,u in v.items() for x,y in zip(u,altered[phase][key]));assert effect>1e-8,effect
    parallel,_=solve('control-r2',control,2);mpi=compare(same,parallel)
    restart={};baseline={}
    for scheme in ['be','bdf2','generalized_alpha']:
        cfg=copy.deepcopy(control);cfg['time']=dict(scheme=scheme)
        if scheme=='generalized_alpha':cfg['time']['rho_infinity']=.5
        full,hist=solve('full-'+scheme,cfg)
        checkpoint=work/('checkpoint-'+scheme);solve('partial-'+scheme,cfg,extra=['-checkpoint',checkpoint,'-stop_after',4])
        resumed,_=solve('resumed-'+scheme,cfg,extra=['-restart',checkpoint])
        expected={key:v for key,v in full.items() if key in resumed};restart[scheme]=compare(expected,resumed)
        assert len(hist)==8 and all(abs(float(v['time'])-(i+1)*.02)<1e-13 for i,v in enumerate(hist))
        for label,value in [('changed',.01),('removed',None)]:
            bad=copy.deepcopy(cfg)
            if value is None:bad['fsi'].pop('stabilization_time_scale')
            else:bad['fsi']['stabilization_time_scale']=value
            solve(label+'-restart-'+scheme,bad,extra=['-restart',checkpoint],failure='Checkpoint mesh/partition/physics mismatch')
        if a.baseline:
            default=copy.deepcopy(cfg);default['fsi'].pop('stabilization_time_scale')
            old,_=solve('old-default-'+scheme,default,executable=a.baseline);new,_=solve('new-default-'+scheme,default)
            baseline[scheme]=compare(old,new);assert baseline[scheme]<2e-12
    for label,value in [('zero',0),('negative',-1),('infinite','.inf')]:
        cfg=copy.deepcopy(control);cfg['fsi']['stabilization_time_scale']=value;solve('invalid-'+label,cfg,failure='must be finite and positive')
    cfg=copy.deepcopy(control);cfg['fsi']['stabilization_tau']=.05;solve('invalid-conflict',cfg,failure='Use only one of')
    result=dict(work=str(work),default_be_identity=identity,changed_operator_difference=effect,mpi_difference=mpi,restart=restart,old_binary_default_difference=baseline,scope='Explicit diagnostic only; all actual time grids and default physics retained. Invalid/conflicting settings and changed/removed restart options rejected.')
    (work/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
