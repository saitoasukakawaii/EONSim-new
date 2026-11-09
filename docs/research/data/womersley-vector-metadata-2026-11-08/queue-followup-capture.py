"""Serialize read-only captures behind the existing N400 archive writer."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107')
status=work/'followup-capture-current.json';assert not status.exists();os.sched_setaffinity(0,{9})

def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),cpu=9,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(status);print(json.dumps(value),flush=True)

try:
    update('waiting_for_n400_capture',original_pid=6801,original_start='2305467')
    deadline=time.monotonic()+3600
    while True:
        try:
            stat=(Path('/proc/6801/stat')).read_text().rsplit(')',1)[1].split()
            if stat[19]!='2305467' or stat[0]=='Z':break
        except FileNotFoundError:break
        if time.monotonic()>deadline:raise TimeoutError('Prior capture has not finished')
        time.sleep(2)
    prior=json.loads((root/'docs/research/data/pressure-tube-n400-2026-11-08/archives.json').read_text())
    assert prior['verified_files']>0
    spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-production-followups.py'))
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    assert json.loads((work/'schur-vector-probe-fine-054b64a/report.json').read_text())['complete']
    assert json.loads((work/'gamg-probe-fine-6093f01/report.json').read_text())['complete']
    assert json.loads((work/'vector-cli-selection-054b64a/summary.json').read_text())['passed']
    names=['schur-vector-validation-054b64a','schur-vector-validation-054b64a-attempt2',
        'schur-vector-validation-054b64a-attempt3','schur-vector-probe-fine-054b64a','gamg-probe-fine-6093f01',
        'vector-cli-selection-054b64a','womersley-vector-metadata-check-054b64a']
    files=sum((c.tree(n) for n in names),[])+[c.completed('schur-vector-validation-retry3-current.json'),
        work/'schur-vector-validation-current.json',work/'schur-vector-validation-retry-current.json',
        work/'alpha1-option-window-current.json',work/'mpi-yield-option-054b64a.json']
    update('running',part='vector')
    c.capture('womersley-vector-metadata-2026-11-08',files,[work/'schur-vector-probe-fine-054b64a/report.json',
        work/'schur-vector-validation-054b64a-attempt3/combined-release-evidence.json',Path(__file__)])
    for part in ['preflight','alpha1']:
        update('running',part=part)
        subprocess.run([sys.executable,str(Path(__file__).with_name('capture-production-followups.py')),'--part',part],check=True,cwd=root,timeout=3600)
    update('completed',parts=['time400','vector','preflight','alpha1'])
except Exception as error:
    update('failed',error=str(error));raise
