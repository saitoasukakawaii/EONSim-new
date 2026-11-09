"""Prepare/run a separate c36 L24 study only after the complete native proof review."""
import argparse,fcntl,hashlib,importlib.util,json,math,os,shutil,sys,time,traceback
from pathlib import Path
import xml.etree.ElementTree as ET
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
P=W/'length24-native-extension-proof-4f5f26d';R=W/'length24-native-proof-review-b002c06'
C=W/'length24-native6400-extension-98ee0f9'
OUT=D/'elastic-s24-l1-n200-L24-native6400-c36-98ee0f9'
STATUS=W/'length24-native6400-extension-current.json';SOURCE=C/'source'
BASE='98ee0f93d04537b7cf8a9a5045c501ac6dcce806'
read=lambda p:json.loads(p.read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),control=str(C),
        adopted=(C/'adoption.json').exists(),full_qualification=False,**kw)
    t=STATUS.with_suffix('.tmp');dump(t,value);t.replace(STATUS);print(json.dumps(value),flush=True)
def inspect():
    states={}
    for label,name in [('proof','length24-native-extension-proof-current.json'),('review','length24-native-proof-review-current.json')]:
        p=W/name;states[label]=read(p)['state'] if p.exists() else 'absent'
    return dict(ready=all(x=='completed' for x in states.values()),states=states,
        prepared=C.exists(),output_exists=OUT.exists(),execution_status_exists=STATUS.exists(),adopted=(C/'adoption.json').exists())
def evidence():
    assert inspect()['ready'],'Complete numerical proof and separate raw review are both required'
    assert sha(P/'controller.py')=='1e150dd1bf8df239d6f5de9d7de53bc62ed07abbd2481d2fb49cbd80aee5c062'
    assert sha(P/'definition.json')=='6320690f7d943b8ff0f3677a41b34c7faadbead5b1fe4f8f0f8c234250f082ed'
    proof=module('proof',P/'controller.py');pc=read(P/'completion.json');rc=read(R/'completion.json')
    assert sha(P/'report.json')==pc['report_sha256'] and sha(R/'raw-review.json')==rc['raw_review_sha256']
    report=read(P/'report.json');review=read(R/'raw-review.json')
    assert report['passed'] and not report['adopted'] and report['immutable_inputs_unchanged']
    assert review['passed'] and review['all_reported_metrics_exactly_recomputed'] and not review['adopted']
    assert review['decision']=='eligible_for_separate_l24_6400_extension_review'
    assert review['proof_report_sha256']==sha(P/'report.json') and review['proof_definition_sha256']==sha(P/'definition.json')
    assert review['field_pairs']==report['field_pairs'] and len(review['field_pairs'])==210
    assert review['native_pairs']==report['native_pairs'] and len(review['native_pairs'])==11
    for resource in pc['resources'].values():proof.clean_resource(resource)
    proof.clean_resource(rc['resource'])
    for name,h in report['raw_hashes'].items():assert sha(name)==h
    for name,h in read(P/'immutable-inputs.json').items():assert sha(name)==h
    return proof
def numerical_command():
    return list(map(str,[sys.executable,C/'execution-guard.py',OUT/'eonsim','-case','case.json',
        '-checkpoint',OUT/'checkpoint','-restart',OUT/'checkpoint','-stop_after',7200,'-solver_report',
        '-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2']))
def audit_command():
    return list(map(str,[sys.executable,C/'execution-guard.py',sys.executable,SOURCE/'scripts/audit_pressure_tube.py',
        '--case',OUT/'case.json','--work',OUT,'--first-step',6601,'--output',OUT/'eonsim-audit.json']))
def expected_case():
    cfg=read(D/P.name/'case.json');assert cfg['fsi']['steps']==6400 and cfg['fsi']['checkpoint_interval']==200
    cfg['fsi']['steps']=7200
    return cfg
