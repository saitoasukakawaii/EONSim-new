"""Reopen every completed L24 proof pair, without adopting a long extension."""
import argparse,fcntl,hashlib,importlib.util,json,math,os,shutil,sys,time,traceback
from pathlib import Path
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
P=W/'length24-native-extension-proof-4f5f26d';OUT=D/P.name
C=W/'length24-native-proof-review-b002c06'
STATUS=W/'length24-native-proof-review-current.json'
PROOF_STATUS=W/'length24-native-extension-proof-current.json'
read=lambda p:json.loads(p.read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),control=str(C),adopted=False,**kw)
    t=STATUS.with_suffix('.tmp');dump(t,value);t.replace(STATUS);print(json.dumps(value),flush=True)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def identity(pid):
    p=Path('/proc')/str(pid)
    try:
        x=(p/'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,start_ticks=int(x[19]),state=x[0])
    except FileNotFoundError:return None
def worker():
    import h5py,numpy as np
    definition=read(C/'definition.json');assert sha(P/'controller.py')==definition['proof_controller_sha256']
    assert sha(P/'definition.json')==definition['proof_definition_sha256']
    proof=module('proof_reader',P/'controller.py');completed=read(P/'completion.json')
    assert sha(P/'report.json')==completed['report_sha256']
    old=read(P/'report.json');assert old['passed'] and not old['adopted'] and old['immutable_inputs_unchanged']
    assert len(old['field_pairs'])==210 and len(old['native_pairs'])==11
    for resource in completed['resources'].values():proof.clean_resource(resource)
    pd=read(P/'definition.json')
    for name,h in pd['source_hashes'].items():assert sha(P/'source'/name)==h
    for name,h in pd['input_hashes'].items():assert sha(OUT/name)==h
    for name,h in read(P/'immutable-inputs.json').items():assert sha(Path(name))==h
    for name,h in old['raw_hashes'].items():assert sha(Path(name))==h
    sys.path.insert(0,str(P/'source/scripts'))
    from audit_pressure_tube import Domain,eonsim_frame
    cfg=read(OUT/'case.json');scales=read(P/'scales.json')
    domains=[Domain(OUT/'fluid.msh'),Domain(OUT/'solid.msh')]
    maps={'original':[{int(k):Path(v) for k,v in x.items()} for x in read(P/'oracle-fields.json')]}
    for label in ('replay200','replay10'):maps[label]=proof.fields(OUT/label,cfg['fsi']['dt'])
    checks=[];native=[]
    expected=[('original','replay200',i) for i in range(6201,6401)]+[('replay200','replay10',i) for i in range(6391,6401)]
    assert [(r['left'],r['right'],r['step']) for r in old['field_pairs']]==expected
    for left,right,step in expected:
        values={}
        for i,domain in enumerate(domains):
            frames=[eonsim_frame(maps[label][i][step],domain,solid=bool(i)) for label in (left,right)]
            for frame in frames:domain.geometry(frame,'displacement' if i else 'mesh_displacement')
            for name,scale in scales[i].items():
                node=max(abs(a-b) for n in domain.nodes for a,b in zip(frames[0][n][name],frames[1][n][name]))
                mass=domain.rms_difference(frames[0],frames[1],name)/scale
                assert math.isfinite(node) and node<2e-9 and math.isfinite(mass) and mass<1e-8
                values[f'{i}:{name}']=dict(node=node,normalized_mass=mass)
        checks.append(dict(left=left,right=right,step=step,fields=values))
        assert checks[-1]==old['field_pairs'][len(checks)-1]
        if len(checks)%20==0:print(json.dumps(dict(reviewed_field_pairs=len(checks))),flush=True)
    pairs=[('original6400','replay200',6400)]+[('replay200','replay10',i) for i in range(6391,6401)]
    assert [(r['left'],r['right'],r['step']) for r in old['native_pairs']]==pairs
    for left,right,step in pairs:
        folders=[OUT/left if left=='original6400' else OUT/left/'checkpoint',OUT/right/'checkpoint']
        files=[proof.generation(folder,step)/'state_rank0.h5' for folder in folders];metrics={}
        with h5py.File(files[0]) as a,h5py.File(files[1]) as b:
            assert set(a)==set(b) and len(a)==11 and int(a['metadata'][()][8])==step
            for name in a:
                x,y=a[name][()],b[name][()];assert x.shape==y.shape and x.dtype==y.dtype
                assert np.all(np.isfinite(x)) and np.all(np.isfinite(y))
                if x.dtype.kind in 'iu':assert np.array_equal(x,y);delta=0.
                else:
                    delta=float(np.max(np.abs(x-y)));assert delta<(1e-12 if name=='clock' else 2e-9)
                metrics[name]=delta
        native.append(dict(left=left,right=right,step=step,datasets=metrics));assert native[-1]==old['native_pairs'][len(native)-1]
    for label,first in [('replay200',6201),('replay10',6391)]:
        assert read(OUT/label/'case.json')==proof.case_for_replay()
        assert read(P/(label+'-command.json'))==pd['planned_commands'][label]
        proof.accepted(P/(label+'.log'),first,6400,True)
    for name,h in old['raw_hashes'].items():assert sha(Path(name))==h
    for name,h in read(P/'immutable-inputs.json').items():assert sha(Path(name))==h
    dump(C/'raw-review.json',dict(passed=True,decision='eligible_for_separate_l24_6400_extension_review',adopted=False,
        proof_report_sha256=sha(P/'report.json'),proof_definition_sha256=sha(P/'definition.json'),
        all_reported_metrics_exactly_recomputed=True,field_pairs=checks,native_pairs=native,raw_files_reopened=len(old['raw_hashes']),
        original_c32_periodic=False,full_qualification=False,
        scope='Separate executing-agent raw verification of all210five-field pairs and11native boundaries. Original native states only every200steps; no claim of200 original native histories, exactv4 clocks, extended production or physical acceptance.'))
def main():
    assert not C.exists() and not STATUS.exists()
    ps=read(PROOF_STATUS);assert ps['pid']==44437 and ps['state'] in ('running','comparing_all_fields_and_available_native_histories','completed')
    assert sha(P/'controller.py')=='1e150dd1bf8df239d6f5de9d7de53bc62ed07abbd2481d2fb49cbd80aee5c062'
    assert sha(P/'definition.json')=='6320690f7d943b8ff0f3677a41b34c7faadbead5b1fe4f8f0f8c234250f082ed'
    C.mkdir();shutil.copy2(__file__,C/'controller.py')
    for name in ('bounded_cgroup_job_2g.py','execution-guard.py'):shutil.copy2(P/name,C/name)
    pd=read(P/'definition.json')
    assert sha(C/'bounded_cgroup_job_2g.py')==pd['cap_sha256'] and sha(C/'execution-guard.py')==pd['guard_sha256']
    dump(C/'definition.json',dict(controller_sha256=sha(C/'controller.py'),proof_pid=44437,proof_identity=identity(44437),
        proof_controller_sha256=sha(P/'controller.py'),proof_definition_sha256=sha(P/'definition.json'),
        cpus=[14],nice=19,shared_cpu=True,cap_sha256=pd['cap_sha256'],guard_sha256=pd['guard_sha256'],
        memory_max_bytes=2*1024**3,swap_max_bytes=0,admission_bytes=10*1024**3,running_floor_bytes=8*1024**3,
        wait_timeout_seconds=21600,review_timeout_seconds=7200,adopted=False))
    try:
        update('waiting_for_complete_proof',holds_locks=False)
        deadline=time.monotonic()+21600
        while True:
            state=read(PROOF_STATUS)
            assert state['pid']==44437 and state['state']!='failed',state
            if state['state']=='completed':break
            p=identity(44437);original=read(C/'definition.json')['proof_identity']
            assert p and p['start_ticks']==original['start_ticks'] and p['state'] not in ('Z','X')
            assert time.monotonic()<deadline
            time.sleep(10)
        os.sched_setaffinity(0,{14});os.nice(19)
        with (W/'length24-extension.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            cap=module('cap',C/'bounded_cgroup_job_2g.py')
            while cap.available()<=10*1024**3:time.sleep(10)
            update('reviewing_all_raw_pairs')
            resource=cap.run([sys.executable,C/'execution-guard.py',sys.executable,C/'controller.py','--worker'],C,C/'review.log',dict(os.environ),f'eonsim-l24-proof-review-{os.getpid()}.scope',7200)
            proof=module('proof_guard',P/'controller.py');proof.clean_resource(resource)
            assert read(C/'raw-review.json')['passed']
            dump(C/'completion.json',dict(resource=resource,raw_review_sha256=sha(C/'raw-review.json'),adopted=False,full_qualification=False))
            update('completed',passed=True,eligible_for_separate_extension_review=True)
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise
if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:main()
