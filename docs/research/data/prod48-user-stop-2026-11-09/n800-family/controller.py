"""Fresh uniform N800 S24 coarse/fine studies and the unchanged N400/N800 budget."""
import argparse, copy, fcntl, hashlib, importlib.util, json, math, os, re, shutil, sys, time, traceback
from pathlib import Path
import xml.etree.ElementTree as ET
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
S=W/'fsi-retained-lu-mature-screen-b8d1c76';R=W/'fsi-retained-lu-mature-review-3b08e4f'
V=W/'fsi-lu-reuse-validation-9ccd73f';B=W/'elastic-s24-native1600-budgets-32fb313'
C=W/'fsi-s24-n800-lu32-family-3b08e4f';SOURCE=C/'source'
OLD={'coarse':D/'elastic-s24-l0-n400-ramp16-c32',
     'fine':D/'elastic-s24-l1-n400-bounded-audit-6bce127'}
OUT={role:D/f'elastic-s24-l{level}-n800-lu32-c32-3b08e4f' for role,level in [('coarse',0),('fine',1)]}
CPU={'coarse':19,'fine':22,'budget':19}
LOCK={'coarse':'elastic-budget-analysis.lock','fine':'elastic-geometry-long.lock','budget':'elastic-budget-analysis.lock'}
BINARY='6993d7f29778524317de991af58af6287a3c9d813ba81337299f4089e0d611c9'
ANALYZER='6fdd2a4a8d82c4a40a51235c51129f1c4bc0a26d2609793540ee4402849e5e3d'
KERNEL='8c53a40420c0dcd41615863745c6f89a16e0dbd4cf631150387d6bb75bfc01f5'
N=800;CYCLES=32;WARMUP=29*N;LAST=CYCLES*N
read=lambda p:json.loads(Path(p).read_text())

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def files(p):return [x for x in p.rglob('*') if x.is_file() and '__pycache__' not in x.parts]

def status(role):return W/f'fsi-s24-n800-lu32-{role}-current.json'

def update(role,state,**kw):
    v=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
           role=role,control=str(C),adopted=(C/role/'adoption.json').exists(),full_qualification=False,**kw)
    p=status(role).with_suffix('.tmp');dump(p,v);p.replace(status(role));print(json.dumps(v),flush=True)

def proof():
    assert read(W/'fsi-retained-lu-mature-screen-current.json')['state']=='completed'
    assert read(W/'fsi-retained-lu-mature-review-current.json')['state']=='completed'
    screen=read(S/'report.json');review=read(R/'raw-review.json')
    assert screen['passed'] and screen['eligible'] and not screen['adopted']
    assert review['passed'] and review['eligible'] and not review['adopted']
    assert review['decision']=='eligible_for_separate_fsi_refined_time_plan_review'
    assert review['screen_definition_sha256']==sha(S/'definition.json')
    assert review['screen_report_sha256']==sha(S/'report.json')==read(S/'completion.json')['report_sha256']
    assert sha(R/'raw-review.json')==read(R/'completion.json')['raw_review_sha256']
    assert review['all_reported_metrics_exactly_recomputed'] and review['native_datasets']==1584
    p=module('original_proof',W/'length24-native-extension-proof-4f5f26d/controller.py')
    for resource in screen['resources'].values():p.clean_resource(resource)
    p.clean_resource(read(S/'completion.json')['comparison_resource'])
    p.clean_resource(read(R/'completion.json')['resource'])
    assert sha(V/'eonsim-release')==BINARY
    return p

def expected_case(role):
    cfg=read(OLD[role]/'case.json');assert cfg['fsi']['steps']==12800
    assert cfg['fsi']['dt']==cfg['fsi']['pressure_time']['period']/400
    cfg['fsi'].update(dt=cfg['fsi']['pressure_time']['period']/N,steps=LAST,
                      checkpoint_interval=N,output_interval=1)
    return cfg

def cycle_case(role,cycle):
    cfg=expected_case(role);cfg['mesh']='../fluid.msh';cfg['fsi']['domains']['solid_mesh']='../solid.msh'
    cfg['fsi']['output_interval']=0 if cycle<=29 else 1
    return cfg

def numerical_command(role,cycle):
    args=[sys.executable,C/(role+'-guard.py'),OUT[role]/'eonsim','-case','case.json',
          '-checkpoint',OUT[role]/'checkpoint','-stop_after',cycle*N,'-solver_report',
          '-log_view',':profile.txt','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2',
          '-fsi_lu_pc_reuse_window',32]
    if cycle>1:args+=['-restart',OUT[role]/'checkpoint']
    return list(map(str,args))