def prepare():
    assert not C.exists() and not OUT.exists() and not STATUS.exists()
    os.sched_setaffinity(0,{14});os.nice(19)
    proof=evidence();assert shutil.disk_usage('/mnt/d').free>24*1024**3
    C.mkdir();OUT.mkdir();shutil.copy2(__file__,C/'controller.py')
    pd=read(P/'definition.json')
    shutil.copytree(P/'source',SOURCE,ignore=shutil.ignore_patterns('__pycache__'))
    for name,h in pd['source_hashes'].items():assert sha(SOURCE/name)==h
    for name in ('bounded_cgroup_job_2g.py','execution-guard.py'):shutil.copy2(P/name,C/name)
    for name in ('fluid.msh','solid.msh','geometry.json','eonsim'):
        shutil.copy2(D/P.name/name,OUT/name);assert sha(OUT/name)==pd['input_hashes'][name]
    dump(OUT/'case.json',expected_case())
    hashes=proof.seed(D/P.name/'original6400',6400,OUT/'checkpoint')
    assert hashes==pd['seed_hashes']['6400']
    for name,src in [('original-audit.json',P/'original-audit.json'),('native-proof-report.json',P/'report.json'),
        ('native-proof-review.json',R/'raw-review.json'),('original-stage-checks.json',D/'elastic-s24-l1-n200-L24-bounded-postprocess-e771355/accepted-stage-checks.json')]:shutil.copy2(src,C/name)
    bindings={str(p):sha(p) for p in [P/'definition.json',P/'report.json',P/'completion.json',R/'raw-review.json',R/'completion.json',
        P/'original-audit.json',W/'length24-bounded-postprocess-handoff-e771355/audit-completion.json']}
    bindings.update({str(p):sha(p) for p in proof.generation(D/P.name/'original6400',6400).iterdir()})
    dump(C/'evidence-bindings.json',bindings)
    dump(C/'definition.json',dict(base=BASE,controller_sha256=sha(C/'controller.py'),source_hashes=pd['source_hashes'],
        input_hashes={name:sha(OUT/name) for name in ('case.json','geometry.json','fluid.msh','solid.msh','eonsim')},
        evidence_bindings_sha256=sha(C/'evidence-bindings.json'),cap_sha256=sha(C/'bounded_cgroup_job_2g.py'),
        guard_sha256=sha(C/'execution-guard.py'),original_seed_hashes=hashes,original_step=6400,final_step=7200,
        numerical_steps=800,first_audited_step=6601,stored_audit_states=600,cycles=36,phases=200,
        cpus=[14],nice=19,shared_cpu=True,lock='length24-extension.lock',memory_max_bytes=2*1024**3,swap_max_bytes=0,
        admission_bytes=10*1024**3,running_floor_bytes=8*1024**3,numerical_timeout=18000,audit_timeout=14400,
        numerical_command=numerical_command(),audit_command=audit_command(),
        periodic_limit=1e-5,lame_limit=.02,kinematic_limit=1e-12,mass_limit=1e-9,divergence_limit=1e-12,
        adopted=False,scope='Separate original-native6400 to7200 extension; no original process signaled or frozen run modified. Original c32 periodic failure and matched c32 length comparison remain. Audit all600 states6601..7200 with actual6600 endpoint. No automatic physics qualification or replacement of old evidence.'))
    print(json.dumps(dict(prepared=True,definition_sha256=sha(C/'definition.json'),adopted=False)),flush=True)
def verify():
    definition=read(C/'definition.json')
    assert sha(C/'controller.py')==definition['controller_sha256']==sha(Path(__file__))
    assert definition['cpus']==[14] and definition['shared_cpu'] and definition['nice']==19 and definition['lock']=='length24-extension.lock'
    assert [definition[k] for k in ('memory_max_bytes','swap_max_bytes','admission_bytes','running_floor_bytes')]==[2*1024**3,0,10*1024**3,8*1024**3]
    assert [definition[k] for k in ('original_step','final_step','numerical_steps','first_audited_step','stored_audit_states','cycles','phases')]==[6400,7200,800,6601,600,36,200]
    assert definition['numerical_timeout']==18000 and definition['audit_timeout']==14400
    assert definition['numerical_command']==numerical_command() and definition['audit_command']==audit_command()
    assert read(OUT/'case.json')==expected_case()
    for name,h in definition['source_hashes'].items():assert sha(SOURCE/name)==h
    for name,h in definition['input_hashes'].items():assert sha(OUT/name)==h
    assert sha(C/'bounded_cgroup_job_2g.py')==definition['cap_sha256']=='5070df17d8c299ea4bc393971e69fcc77f09821c1d0b895df6074c7a9997a939'
    assert sha(C/'execution-guard.py')==definition['guard_sha256']=='5fe97dffd47ecca76da8ff183cd2ddb309d1e06d32210d71ab2d90977434e036'
    assert sha(C/'evidence-bindings.json')==definition['evidence_bindings_sha256']
    for name,h in read(C/'evidence-bindings.json').items():assert sha(name)==h
    return definition
