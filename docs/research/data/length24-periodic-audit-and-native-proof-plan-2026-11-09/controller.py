"""Validate a longer final time using sealed L24 states; never adopt an extension."""
import argparse, fcntl, hashlib, importlib.util, json, math, os, re, shutil
import sys, time, traceback
from pathlib import Path
import xml.etree.ElementTree as ET

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
W = Path('/home/tfblab633/EONSim-prod48-20261107')
D = Path('/mnt/d/EONSim-prod48-20261107')
OLD = D/'elastic-s24-l1-n200-L24-ramp16-c32'
PRIOR = W/'length24-bounded-postprocess-handoff-e771355'
AUDIT = D/'elastic-s24-l1-n200-L24-bounded-postprocess-e771355/eonsim-audit.json'
C = W/'length24-native-extension-proof-4f5f26d'
OUT = D/'length24-native-extension-proof-4f5f26d'
SOURCE = C/'source'
STATUS = W/'length24-native-extension-proof-current.json'
BASE = '4f5f26d7e70585383a9a9f5ea5f9163875df5a7e'
OPTIONS = ['-pc_factor_mat_solver_type', 'mumps', '-snes_lag_jacobian', '-2']
SEED_HASHES = {
    6200: {'manifest': 'e2bb90d01574f8270d549062de76372b8b81e48b3ec5e276f79ff641962a2b81',
           'state_rank0.h5': 'a0cf494cec0b370dda9f8d31e1e4323cf77a776cb02800a4b55e4534ab7c50fd'},
    6400: {'manifest': '066bd919ae7390eb897974bee8a0cb357f0cb25e154c5ecb7736c23a12f4faf0',
           'state_rank0.h5': '0039c7bb2031b69f2a21db6e535c1219402075928801bc969426fbdf251d9571'}}
read = lambda p: json.loads(Path(p).read_text())

def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def dump(p, value):
    Path(p).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def update(state, **extra):
    value = dict(state=state, pid=os.getpid(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 control=str(C), adopted=False, full_qualification=False, **extra)
    tmp=STATUS.with_suffix('.tmp'); dump(tmp,value); tmp.replace(STATUS)
    print(json.dumps(value), flush=True)

def generation(folder, step):
    matches=[]
    for p in Path(folder).glob('*/manifest'):
        tokens=p.read_text().split()
        if int(tokens[2]) == step:
            assert tokens[0]=='EONSim_checkpoint_v3' and int(tokens[1])==1
            matches.append(p.parent)
    assert len(matches)==1, (str(folder),step,len(matches))
    return matches[0]

def seed(folder, step, destination):
    src=generation(folder,step)
    before={p.name:sha(p) for p in src.iterdir() if p.is_file()}
    assert set(before)=={'manifest','state_rank0.h5'}
    destination.mkdir(); shutil.copytree(src,destination/src.name)
    (destination/'current').write_text('EONSim_checkpoint_v3 '+src.name+'\n')
    assert before=={p.name:sha(p) for p in (destination/src.name).iterdir() if p.is_file()}
    assert before=={p.name:sha(p) for p in src.iterdir() if p.is_file()}
    return before

def fields(folder, dt):
    result=[]
    for solid in (False,True):
        files=[p for p in Path(folder).glob('*.pvd') if ('_solid' in p.stem)==solid]
        assert len(files)==1, (str(folder),solid,files)
        mapping={}
        for element in ET.parse(files[0]).getroot().findall('.//DataSet'):
            t=float(element.attrib['timestep']); step=round(t/dt)
            assert abs(t-step*dt)<1e-9 and step not in mapping
            mapping[step]=(files[0].parent/element.attrib['file']).resolve()
        result.append(mapping)
    return result

def clean_resource(receipt):
    assert receipt['returncode']==0 and receipt['scope_seen']
    assert receipt['memory_max_bytes']==2*1024**3 and receipt['memory_swap_max_bytes']==0
    assert receipt['minimum_available_bytes']>=8*1024**3
    assert not receipt['remaining_scope_members'] and not receipt['cleanup']
    assert all(int(line.split()[1])==0 for line in receipt['memory_events'].splitlines())
    group=Path('/sys/fs/cgroup')/f'user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice'/receipt['unit']
    assert not group.exists() or not (group/'cgroup.procs').read_text().strip()

def accepted(log, first, last, reports):
    text=Path(log).read_text()
    rows=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('fsi_step=')]
    assert [int(row['fsi_step']) for row in rows]==list(range(first,last+1))
    for row in rows:
        assert math.isfinite(float(row['residual']))
        for key in ('endpoint_min_fluid_j','endpoint_min_solid_j'):
            assert math.isfinite(float(row[key])) and float(row[key])>0
    if reports:
        assert 'status=success' in text
        rep=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('solver_report ')]
        assert len(rep)==len(rows)
        assert all(int(r['snes_reason'])>0 and int(r['ksp_reason'])>0 for r in rep)
    return rows