def audit_command(role):
    return list(map(str,[sys.executable,C/(role+'-guard.py'),sys.executable,SOURCE/'scripts/audit_pressure_tube.py',
                        '--case',OUT[role]/'case.json','--work',OUT[role],'--first-step',WARMUP+1,
                        '--output',OUT[role]/'eonsim-audit.json']))

def kernel_text(original):
    changes=[('left.n==fine.n==400 and temporal.n==200','left.n==fine.n==800 and temporal.n==400'),
             ('not400 Python fields','not800 Python fields'),
             ('dense_phases=400,reconstruction_phases=200','dense_phases=800,reconstruction_phases=400'),
             ('actual400 dense states','actual800 dense states'),('level1/N400 numerical','level1/N800 numerical')]
    result=original
    for old,new in changes:
        assert result.count(old)==1;result=result.replace(old,new)
    check=result
    for old,new in reversed(changes):check=check.replace(new,old)
    assert check==original
    return result

def prepare():
    assert not C.exists() and all(not p.exists() for p in OUT.values())
    assert all(not status(role).exists() for role in (*OUT,'budget'))
    proof();os.sched_setaffinity(0,{19});os.nice(19)
    assert read(W/'elastic-s24-bounded-audit-recovery-current.json')['state']=='completed'
    assert read(W/'elastic-budget-s24-l0-n400-eonsim-current.json')['state']=='completed'
    assert shutil.disk_usage(D).free>48*1024**3
    C.mkdir();shutil.copy2(__file__,C/'controller.py')
    shutil.copytree(B/'source',SOURCE,ignore=shutil.ignore_patterns('__pycache__'))
    previous=read(B/'definition.json')['source_hashes']
    for name,h in previous.items():assert sha(SOURCE/name)==h
    original=SOURCE/'build/prod48-20261107/s24-budget-kernel.py';assert sha(original)==KERNEL
    refined=SOURCE/'build/prod48-20261107/s24-n800-budget-kernel.py';refined.write_text(kernel_text(original.read_text()))
    shutil.copy2(S/'bounded_cgroup_job_2g.py',C/'bounded_cgroup_job_2g.py')
    bindings={str(p):sha(p) for p in [S/'definition.json',S/'report.json',S/'completion.json',R/'definition.json',
              R/'raw-review.json',R/'completion.json',V/'definition.json',V/'completion.json',B/'eonsim/budget.json']}
    roles={}
    for role in (*OUT,'budget'):
        (C/role).mkdir()
        guard=C/(role+'-guard.py');text=(S/'execution-guard.py').read_text()
        assert text.count('os.sched_setaffinity(0,{19})')==1
        guard.write_text(text.replace('os.sched_setaffinity(0,{19})',f'os.sched_setaffinity(0,{{{CPU[role]}}})'))
    for role,directory in OUT.items():
        directory.mkdir()
        for name in ('fluid.msh','solid.msh','geometry.json'):
            shutil.copy2(OLD[role]/name,directory/name);bindings[str(OLD[role]/name)]=sha(OLD[role]/name)
        bindings[str(OLD[role]/'case.json')]=sha(OLD[role]/'case.json')
        bindings[str(OLD[role]/'eonsim-audit.json')]=sha(OLD[role]/'eonsim-audit.json')
        dump(directory/'case.json',expected_case(role));shutil.copy2(V/'eonsim-release',directory/'eonsim')
        roles[role]=dict(cpu=CPU[role],lock=LOCK[role],
                        input_hashes={p.name:sha(p) for p in directory.iterdir() if p.is_file()},
                        commands={str(cycle):numerical_command(role,cycle) for cycle in range(1,33)},
                        audit_command=audit_command(role))
    matched=B/'matched-audits/eonsim/eonsim-fine-audit.json'
    assert read(matched)['analysis_script_sha256']==ANALYZER
    shutil.copy2(matched,C/'original-n400-audit.json');bindings[str(matched)]=sha(matched)
    assert read(C/'original-n400-audit.json')['case_sha256']==sha(OLD['fine']/'case.json')
    dump(C/'evidence-bindings.json',bindings)
    dump(C/'definition.json',dict(controller_sha256=sha(C/'controller.py'),candidate_sha256=BINARY,
        source_hashes={p.relative_to(SOURCE).as_posix():sha(p) for p in files(SOURCE)},roles=roles,
        original_kernel_sha256=KERNEL,refined_kernel_sha256=sha(refined),
        original_budget_sha256=sha(B/'eonsim/budget.json'),evidence_bindings_sha256=sha(C/'evidence-bindings.json'),
        cap_sha256=sha(C/'bounded_cgroup_job_2g.py'),guard_hashes={role:sha(C/(role+'-guard.py')) for role in (*OUT,'budget')},
        cycles=32,ramp_cycles=16,steps_per_cycle=N,first_audited_step=WARMUP+1,stored_audit_states=3*N,
        final_step=LAST,rank_count=1,uniform_dt_from_zero=True,coarser_time_control_steps_per_cycle=400,
        restart_only_same_grid_cycle_boundaries=True,nice=19,shared_guest_cpus=True,
        memory_max_bytes=2*1024**3,swap_max_bytes=0,admission_bytes=12*1024**3,running_floor_bytes=8*1024**3,
        cycle_timeout=18000,audit_timeout=28800,budget_timeout=28800,lu_window=32,
        periodic_limit=1e-5,lame_limit=.02,budget_fraction=.1,kinematics_limit=1e-12,mass_limit=1e-9,divergence_limit=1e-12,
        scope='Fresh uniform N800 for same S24 coarse/fine meshes, all32 cycles and original16-cycle ramp. Original complete N400 fine is the coarser time control, matching the original N200/N400 budget direction. Same kernel arithmetic with only explicit grid constants/labels changed. Original failed N400 budget remains. No startup shortcut, Richardson scaling, phase fitting or stabilization change; sharedCPU22 has occupied guest-sibling23. No full qualification implied.'))
    print(json.dumps(dict(prepared=True,definition_sha256=sha(C/'definition.json'),adopted=False)),flush=True)

