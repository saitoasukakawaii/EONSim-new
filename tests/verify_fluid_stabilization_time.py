"""Time-scale control: default identity, distinct operator, MPI and restart.

The no-slip pressure-driven cube has genuine spatial error, so this control
must affect its solution. Uniform accelerating flow alone cannot test tau:
its strong momentum residual vanishes exactly for every coefficient.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from verify_fluid_pressure_time import fields,difference,expected
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cases/poisson'))
from generate_mesh import write_mesh


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();args.work.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=args.work)).resolve()
    mesh=work/'cube.msh';write_mesh(mesh,3)
    boundaries=[]
    for tag,value in ((1,.2),(2,0.)):
        boundaries.extend((dict(tag=tag,type='pressure',value=value,components=[0]),
                           dict(tag=tag,type='velocity',value=[0,0,0],components=[1,2])))
    boundaries.extend(dict(tag=tag,type='velocity',value=[0,0,0]) for tag in (3,4,5,6))
    base=dict(mesh=str(mesh),fluid=dict(mode='transient',dt=.02,steps=6,boundaries=boundaries),
              time=dict(scheme='be'),solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30))

    def run(command,log,failure=None):
        result=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
        log.write_text(result.stdout)
        if failure:
            assert result.returncode!=0 and failure in result.stdout and 'status=success' not in result.stdout,result.stdout
        else:
            assert result.returncode==0 and 'status=success' in result.stdout,result.stdout

    def solve(name,cfg,ranks=1,extra=(),failure=None):
        directory=work/name;directory.mkdir()
        cfg=copy.deepcopy(cfg);cfg['output']=str(directory/'solution.vtu')
        path=directory/'case.json';path.write_text(json.dumps(cfg,indent=2)+'\n')
        command=[args.executable.resolve(),'-case',path]
        if ranks>1:
            partition=work/f'parts{ranks}'
            if not partition.exists():
                run(command+['-prepare',partition,'-parts',ranks],directory/'prepare.log')
            command=[args.mpiexec,'-n',ranks]+command+['-partition',partition]
        run(command+list(extra),directory/'solve.log',failure)
        return (None if failure else fields(directory/'solution.vtu',ranks)),directory

    reference,_=solve('default',base)
    controlled=copy.deepcopy(base);controlled['fluid']['stabilization_time_scale']=.02
    same,_=solve('same-scale',controlled)
    parallel,_=solve('same-scale-r2',controlled,2)
    identity=difference(reference,same);mpi=difference(same,parallel)
    assert identity<2e-10 and mpi<2e-10,(identity,mpi)
    changed=copy.deepcopy(controlled);changed['fluid']['stabilization_time_scale']=.01
    altered,_=solve('different-scale',changed,2)
    effect=difference(same,altered)
    assert effect>1e-8,effect
    checkpoint=work/'checkpoint'
    solve('partial',controlled,2,['-checkpoint',checkpoint,'-stop_after',3])
    resumed,_=solve('resumed',controlled,2,['-restart',checkpoint])
    restart=difference(same,resumed);assert restart<2e-10,restart
    for name,cfg in (('changed-scale',changed),('removed-scale',base)):
        solve(name+'-restart',cfg,2,['-restart',checkpoint],failure='Checkpoint mesh/partition/physics mismatch')
    for name,mutate,message in (
        ('zero',lambda c:c['fluid'].update(stabilization_time_scale=0),'must be finite and positive'),
        ('negative',lambda c:c['fluid'].update(stabilization_time_scale=-1),'must be finite and positive'),
        ('infinite',lambda c:c['fluid'].update(stabilization_time_scale='.inf'),'must be finite and positive'),
        ('steady',lambda c:c['fluid'].update(mode='steady'),'requires transient fluid'),
        ('both',lambda c:c['fluid'].update(stabilization_tau=.01),'Use only one of'),
    ):
        cfg=copy.deepcopy(controlled);mutate(cfg)
        solve('invalid-'+name,cfg,failure=message)
    # An exact spatial solution independently proves that the altered time
    # scale never changes the actual BE/BDF2/alpha derivative or load time.
    slip=[]
    for tag in (1,2):
        slip.extend((dict(tag=tag,type='pressure',value=0.,components=[0]),
                     dict(tag=tag,type='velocity',value=[0,0,0],components=[1,2])))
    slip[0]['pressure_time']=dict(amplitude=.2,period=.4,ramp_time=.09)
    slip.extend(dict(tag=tag,type='velocity',value=[0,0,0],components=[component])
                for tag,component in ((3,1),(4,1),(5,2),(6,2)))
    oracle={}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg=copy.deepcopy(controlled)
        cfg['fluid'].update(dt=.037,steps=11,boundaries=slip,stabilization_time_scale=.017)
        cfg['time']=dict(scheme=scheme)
        if scheme=='generalized_alpha':
            cfg['time']['rho_infinity']=.5
        state,_=solve('unchanged-derivative-'+scheme,cfg)
        velocity,pressure=expected(scheme)
        oracle[scheme]=max(max(abs(a-b) for a,b in zip(v,(velocity,0.,0.,pressure*(1-x)))) for v,x in state.values())
        assert oracle[scheme]<2e-9,(scheme,oracle[scheme])
    result=dict(work=str(work),default_identity=identity,mpi_difference=mpi,changed_operator_difference=effect,
                restart_difference=restart,unchanged_derivative_oracle=oracle,
                checks='invalid values/mode/conflict and changed restart rejected')
    (work/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