def case_for_replay():
    case=read(OUT/'case.json')
    assert case['fsi']['steps']==6400 and case['fsi']['checkpoint_interval']==200
    case['mesh']='../fluid.msh'; case['fsi']['domains']['solid_mesh']='../solid.msh'
    case['fsi'].update(steps=7200,output_interval=1,checkpoint_interval=1)
    return case

def command(label, end):
    directory=OUT/label
    return list(map(str,[sys.executable,C/'execution-guard.py',OUT/'eonsim','-case','case.json',
        '-checkpoint',directory/'checkpoint','-restart',directory/'checkpoint','-stop_after',end,
        '-solver_report','-log_view',':profile.txt',*OPTIONS]))

def immutable():
    return {str(p):sha(p) for p in map(Path,read(C/'immutable-inputs.json'))}

def prepare():
    assert not C.exists() and not OUT.exists() and not STATUS.exists()
    os.sched_setaffinity(0,{14}); os.nice(19)
    completion=read(PRIOR/'audit-completion.json'); clean_resource(completion['resource'])
    assert completion['immutable_inputs_unchanged'] and not completion['periodic']
    assert completion['report_sha256']==sha(AUDIT)=='60daa871c263faf79d5e75975c76708d4ebbeb71582b52679eaf25bf9c246f2d'
    audit=read(AUDIT); assert audit['steps']==6400 and audit['sampled_steps']==600
    assert not audit['periodic'] and all(v['passed'] for v in audit['quality_gates'].values())
    provenance=read(OLD/'provenance.json'); assert provenance['options']==OPTIONS
    pd=read(PRIOR/'definition.json')
    for name,h in pd['original_input_hashes'].items(): assert sha(OLD/name)==h
    assert pd['original_input_hashes']['eonsim']=='2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12'
    assert shutil.disk_usage('/mnt/d').free>24*1024**3
    C.mkdir(); OUT.mkdir(); shutil.copy2(__file__,C/'controller.py')
    shutil.copytree(PRIOR/'source',SOURCE,ignore=shutil.ignore_patterns('__pycache__'))
    for name,h in pd['source_hashes'].items(): assert sha(SOURCE/name)==h
    shutil.copy2(PRIOR/'bounded_cgroup_job_2g.py',C/'bounded_cgroup_job_2g.py')
    shutil.copy2(PRIOR/'analysis-guard.py',C/'execution-guard.py')
    assert sha(C/'bounded_cgroup_job_2g.py')==pd['cap_sha256']
    assert sha(C/'execution-guard.py')==pd['guard_sha256']
    for name in pd['original_input_hashes']: shutil.copy2(OLD/name,OUT/name)
    for step in (6200,6400): assert seed(OLD/'checkpoint',step,OUT/f'original{step}')==SEED_HASHES[step]
    shutil.copy2(AUDIT,C/'original-audit.json'); shutil.copy2(PRIOR/'audit-completion.json',C/'original-audit-completion.json')
    dump(C/'scales.json',audit['scales'])
    cfg=read(OUT/'case.json'); mapping=fields(OLD/'sample',cfg['fsi']['dt'])
    accepted(OLD/'sample.log',5801,6400,False)
    paths={AUDIT,PRIOR/'audit-completion.json',OLD/'provenance.json',OLD/'sample.log',OLD/'sample-command.json'}
    paths.update(OLD/name for name in pd['original_input_hashes'])
    paths.update((OLD/'sample').glob('*.pvd'))
    for step in (6200,6400): paths.update(generation(OLD/'checkpoint',step).iterdir())
    for one in mapping:
        assert all(step in one for step in range(6201,6401))
        paths.update(one[step] for step in range(6201,6401))
    dump(C/'oracle-fields.json',[{str(step):str(one[step]) for step in range(6201,6401)} for one in mapping])
    dump(C/'immutable-inputs.json',{str(p):sha(p) for p in sorted(paths) if p.is_file()})
    (OUT/'replay200').mkdir(); dump(OUT/'replay200/case.json',case_for_replay())
    seed(OUT/'original6200',6200,OUT/'replay200/checkpoint')
    dump(C/'definition.json',dict(base=BASE,controller_sha256=sha(C/'controller.py'),
        source_hashes=pd['source_hashes'],input_hashes=pd['original_input_hashes'],seed_hashes=SEED_HASHES,
        cap_sha256=sha(C/'bounded_cgroup_job_2g.py'),guard_sha256=sha(C/'execution-guard.py'),
        scopes='fresh owned 2GiB/swap0 scopes only',cpus=[14],nice=19,shared_cpu=True,
        memory_max_bytes=2*1024**3,swap_max_bytes=0,admission_bytes=10*1024**3,running_floor_bytes=8*1024**3,
        proof_steps=[6200,6400],replay_steps=[6390,6400],new_final_step=7200,
        planned_commands={'replay200':command('replay200',6400),'replay10':command('replay10',6400)},
        timeouts={'replay200':7200,'replay10':1200,'comparison':7200},
        immutable_manifest_sha256=sha(C/'immutable-inputs.json'),oracle_fields_sha256=sha(C/'oracle-fields.json'),
        original_audit_sha256=sha(C/'original-audit.json'),scales_sha256=sha(C/'scales.json'),
        nodal_limit=2e-9,history_limit=2e-9,normalized_mass_limit=1e-8,legacy_clock_limit=1e-12,
        original_native_boundary_pairs=1,replay_native_pairs=10,field_pairs=210,adopted=False,
        scope='Replay6201..6400 with final step7200 and unchanged physics, then native6390..6400 replay. Original only saved native states every200steps: compare all11datasets at6400 plus10 replay boundaries; all210 five-field pairs. Legacy v3 clock tolerance only. No v4 claim, no cost claim, no extended production, no replacement of failed c32 periodic audit.'))
    assert immutable()==read(C/'immutable-inputs.json')
    print(json.dumps(dict(prepared=True,definition_sha256=sha(C/'definition.json'),adopted=False)),flush=True)