def verify():
    d=read(C/'definition.json')
    assert sha(C/'controller.py')==d['controller_sha256']==sha(Path(__file__))
    assert sha(C/'evidence-bindings.json')==d['evidence_bindings_sha256']
    for name,h in read(C/'evidence-bindings.json').items():assert sha(name)==h
    for name,h in d['source_hashes'].items():assert sha(SOURCE/name)==h
    for role,v in d['roles'].items():
        for name,h in v['input_hashes'].items():assert sha(OUT[role]/name)==h
        assert v['commands']=={str(cycle):numerical_command(role,cycle) for cycle in range(1,33)}
        assert v['audit_command']==audit_command(role) and read(OUT[role]/'case.json')==expected_case(role)
        assert sha(OUT[role]/'eonsim')==BINARY
    for role,h in d['guard_hashes'].items():assert sha(C/(role+'-guard.py'))==h
    assert sha(C/'bounded_cgroup_job_2g.py')==d['cap_sha256']=='5070df17d8c299ea4bc393971e69fcc77f09821c1d0b895df6074c7a9997a939'
    original=SOURCE/'build/prod48-20261107/s24-budget-kernel.py'
    refined=SOURCE/'build/prod48-20261107/s24-n800-budget-kernel.py'
    assert sha(original)==KERNEL and refined.read_text()==kernel_text(original.read_text())
    return d

def environment():
    prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
    env={k:v for k,v in os.environ.items() if not k.startswith(('OMPI_','PMIX_','PRTE_')) and k not in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH')}
    env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR='/tmp')
    return env

def accepted(role,cycle):
    import h5py,numpy as np
    p=C/role/f'cycle{cycle:03d}.log';text=p.read_text();assert 'status=success' in text and 'step_retry=' not in text
    parse=lambda prefix:[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith(prefix)]
    rows=parse('fsi_step=');reports=parse('solver_report ');uses=parse('lu_preconditioner ')
    assert [int(x['fsi_step']) for x in rows]==list(range((cycle-1)*N+1,cycle*N+1))
    assert len(reports)==len(uses)==N
    dt=read(OUT[role]/'case.json')['fsi']['dt']
    for row,report,use in zip(rows,reports,uses):
        assert int(report['snes_reason'])>0 and report['ksp']=='fgmres' and report['pc']=='lu'
        # An exactly accepted startup zero needs no KSP; a started linear solve must converge.
        assert int(report['linear_started'])==int(report['linear_completed'])
        assert int(report['ksp_reason'])>0 or (int(report['linear_started'])==0 and int(report['ksp_reason'])==0)
        assert math.isfinite(float(row['residual'])) and abs(float(row['time'])-int(row['fsi_step'])*dt)<1e-9
        assert all(math.isfinite(float(row[k])) and float(row[k])>0 for k in ('endpoint_min_fluid_j','endpoint_min_solid_j'))
        assert int(use['window'])==32 and 0<=int(use['uses'])<=32
    event=[line.split() for line in (OUT[role]/f'cycle{cycle:03d}/profile.txt').read_text().splitlines() if line.lstrip().startswith('MatLUFactorNum ')]
    assert len(event)==1 and 0<int(event[0][1])<=N and float(event[0][2])==1
    manifest=[p for p in (OUT[role]/'checkpoint').glob('*/manifest') if int(p.read_text().split()[2])==cycle*N]
    assert len(manifest)==1;tokens=manifest[0].read_text().split();assert tokens[:3]==['EONSim_checkpoint_v4','1',str(cycle*N)]
    with h5py.File(manifest[0].parent/'state_rank0.h5') as f:
        assert len(f)==11 and tuple(f['metadata'][...][:3])==(4,0,1) and int(f['metadata'][8])==cycle*N
        assert all(np.all(np.isfinite(f[name][...])) for name in f)
        assert np.array_equal(f['clock'][...],np.array(list(map(float,tokens[3:]))))
    return dict(first_step=(cycle-1)*N+1,last_step=cycle*N,accepted_count=N,actual_lu_count=int(event[0][1]),
                native_sha256=sha(manifest[0].parent/'state_rank0.h5'),log_sha256=sha(p))

