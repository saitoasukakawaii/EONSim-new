"""Review the concrete uniform N800 family before any fresh solver starts."""
import hashlib, importlib.util, json, os, shutil, sys, time
from pathlib import Path
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
W=Path('/home/tfblab633/EONSim-prod48-20261107')
C=W/'fsi-s24-n800-lu32-family-3b08e4f'
ROOT=Path('/mnt/c/Users/tfblab633/Documents/ChatGPT/数值计算/EONSim-new-current')
read=lambda p:json.loads(p.read_text())

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def worker():
    m=module('family',C/'controller.py');m.proof();d=m.verify()
    assert all(not m.status(role).exists() for role in ('coarse','fine','budget'))
    assert all(not (C/role/'adoption.json').exists() for role in ('coarse','fine'))
    assert [d[k] for k in ('cycles','ramp_cycles','steps_per_cycle','first_audited_step','stored_audit_states','final_step')]==[32,16,800,23201,2400,25600]
    assert [d[k] for k in ('rank_count','lu_window','coarser_time_control_steps_per_cycle')]==[1,32,400]
    assert d['uniform_dt_from_zero'] and d['restart_only_same_grid_cycle_boundaries'] and d['shared_guest_cpus'] and d['nice']==19
    assert [d[k] for k in ('memory_max_bytes','swap_max_bytes','admission_bytes','running_floor_bytes')]==[2*1024**3,0,12*1024**3,8*1024**3]
    assert [d[k] for k in ('cycle_timeout','audit_timeout','budget_timeout')]==[18000,28800,28800]
    assert [d[k] for k in ('periodic_limit','lame_limit','budget_fraction','kinematics_limit','mass_limit','divergence_limit')]==[1e-5,.02,.1,1e-12,1e-9,1e-12]
    source_count=0
    for name,h in read(m.V/'definition.json')['source_hashes'].items():
        assert sha(ROOT/name)==sha(m.V/'source'/name)==h;source_count+=1
    assert d['candidate_sha256']==m.BINARY=='6993d7f29778524317de991af58af6287a3c9d813ba81337299f4089e0d611c9'
    assert d['original_kernel_sha256']=='8c53a40420c0dcd41615863745c6f89a16e0dbd4cf631150387d6bb75bfc01f5'
    original=m.SOURCE/'build/prod48-20261107/s24-budget-kernel.py'
    refined=m.SOURCE/'build/prod48-20261107/s24-n800-budget-kernel.py'
    assert refined.read_text()==m.kernel_text(original.read_text())
    assert original.read_text().split('    prerequisites=',1)[1].replace('level1/N400 numerical','level1/N800 numerical')==refined.read_text().split('    prerequisites=',1)[1]
    commands=0
    for role,cpu,lock in [('coarse',19,'elastic-budget-analysis.lock'),('fine',22,'elastic-geometry-long.lock')]:
        assert d['roles'][role]['cpu']==cpu and d['roles'][role]['lock']==lock
        old=read(m.OLD[role]/'case.json');cfg=read(m.OUT[role]/'case.json')
        restored=json.loads(json.dumps(cfg))
        for key in ('dt','steps','checkpoint_interval','output_interval'):restored['fsi'][key]=old['fsi'][key]
        assert restored==old and cfg['fsi']['dt']==old['fsi']['dt']/2
        assert cfg['fsi']['pressure_time']['ramp_time']==16*cfg['fsi']['pressure_time']['period']
        assert cfg['time']=={'scheme':'generalized_alpha','rho_infinity':.5} and 'stabilization_tau' not in cfg['fsi']
        assert cfg['solver']=={'relative_tolerance':1e-11,'absolute_tolerance':1e-13,'maximum_iterations':30}
        assert not any((m.OUT[role]/f'cycle{cycle:03d}').exists() for cycle in range(1,33))
        for cycle in range(1,33):
            expected=['/usr/bin/python3',str(C/(role+'-guard.py')),str(m.OUT[role]/'eonsim'),'-case','case.json',
                      '-checkpoint',str(m.OUT[role]/'checkpoint'),'-stop_after',str(cycle*800),'-solver_report',
                      '-log_view',':profile.txt','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32']
            if cycle>1:expected+=['-restart',str(m.OUT[role]/'checkpoint')]
            assert expected==d['roles'][role]['commands'][str(cycle)]==m.numerical_command(role,cycle)
            v=m.cycle_case(role,cycle);v['mesh']='fluid.msh';v['fsi']['domains']['solid_mesh']='solid.msh'
            assert v['fsi']['output_interval']==(0 if cycle<=29 else 1)
            v['fsi']['output_interval']=1;assert v==cfg;commands+=1
        assert d['roles'][role]['audit_command']==['/usr/bin/python3',str(C/(role+'-guard.py')),'/usr/bin/python3',
              str(m.SOURCE/'scripts/audit_pressure_tube.py'),'--case',str(m.OUT[role]/'case.json'),'--work',str(m.OUT[role]),
              '--first-step','23201','--output',str(m.OUT[role]/'eonsim-audit.json')]
    fields=module('fields',m.SOURCE/'build/prod48-20261107/compare-pressure-fields.py')
    for name in ('fluid.msh','solid.msh'):fields.nested(m.OUT['coarse']/name,m.OUT['fine']/name,1)
    report=read(C/'original-n400-audit.json')
    assert report['analysis_script_sha256']==m.ANALYZER and report['case_sha256']==sha(m.OLD['fine']/'case.json')
    assert report['steps']==12800 and report['samples_per_cycle']==400 and report['sampled_steps']==1200
    assert report['periodic'] and all(x['passed'] for x in report['quality_gates'].values())
    # The final snapshot uses config.output. Restart suffixes belong to history series only.
    assert "initial=directory/f'cycle029/solution{suffix}.vtu'" in (C/'controller.py').read_text()
    result=dict(passed=True,decision='run_separate_uniform_s24_n800_lu32_family',
        definition_sha256=sha(C/'definition.json'),raw_review_sha256=sha(m.R/'raw-review.json'),
        screen_report_sha256=sha(m.S/'report.json'),reviewer_sha256=sha(C/'execution-reviewer.py'),
        build_source_files_checked=source_count,commands_checked=commands,nested_meshes_checked=2,
        original_budget_failure_preserved=True,exact_budget_arithmetic_except_grid_constants=True,
        full_qualification=False,adopted=False,
        scope='Implementing-agent review of the actual prepared plan after all mature raw proof passed. Uniform finer dt from zero,32 physical cycles,16-cycle ramp, full2400-state audit, unchanged physics/tolerances/thresholds. One-rank sharedCPU19/22,2GiB caps and12GiB admission. No deadline completion guarantee.')
    (C/'execution-review-result.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='worker':worker()
    else:
        assert not (C/'execution-review.json').exists() and not (C/'execution-reviewer.py').exists()
        shutil.copy2(__file__,C/'execution-reviewer.py')
        cap=module('cap',C/'bounded_cgroup_job_2g.py');m=module('family',C/'controller.py')
        while cap.available()<=10*1024**3:time.sleep(10)
        os.sched_setaffinity(0,{19});os.nice(19)
        resource=cap.run([sys.executable,C/'budget-guard.py',sys.executable,C/'execution-reviewer.py','worker'],C,
                        C/'execution-review.log',os.environ.copy(),f'eonsim-fsi-n800-plan-review-{os.getpid()}.scope',600)
        p=m.proof();p.clean_resource(resource)
        result=read(C/'execution-review-result.json');result.update(resource=resource,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        (C/'execution-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