def verify_plan():
    definition=read(C/'definition.json')
    assert definition['base']==BASE and definition['controller_sha256']==sha(C/'controller.py')==sha(Path(__file__))
    assert definition['cpus']==[14] and definition['nice']==19 and definition['shared_cpu']
    assert [definition[k] for k in ('memory_max_bytes','swap_max_bytes','admission_bytes','running_floor_bytes')]==[2*1024**3,0,10*1024**3,8*1024**3]
    assert definition['proof_steps']==[6200,6400] and definition['replay_steps']==[6390,6400] and definition['new_final_step']==7200
    assert definition['planned_commands']=={'replay200':command('replay200',6400),'replay10':command('replay10',6400)}
    assert definition['timeouts']=={'replay200':7200,'replay10':1200,'comparison':7200}
    for name,h in definition['source_hashes'].items(): assert sha(SOURCE/name)==h
    for name,h in definition['input_hashes'].items(): assert sha(OUT/name)==h
    for filename,key in [('bounded_cgroup_job_2g.py','cap_sha256'),('execution-guard.py','guard_sha256'),
        ('immutable-inputs.json','immutable_manifest_sha256'),('oracle-fields.json','oracle_fields_sha256'),
        ('original-audit.json','original_audit_sha256'),('scales.json','scales_sha256')]: assert sha(C/filename)==definition[key]
    assert read(OUT/'replay200/case.json')==case_for_replay()
    for step in (6200,6400):
        assert {p.name:sha(p) for p in generation(OUT/f'original{step}',step).iterdir()}==SEED_HASHES[step]
    assert immutable()==read(C/'immutable-inputs.json')
    return definition