def combine_outputs(role):
    directory=OUT[role];dt=read(directory/'case.json')['fsi']['dt']
    for solid in (False,True):
        suffix='_solid' if solid else '';tree=ET.Element('VTKFile',type='Collection',version='0.1');collection=ET.SubElement(tree,'Collection')
        # main writes the final endpoint at config.output; only history/PVD names carry restart.
        initial=directory/f'cycle029/solution{suffix}.vtu';assert initial.is_file()
        ET.SubElement(collection,'DataSet',timestep=format(WARMUP*dt,'.17g'),file=initial.relative_to(directory).as_posix())
        for cycle in (30,31,32):
            path=directory/f'cycle{cycle:03d}'/f'solution_restart{(cycle-1)*N}{suffix}.pvd'
            items=ET.parse(path).findall('.//DataSet');assert len(items)==N
            for step,item in enumerate(items,(cycle-1)*N+1):
                assert abs(float(item.attrib['timestep'])-step*dt)<1e-9
                actual=(path.parent/item.attrib['file']).resolve(strict=True);assert actual.is_relative_to(directory)
                item.attrib['file']=actual.relative_to(directory).as_posix();collection.append(item)
        ET.ElementTree(tree).write(directory/f'solution{suffix}.pvd',encoding='utf-8',xml_declaration=True)
    sealed={str(p):sha(p) for p in files(directory)}
    dump(C/role/'sealed-numerical-outputs.json',sealed)

def guard_cpu(role):
    others=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0');name=Path(os.fsdecode(args[0])).name.lower() if args else ''
            if name.startswith(('eonsim','svfsi')):
                cpus=sorted(os.sched_getaffinity(int(p.name)))
                assert CPU[role] not in cpus,(p.name,cpus)
                others.append(dict(pid=int(p.name),cpus=cpus,executable=os.fsdecode(args[0])))
        except (FileNotFoundError,ProcessLookupError):pass
    return others

def execution_review():
    d=verify();v=read(C/'execution-review.json')
    assert v['passed'] and v['decision']=='run_separate_uniform_s24_n800_lu32_family'
    assert v['definition_sha256']==sha(C/'definition.json') and v['raw_review_sha256']==sha(R/'raw-review.json')
    return d

