"""Actual transient fields and restart with fresh versus retained LU preconditioning."""
import argparse,json,math,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();a.work=a.work.resolve();a.work.mkdir(parents=True,exist_ok=True)
    # Every invocation owns fresh checkpoints. Preserve earlier attempts without
    # mixing different binaries' generations at the same accepted step.
    run_work=Path(tempfile.mkdtemp(prefix='run-',dir=a.work))
    (a.work/'current.json').write_text(json.dumps(dict(run_directory=run_work.name))+'\n')
    a.work=run_work
    tube.generate(a.work/'mesh',sectors=6,radial=1,axial=2,radius=1,length=2)
    cfg=tube.case_config();cfg['mesh']=str(a.work/'mesh/fluid.msh')
    cfg['fluid'].update(mode='transient',dt=1/32,steps=8,checkpoint_interval=1)
    cfg['fluid']['boundaries'][1].update(value=0,pressure_time=dict(amplitude=.02,period=math.pi/2))
    # Binary-exact physical increments isolate BDF2 coefficient changes from
    # an incidental final-time subtraction in this factor-count check.
    cfg['time']=dict(scheme='bdf2');cfg['time_control']=dict(step_sizes=[1/64,1/64,1/32,1/32,5/128,5/128,5/128,5/128])
    case=a.work/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n')
    def run(label,command,failure=None):
        command=list(map(str,command));(a.work/(label+'-command.json')).write_text(json.dumps(command,indent=2)+'\n')
        with (a.work/(label+'.log')).open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=sys.platform.startswith('linux'))
            try:code=child.wait(timeout=90)
            except BaseException:
                if sys.platform.startswith('linux'):
                    (a.work/(label+'-cleanup.json')).write_text(json.dumps(tube._stop_session(child),indent=2)+'\n')
                else:child.kill();child.wait()
                raise
        text=(a.work/(label+'.log')).read_text()
        if failure:assert code!=0 and failure in text,text[-4000:]
        else:assert code==0 and 'status=success' in text,text[-4000:]
        return text
    def compare(left,right):
        assert left.keys()==right.keys();delta=max(abs(x-y) for n in left for x,y in zip(left[n],right[n]))
        assert math.isfinite(delta) and delta<2e-9,delta;return delta
    def rows(text,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith(prefix)]
    def factorizations(path,expected):
        events=[line.split() for line in path.read_text().splitlines() if line.lstrip().startswith('MatLUFactorNum ')]
        assert len(events)==1 and int(events[0][1])==expected and float(events[0][2])==1,events
    results=[];serial=None
    for ranks in [1,2,4]:
        part=a.work/f'parts{ranks}';run(f'prepare{ranks}',[a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        mpi=[a.mpiexec,'-n',ranks] if ranks>1 else []
        base=mpi+[a.executable,'-case',case,'-partition',part,'-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-solver_report']
        directories={name:a.work/f'r{ranks}-{name}' for name in ['direct','cached','restart']}
        for d in directories.values():d.mkdir(exist_ok=True)
        direct=directories['direct'];cached=directories['cached'];restart=directories['restart']
        run(f'r{ranks}-direct',base+['-output',direct/'solution.vtu','-checkpoint',direct/'checkpoint'])
        profile=a.work/f'r{ranks}-cached-profile.txt'
        text=run(f'r{ranks}-cached',base+['-output',cached/'solution.vtu','-checkpoint',cached/'checkpoint','-fluid_lu_pc_reuse_window',4,'-log_view',':'+str(profile)])
        reports=rows(text,'solver_report ');uses=rows(text,'lu_preconditioner ')
        assert len(reports)==len(uses)==8
        assert all(r['ksp']=='fgmres' and r['pc']=='lu' and int(r['snes_reason'])>0 and int(r['ksp_reason'])>0 for r in reports)
        assert [int(r['reused']) for r in uses]==[0,0,0,0,0,0,1,1]
        assert [int(r['uses']) for r in uses]==[1,1,1,1,1,1,2,3]
        factorizations(profile,6)
        reference=tube.fields(direct,ranks);actual=tube.fields(cached,ranks)
        if serial is None:serial=reference
        result=dict(ranks=ranks,cached_vs_direct=compare(reference,actual),direct_vs_serial=compare(serial,reference))
        run(f'r{ranks}-split',base+['-output',restart/'solution.vtu','-checkpoint',restart/'checkpoint','-stop_after',3,'-fluid_lu_pc_reuse_window',4])
        marker,generation=(restart/'checkpoint/current').read_text().split();assert marker=='EONSim_checkpoint_v4'
        resumed=run(f'r{ranks}-resume',base+['-output',restart/'solution.vtu','-checkpoint',restart/'checkpoint','-restart',restart/'checkpoint'/generation,'-fluid_lu_pc_reuse_window',4])
        assert rows(resumed,'lu_preconditioner ')[0]['reused']=='0'
        result['restart_vs_uninterrupted']=compare(actual,tube.fields(restart,ranks))
        continuous_steps={int(r['fluid_step']):r for r in rows(text,'fluid_step=')}
        restart_steps={int(r['fluid_step']):r for r in rows(resumed,'fluid_step=')};assert set(restart_steps)==set(range(4,9))
        for step,r in restart_steps.items():
            for name in ['time','evaluation_time']:assert r[name]==continuous_steps[step][name]
        result['restart_logged_clocks_exact']=True
        # With constant physical dt, only BE startup and the first BDF2 solve
        # factorize. A long window must not retain the BE factor into BDF2.
        startup_cfg=json.loads(json.dumps(cfg));startup_cfg.pop('time_control')
        startup_cfg['fluid'].update(dt=1/64,steps=10)
        startup_case=a.work/'startup-case.json';startup_case.write_text(json.dumps(startup_cfg,indent=2)+'\n')
        startup_base=mpi+[a.executable,'-case',startup_case,'-partition',part,'-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-solver_report']
        outputs={name:a.work/f'r{ranks}-startup-{name}' for name in ['direct','cached']}
        for directory in outputs.values():directory.mkdir()
        for name,directory in outputs.items():
            command=startup_base+['-output',directory/'solution.vtu','-checkpoint',directory/'checkpoint']
            if name=='cached':command+=['-fluid_lu_pc_reuse_window',32,'-log_view',':'+str(directory/'petsc-profile.txt')]
            startup_text=run(f'r{ranks}-startup-{name}',command)
            if name=='cached':
                startup_uses=rows(startup_text,'lu_preconditioner ')
                assert [int(r['reused']) for r in startup_uses]==[0,0]+[1]*8
                assert [int(r['uses']) for r in startup_uses]==[1]+list(range(1,10))
                factorizations(directory/'petsc-profile.txt',2)
        result['startup_cached_vs_direct']=compare(tube.fields(outputs['direct'],ranks),tube.fields(outputs['cached'],ranks))
        result['actual_variable_step_factorizations']=6;result['actual_constant_step_factorizations']=2
        if ranks==2:
            extras={}
            for label in ['event','alpha']:
                extra_cfg=json.loads(json.dumps(startup_cfg))
                if label=='event':extra_cfg['time_control']=dict(events=[5/64])
                else:extra_cfg['time']=dict(scheme='generalized_alpha',rho_infinity=.5)
                extra_case=a.work/(label+'-case.json');extra_case.write_text(json.dumps(extra_cfg,indent=2)+'\n')
                extra_base=mpi+[a.executable,'-case',extra_case,'-partition',part,'-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-solver_report']
                outputs={name:a.work/f'r{ranks}-{label}-{name}' for name in ['direct','cached']}
                for name,directory in outputs.items():
                    directory.mkdir();command=extra_base+['-output',directory/'solution.vtu','-checkpoint',directory/'checkpoint']
                    if name=='cached':command+=['-fluid_lu_pc_reuse_window',32,'-log_view',':'+str(directory/'petsc-profile.txt')]
                    extra_text=run(f'r{ranks}-{label}-{name}',command)
                    if name=='cached':
                        actual_uses=rows(extra_text,'lu_preconditioner ')
                        expected_uses=[1,1,2,3,4,1,1,2,3,4] if label=='event' else [1]+list(range(1,10))
                        assert [int(r['uses']) for r in actual_uses]==expected_uses
                        assert [int(r['reused']) for r in actual_uses]==[int(v>1) for v in expected_uses]
                        factorizations(directory/'petsc-profile.txt',4 if label=='event' else 2)
                extras[label]=dict(cached_vs_direct=compare(tube.fields(outputs['direct'],ranks),tube.fields(outputs['cached'],ranks)),actual_factorizations=4 if label=='event' else 2)
            result['extra_coefficient_checks']=extras
        results.append(result)
    run('invalid-window',[a.executable,'-case',case,'-fluid_lu_pc_reuse_window',-1],failure='Invalid -fluid_lu_pc_reuse_window')
    run('unsupported-physics',[a.executable,'-case',ROOT/'cases/poisson/case.yaml','-fluid_lu_pc_reuse_window',4],failure='requires standalone transient fixed-mesh fluid')
    run('unsupported-pc',[a.executable,'-case',case,'-pc_type','jacobi','-fluid_lu_pc_reuse_window',4],failure='LU preconditioner reuse requires')
    (a.work/'summary.json').write_text(json.dumps(dict(passed=True,results=results,steps=8,variable_step_schedule=cfg['time_control']['step_sizes'],
        scope='Same current PDE, true final fields, coefficient-change/restart refresh, actual PETSc factor counts and logged v4 clocks. Complete HDF snapshots retained for a separate dataset audit. No performance or long-cycle qualification.'),indent=2)+'\n')
    print(json.dumps(results))

if __name__=='__main__':main()
