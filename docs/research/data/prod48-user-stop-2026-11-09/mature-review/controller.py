"""Reopen all completed mature-screen raw pairs in a separate bounded review."""
import fcntl,hashlib,importlib.util,json,os,shutil,sys,time,traceback
from pathlib import Path
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
W=Path('/home/tfblab633/EONSim-prod48-20261107');S=W/'fsi-retained-lu-mature-screen-b8d1c76'
C=W/'fsi-retained-lu-mature-review-3b08e4f';STATUS=W/'fsi-retained-lu-mature-review-current.json'
read=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def update(state,**kw):
    v=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),control=str(C),adopted=False,**kw)
    p=STATUS.with_suffix('.tmp');dump(p,v);p.replace(STATUS);print(json.dumps(v),flush=True)
def worker():
    m=module('screen_for_review',S/'controller.py');definition=m.verify();m.validate_completion()
    original=read(S/'report.json');assert original['numerical_passed'] and original['eligible'] and not original['adopted']
    proof=module('proof',m.P/'controller.py')
    for receipt in original['resources'].values():proof.clean_resource(receipt)
    proof.clean_resource(read(S/'completion.json')['comparison_resource'])
    assert definition['controller_sha256']==sha(S/'controller.py') and len(original['checks'])==176
    assert sum(x['datasets'] for x in original['checks'])==1584
    assert sha(S/'report.json')==read(S/'completion.json')['report_sha256']
    before={name:sha(Path(name)) for name in original['raw_hashes']};assert before==original['raw_hashes']
    output=C/'recomputed-report.json'
    def isolated_dump(path,value):
        assert Path(path)==S/'report.json' and not output.exists()
        dump(output,value)
    # Reuse the same frozen arithmetic, with a separate destination only.
    # No claim of an independent algorithm or external reviewer is made.
    m.dump=isolated_dump;m.worker();actual=read(output);assert actual==original
    assert before=={name:sha(Path(name)) for name in original['raw_hashes']}
    report=dict(passed=True,eligible=True,decision='eligible_for_separate_fsi_refined_time_plan_review',adopted=False,full_qualification=False,
        screen_definition_sha256=sha(S/'definition.json'),screen_report_sha256=sha(S/'report.json'),reviewer_sha256=sha(C/'controller.py'),
        all_reported_metrics_exactly_recomputed=True,field_pairs=176,native_pairs=144,native_datasets=1584,
        maximum_node=max(x['maximum_node'] for x in actual['checks']),maximum_mass=max(x['maximum_normalized_mass'] for x in actual['checks']),
        maximum_history=max(x['maximum_history'] for x in actual['checks']),maximum_legacy_clock=max(x['legacy_clock_difference'] for x in actual['checks']),
        cost_ratios=actual['cost_ratios'],raw_files_verified=len(before),
        scope='Separate full raw reread using the identical frozen comparator and unchanged thresholds. All metrics match exactly; no new numerical solve, no external/algorithm-independent review claim, no production adoption.')
    dump(C/'raw-review.json',report)
def run():
    assert not C.exists() and not STATUS.exists();C.mkdir();shutil.copy2(__file__,C/'controller.py')
    try:
        update('waiting_for_complete_screen',holds_locks=False)
        while True:
            status=read(W/'fsi-retained-lu-mature-screen-current.json')
            if status['state']=='failed':raise RuntimeError('Screen failed; no adoption or automatic retry')
            if status['state']=='completed':break
            time.sleep(10)
        original=read(S/'report.json')
        if not original['eligible']:
            dump(C/'rejection.json',dict(screen_report_sha256=sha(S/'report.json'),reason='Completed screen cost gate failed',adopted=False))
            update('completed_ineligible',eligible=False);return
        with (W/'mpi-option-independent-review.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{15});os.nice(19)
            shutil.copy2(S/'bounded_cgroup_job_2g.py',C/'bounded_cgroup_job_2g.py')
            assert sha(C/'bounded_cgroup_job_2g.py')=='5070df17d8c299ea4bc393971e69fcc77f09821c1d0b895df6074c7a9997a939'
            cap=module('cap',C/'bounded_cgroup_job_2g.py')
            while cap.available()<=10*1024**3:time.sleep(10)
            guard=C/'execution-guard.py'
            text=(S/'execution-guard.py').read_text();assert text.count('os.sched_setaffinity(0,{19})')==1
            guard.write_text(text.replace('os.sched_setaffinity(0,{19})','os.sched_setaffinity(0,{15})'))
            dump(C/'definition.json',dict(screen_definition_sha256=sha(S/'definition.json'),screen_controller_sha256=sha(S/'controller.py'),reviewer_sha256=sha(C/'controller.py'),
                cpu=15,nice=19,lock='mpi-option-independent-review.lock',memory_max_bytes=2*1024**3,swap_max_bytes=0,timeout_seconds=7200,
                admission_bytes=10*1024**3,running_floor_bytes=8*1024**3,guard_sha256=sha(guard),same_comparator=True,adopted=False))
            update('reviewing_all_raw_pairs')
            r=cap.run([sys.executable,guard,sys.executable,C/'controller.py','worker'],C,C/'review.log',os.environ.copy(),f'eonsim-fsi-lu-raw-review-{os.getpid()}.scope',7200)
            proof=module('proof',W/'length24-native-extension-proof-4f5f26d/controller.py');proof.clean_resource(r)
            report=read(C/'raw-review.json');assert report['passed'] and report['eligible']
            dump(C/'completion.json',dict(resource=r,raw_review_sha256=sha(C/'raw-review.json'),adopted=False));update('completed',eligible=True)
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='worker':worker()
    else:run()