def run(role):
    assert role in OUT and not status(role).exists() and not (C/role/'adoption.json').exists()
    d=execution_review();p=proof();cap=module('cap',C/'bounded_cgroup_job_2g.py')
    try:
        update(role,'waiting_for_resources',holds_locks=False)
        with (W/LOCK[role]).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{CPU[role]});os.nice(19)
            while cap.available()<=d['admission_bytes']:time.sleep(10)
            others=guard_cpu(role);verify()
            dump(C/role/'adoption.json',dict(adopted=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                 definition_sha256=sha(C/'definition.json'),execution_review_sha256=sha(C/'execution-review.json'),
                 original_process_signals=[],other_numerical_cpus=others,full_qualification=False))
            receipts=[]
            for cycle in range(1,33):
                while cap.available()<=10*1024**3:time.sleep(10)
                assert shutil.disk_usage(D).free>32*1024**3
                directory=OUT[role]/f'cycle{cycle:03d}';directory.mkdir();dump(directory/'case.json',cycle_case(role,cycle))
                cmd=numerical_command(role,cycle);dump(C/role/f'cycle{cycle:03d}-command.json',cmd)
                update(role,'running',cycle=cycle,completed_steps=(cycle-1)*N,target_steps=LAST)
                resource=cap.run(cmd,directory,C/role/f'cycle{cycle:03d}.log',environment(),f'eonsim-fsi-n800-{role}-c{cycle}-{os.getpid()}.scope',d['cycle_timeout'])
                p.clean_resource(resource);check=accepted(role,cycle);verify()
                receipt=dict(cycle=cycle,resource=resource,accepted=check);dump(C/role/f'cycle{cycle:03d}-receipt.json',receipt);receipts.append(receipt)
            combine_outputs(role);dump(C/role/'numerical-completion.json',dict(accepted_steps=LAST,cycles=receipts,full_qualification=False))
            update(role,'analyzing',job='last2400-state-audit',completed_steps=LAST)
            resource=cap.run(audit_command(role),SOURCE,C/role/'audit.log',environment(),f'eonsim-fsi-n800-{role}-audit-{os.getpid()}.scope',d['audit_timeout'])
            p.clean_resource(resource)
            for name,h in read(C/role/'sealed-numerical-outputs.json').items():assert sha(name)==h
            report=read(OUT[role]/'eonsim-audit.json')
            assert report['analysis_script_sha256']==ANALYZER and report['steps']==LAST and report['first_step']==WARMUP+1 and report['sampled_steps']==3*N
            assert report['analysis_window']['initial_step']==WARMUP and report['samples_per_cycle']==N
            mean=report['harmonics']['mid_radial_displacement']['mean'];target=.02*report['infinite_plane_strain_compliance']
            gates=dict(periodic=report['periodic'],quality=all(v['passed'] for v in report['quality_gates'].values()),
                       positive_jacobians=min(report['minimum_fluid_jacobian'],report['minimum_solid_jacobian'])>0,
                       lame_mean=abs(mean-target)/abs(target)<.02)
            dump(C/role/'completion.json',dict(audit_resource=resource,report_sha256=sha(OUT[role]/'eonsim-audit.json'),
                 gates=gates,lame_relative_error=abs(mean-target)/abs(target),immutable_numerical_outputs=True,full_qualification=False))
            update(role,'completed',gates=gates,completed_steps=LAST)
    except BaseException as error:
        dump(C/role/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update(role,'failed',error=str(error));raise

def budget_worker():
    import numpy as np
    verify();fields=module('fields',SOURCE/'build/prod48-20261107/compare-pressure-fields.py')
    plan=dict(coarse=OUT['coarse'],time=OLD['fine'],fine=OUT['fine'])
    def study(solver,path):
        audit=C/'original-n400-audit.json' if path==OLD['fine'] else path/'eonsim-audit.json'
        return fields.Study(path/'case.json',path,audit)
    context=dict(out=C/'budget',dump=dump,study=study,fields=fields,np=np,math=math,EXPECTED_ANALYZER=ANALYZER)
    kernel=SOURCE/'build/prod48-20261107/s24-n800-budget-kernel.py';exec(compile(kernel.read_text(),str(kernel),'exec'),context)
    receipts={role:read(status(role)) for role in OUT};assert all(v['state']=='completed' for v in receipts.values())
    context['analyze']('eonsim',plan,receipts)

def budget():
    assert not status('budget').exists();d=execution_review();p=proof();cap=module('cap',C/'bounded_cgroup_job_2g.py')
    try:
        update('budget','waiting_for_complete_families',holds_locks=False)
        while True:
            states={role:read(status(role)) if status(role).exists() else {'state':'not_started'} for role in OUT}
            assert all(v['state']!='failed' for v in states.values()),'A required fresh producer failed'
            if all(v['state']=='completed' for v in states.values()):break
            time.sleep(10)
        with (W/LOCK['budget']).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{19});os.nice(19)
            while cap.available()<=10*1024**3:time.sleep(10)
            verify();update('budget','analyzing')
            resource=cap.run([sys.executable,C/'budget-guard.py',sys.executable,C/'controller.py','budget-worker'],SOURCE,C/'budget/budget.log',environment(),f'eonsim-fsi-n800-budget-{os.getpid()}.scope',d['budget_timeout'])
            p.clean_resource(resource);report=read(C/'budget/eonsim/budget.json')
            dump(C/'budget/completion.json',dict(resource=resource,budget_sha256=sha(C/'budget/eonsim/budget.json'),passed=report['passed'],full_qualification=False))
            update('budget','completed',passed=report['passed'])
    except BaseException as error:
        dump(C/'budget/failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('budget','failed',error=str(error));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','verify','run','budget','budget-worker'));parser.add_argument('--role',choices=('coarse','fine'));args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='verify':print(json.dumps(verify()))
    elif args.action=='run':run(args.role)
    elif args.action=='budget-worker':budget_worker()
    else:budget()
