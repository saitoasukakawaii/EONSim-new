"""Preserve the hard-link rejection and retry only the unfinished captures."""
import hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107')
status=work/'followup-capture-retry-current.json';assert not status.exists();os.sched_setaffinity(0,{9})
def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),cpu=9,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(status);print(json.dumps(value),flush=True)
try:
    failed=root/'docs/research/data/pressure-s24-preflight-failed-2026-11-08'
    shutil.copy2(work/'followup-capture-current.json',failed/'queue-failure.json')
    (failed/'failure.json').write_text(json.dumps(dict(reason='TarFile emitted a valid in-archive hard link for svFSI last-state. The strict regular-member assertion rejected it; source data were untouched.',
        member='work/elastic-s24-l1-n400-probe-6093f01/reference/results/stFile_last.bin',
        target='work/elastic-s24-l1-n400-probe-6093f01/reference/results/stFile_005.bin',
        original_capture_sha256=hashlib.sha256((failed/'original-capture.py').read_bytes()).hexdigest(),
        archive_sha256=hashlib.sha256((failed/'part001.tar.xz').read_bytes()).hexdigest(),
        resolution='Retain original failure; new capture uses dereference=True and verifies every regular member against source bytes.'),indent=2)+'\n')
    for part in ('preflight','alpha1'):
        update('running',part=part)
        subprocess.run([sys.executable,str(Path(__file__).with_name('capture-production-followups.py')),'--part',part],cwd=root,check=True,timeout=3600)
    update('running',part='elastic-direct-options')
    spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-production-followups.py'))
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    assert json.loads((work/'elastic-direct-probe-054b64a/report.json').read_text())['complete']
    c.capture('elastic-direct-options-2026-11-08',c.tree('elastic-direct-probe-054b64a')+[c.completed('elastic-direct-probe-current.json')],
        [work/'elastic-direct-probe-054b64a/report.json',Path(__file__)])
    update('completed',parts=['preflight','alpha1','elastic-direct-options'],previous_completed_captures_reused=['time400','vector'])
except Exception as error:update('failed',error=str(error));raise