def seal_outputs(proof):
    cfg=read(OUT/'case.json');dt=cfg['fsi']['dt'];files={}
    for solid in (False,True):
        suffix='_solid' if solid else ''
        native=OUT/('solution_restart6400'+suffix+'.pvd')
        original=ET.parse(native).findall('.//DataSet');assert len(original)==800
        doc=ET.Element('VTKFile',type='Collection',version='0.1');collection=ET.SubElement(doc,'Collection')
        for step,item in enumerate(original,6401):
            assert abs(float(item.attrib['timestep'])-step*dt)<1e-9
            field=(native.parent/item.attrib['file']).resolve(strict=True);assert field.is_relative_to(OUT)
            files[str(field)]=sha(field);item.attrib['file']=os.path.relpath(field,OUT);collection.append(item)
        ET.ElementTree(doc).write(OUT/('solution'+suffix+'.pvd'),encoding='utf-8',xml_declaration=True)
    for folder in (OUT/'checkpoint',SOURCE):
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files[str(p)]=sha(p)
    for name in ('case.json','fluid.msh','solid.msh','geometry.json','eonsim','solution.pvd','solution_solid.pvd','solution_restart6400.pvd','solution_restart6400_solid.pvd'):
        files[str(OUT/name)]=sha(OUT/name)
    for p in (C/'solve.log',C/'solve.resource.json'):files[str(p)]=sha(p)
    assert proof.generation(OUT/'checkpoint',7200).exists()
    dump(C/'sealed-numerical-outputs.json',files)
    return files
def run():
    assert not STATUS.exists() and not (C/'adoption.json').exists() and not (C/'solve.log').exists()
    os.sched_setaffinity(0,{14});os.nice(19)
    proof=evidence();definition=verify();review=read(C/'execution-review.json')
    assert review['decision']=='run_l24_native6400_to7200_after_complete_proof'
    assert review['definition_sha256']==sha(C/'definition.json') and review['proof_report_sha256']==sha(P/'report.json')
    assert review['raw_review_sha256']==sha(R/'raw-review.json')
    try:
        update('waiting_for_private_extension_resources')
        with (W/'length24-extension.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);cap=module('cap',C/'bounded_cgroup_job_2g.py')
            while cap.available()<=10*1024**3:time.sleep(10)
            verify();assert shutil.disk_usage('/mnt/d').free>24*1024**3
            assert {p.name:sha(p) for p in proof.generation(OUT/'checkpoint',6400).iterdir()}==definition['original_seed_hashes']
            dump(C/'adoption.json',dict(adopted=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                definition_sha256=sha(C/'definition.json'),execution_review_sha256=sha(C/'execution-review.json'),
                original_numerical_signals=[],full_qualification=False))
            prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
            env={k:v for k,v in os.environ.items() if not k.startswith(('OMPI_','PMIX_','PRTE_')) and k not in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH')}
            env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR='/tmp')
            dump(C/'solve-command.json',numerical_command());update('running',job='native6400-to7200')
            numeric=cap.run(numerical_command(),OUT,C/'solve.log',env,f'eonsim-l24-c36-solve-{os.getpid()}.scope',18000)
            proof.clean_resource(numeric);rows=proof.accepted(C/'solve.log',6401,7200,True)
            assert all(abs(float(row['time'])-int(row['fsi_step'])*read(OUT/'case.json')['fsi']['dt'])<1e-9 for row in rows)
            files=seal_outputs(proof)
            dump(C/'numerical-completion.json',dict(resource=numeric,accepted_steps=800,final_step=7200,
                immutable_outputs_sha256=sha(C/'sealed-numerical-outputs.json'),full_qualification=False))
            while cap.available()<=10*1024**3:time.sleep(10)
            dump(C/'audit-command.json',audit_command());update('analyzing',job='last600-state-audit')
            resource=cap.run(audit_command(),SOURCE,C/'audit.log',env,f'eonsim-l24-c36-audit-{os.getpid()}.scope',14400)
            proof.clean_resource(resource)
            for name,h in files.items():assert sha(name)==h
            for name,h in read(C/'evidence-bindings.json').items():assert sha(name)==h
            report=read(OUT/'eonsim-audit.json')
            assert report['steps']==7200 and report['first_step']==6601 and report['sampled_steps']==600
            assert report['samples_per_cycle']==200 and report['analysis_window']['initial_step']==6600
            assert report['analysis_script_sha256']==definition['source_hashes']['scripts/audit_pressure_tube.py']
            mean=report['harmonics']['mid_radial_displacement']['mean'];target=.02*report['infinite_plane_strain_compliance']
            gates=dict(periodic=report['periodic'],quality=all(v['passed'] for v in report['quality_gates'].values()),
                positive_jacobians=min(report['minimum_solid_jacobian'],report['minimum_fluid_jacobian'])>0,
                lame_mean=abs(mean-target)/abs(target)<.02)
            dump(C/'completion.json',dict(numerical_resource=numeric,audit_resource=resource,
                report_sha256=sha(OUT/'eonsim-audit.json'),gates=gates,lame_relative_error=abs(mean-target)/abs(target),
                immutable_outputs_unchanged=True,original_c32_periodic=False,adopted=True,full_qualification=False))
            update('completed',gates=gates)
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('inspect','prepare','verify','run'))
    action=parser.parse_args().action
    if action=='inspect':print(json.dumps(inspect()))
    elif action=='prepare':prepare()
    elif action=='verify':print(json.dumps(verify()))
    else:run()