def worker():
    sys.path.insert(0,str(SOURCE/'scripts'))
    import h5py
    import numpy as np
    from audit_pressure_tube import Domain, eonsim_frame
    definition=verify_plan(); raw={}; checks=[]; native=[]
    cfg=read(OUT/'case.json'); scales=read(C/'scales.json')
    domains=[Domain(OUT/'fluid.msh'),Domain(OUT/'solid.msh')]
    maps={'original':[{int(k):Path(v) for k,v in one.items()} for one in read(C/'oracle-fields.json')]}
    for label in ('replay200','replay10'): maps[label]=fields(OUT/label,cfg['fsi']['dt'])
    for left,right,steps in [('original','replay200',range(6201,6401)),('replay200','replay10',range(6391,6401))]:
        for step in steps:
            metrics={}
            for index,domain in enumerate(domains):
                paths=[maps[label][index][step] for label in (left,right)]
                values=[eonsim_frame(p,domain,solid=bool(index)) for p in paths]
                for value in values: domain.geometry(value,'displacement' if index else 'mesh_displacement')
                for name,scale in scales[index].items():
                    node=max(abs(a-b) for n in domain.nodes for a,b in zip(values[0][n][name],values[1][n][name]))
                    mass=domain.rms_difference(values[0],values[1],name)/scale
                    assert math.isfinite(node) and node<2e-9 and math.isfinite(mass) and mass<1e-8
                    metrics[f'{index}:{name}']=dict(node=node,normalized_mass=mass)
                for p in paths: raw[str(p)]=sha(p)
            checks.append(dict(left=left,right=right,step=step,fields=metrics))
            if len(checks)%20==0: print(json.dumps(dict(field_pairs_completed=len(checks))),flush=True)
    for left,right,steps in [('original6400','replay200',[6400]),('replay200','replay10',range(6391,6401))]:
        for step in steps:
            folders=[OUT/left if left.startswith('original') else OUT/left/'checkpoint',OUT/right/'checkpoint']
            files=[generation(folder,step)/'state_rank0.h5' for folder in folders]; metrics={}
            with h5py.File(files[0]) as a,h5py.File(files[1]) as b:
                assert set(a)==set(b) and len(a)==11
                assert int(a['metadata'][()][8])==step
                for name in a:
                    x,y=a[name][()],b[name][()]; assert x.shape==y.shape and x.dtype==y.dtype
                    assert np.all(np.isfinite(x)) and np.all(np.isfinite(y))
                    if x.dtype.kind in 'iu': assert np.array_equal(x,y); difference=0.
                    else:
                        difference=float(np.max(np.abs(x-y)))
                        assert difference<(1e-12 if name=='clock' else 2e-9),(left,right,step,name,difference)
                    metrics[name]=difference
            native.append(dict(left=left,right=right,step=step,datasets=metrics))
            for p in files: raw[str(p)]=sha(p)
    assert len(checks)==210 and len(native)==11
    for label,start in [('replay200',6200),('replay10',6390)]:
        assert read(OUT/label/'case.json')==case_for_replay()
        accepted(C/(label+'.log'),start+1,6400,True)
        clean_resource(read(C/(label+'.resource.json')))
        for p in [OUT/label/'case.json',C/(label+'.log'),C/(label+'.resource.json'),C/(label+'-command.json')]: raw[str(p)]=sha(p)
    assert immutable()==read(C/'immutable-inputs.json')
    dump(C/'report.json',dict(passed=True,eligible_for_separate_extension_review=True,adopted=False,
        full_qualification=False,definition_sha256=sha(C/'definition.json'),field_pairs=checks,native_pairs=native,
        raw_hashes=raw,immutable_inputs_unchanged=True,scope=definition['scope']))

def run():
    assert not STATUS.exists()
    os.sched_setaffinity(0,{14}); os.nice(19)
    verify_plan(); review=read(C/'plan-review.json')
    assert review['decision']=='run_bounded_l24_replay_proof_only' and review['definition_sha256']==sha(C/'definition.json')
    try:
        update('waiting_for_private_proof_lock')
        with (W/'length24-extension.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            spec=importlib.util.spec_from_file_location('cap',C/'bounded_cgroup_job_2g.py')
            cap=importlib.util.module_from_spec(spec); spec.loader.exec_module(cap)
            prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
            env={k:v for k,v in os.environ.items() if not k.startswith(('OMPI_','PMIX_','PRTE_')) and k not in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH')}
            env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR='/tmp')
            resources={}
            for label,start,timeout in [('replay200',6200,7200),('replay10',6390,1200)]:
                while cap.available()<=10*1024**3: update('waiting_for_memory',mode=label); time.sleep(10)
                if label=='replay10':
                    (OUT/label).mkdir(); dump(OUT/label/'case.json',case_for_replay())
                    seed(OUT/'replay200/checkpoint',start,OUT/label/'checkpoint')
                cmd=command(label,6400); dump(C/(label+'-command.json'),cmd); update('running',mode=label,start=start,end=6400)
                resources[label]=cap.run(cmd,OUT/label,C/(label+'.log'),env,f'eonsim-l24-proof-{label}-{os.getpid()}.scope',timeout)
                clean_resource(resources[label]); accepted(C/(label+'.log'),start+1,6400,True)
                assert generation(OUT/label/'checkpoint',6400).is_dir()
            dump(C/'numerical-completion.json',dict(resources=resources,adopted=False))
            while cap.available()<=10*1024**3: time.sleep(10)
            update('comparing_all_fields_and_available_native_histories')
            resources['comparison']=cap.run([sys.executable,C/'execution-guard.py',sys.executable,C/'controller.py','worker'],SOURCE,C/'compare.log',env,f'eonsim-l24-proof-compare-{os.getpid()}.scope',7200)
            clean_resource(resources['comparison']); assert read(C/'report.json')['passed']
            dump(C/'completion.json',dict(resources=resources,report_sha256=sha(C/'report.json'),adopted=False,full_qualification=False))
            update('completed',passed=True,eligible_for_separate_extension_review=True)
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc()))
        update('failed',error=str(error)); raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['prepare','verify','run','worker'])
    action=parser.parse_args().action
    if action=='prepare': prepare()
    elif action=='verify': print(json.dumps(dict(verified=True,definition_sha256=sha(C/'definition.json'),plan=verify_plan())),flush=True)
    elif action=='run': run()
    else: worker()
