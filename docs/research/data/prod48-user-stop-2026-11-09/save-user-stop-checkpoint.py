"""Save the requested stopped progress; no numerical jobs or archive resumption."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
STOP=ROOT/'build/prod48-20261107/user-stop-20261109'
OUT=ROOT/'docs/research/data/prod48-user-stop-2026-11-09'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def read(p):return json.loads(p.read_text())
assert read(STOP/'report.json')['stopped'] and not OUT.exists()
OUT.mkdir();entries={};total=0
def copy(p,label):
    global total
    assert p.is_file() and p.stat().st_size<8*1024**2,p
    before=(p.stat().st_size,p.stat().st_mtime_ns);digest=sha(p)
    dest=OUT/label;assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest);assert sha(dest)==digest and before==(p.stat().st_size,p.stat().st_mtime_ns)
    total+=before[0];assert total<32*1024**2
    entries[label]=dict(source=str(p),bytes=before[0],sha256=digest)
for p in STOP.iterdir():
    if p.is_file():copy(p,'stop/'+p.name)
copy(ROOT/'build/prod48-20261107/stop-all-prod48-user-20261109.py','stop/controller.py')
copy(Path(__file__),'save-user-stop-checkpoint.py')
for label,folder in [('mature-screen',W/'fsi-retained-lu-mature-screen-b8d1c76'),
                     ('mature-review',W/'fsi-retained-lu-mature-review-3b08e4f'),
                     ('n800-family',W/'fsi-s24-n800-lu32-family-3b08e4f')]:
    for p in folder.iterdir():
        if p.is_file() and p.suffix in ('.json','.py','.log'):copy(p,label+'/'+p.name)
    if label=='n800-family':
        for role in ('fine','coarse','budget'):
            for p in (folder/role).glob('*'):
                if p.is_file() and p.suffix=='.json':copy(p,label+'/'+role+'/'+p.name)
        for p in (folder/'source').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:copy(p,label+'/source/'+p.relative_to(folder/'source').as_posix())
analysis=W/'alpha1-native200-lu32-recovery-a3e1c87/n400-analysis.json'
copy(analysis,'alpha1-n400-analysis.json')
copy(W/'alpha1-native200-lu32-recovery-a3e1c87/n400-analysis.resource.json','alpha1-n400-analysis.resource.json')
for path in read(STOP/'after-statuses.json'):
    p=Path(path);copy(p,'terminal-statuses/'+p.name)
snapshot=subprocess.run(['/usr/bin/python3',str(ROOT/'build/prod48-20261107/compact-active-studies-v7-20261109.py')],capture_output=True,text=True,timeout=30)
assert snapshot.returncode==0,snapshot.stderr
(OUT/'stopped-progress.json').write_text(snapshot.stdout)
final=read(OUT/'stopped-progress.json')
assert all(not x.get('active_solver_pids') for x in final['active_numeric_studies'])
partial=[]
for name in ('elastic-length24-complete-sample-2026-11-09','length24-native-extension-proof-2026-11-09',
             'fsi-retained-lu-mature-proof-2026-11-09','fsi-s24-n800-family-execution-2026-11-09'):
    folder=ROOT/'docs/research/data'/name;store=D/'repository-archives'/name
    parts=sorted(store.glob('part*.tar.xz'))
    partial.append(dict(name=name,parts_present=len(parts),local_bytes=sum(p.stat().st_size for p in parts),
        archives_json_exists=(folder/'archives.json').exists(),index_staging_exists=(folder/'index-staging.json').exists(),
        local_store=str(store),qualification=False,scope='Interrupted capture retained locally; parts are not asserted complete or staged by this checkpoint.'))
dump(OUT/'interrupted-captures.json',partial)
dump(OUT/'copied-files.json',entries)
dump(OUT/'summary.json',dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),user_requested_stop=True,
    automation_status='PAUSED',background_controllers_stopped=20,owned_scopes_empty=9,
    new_user_authorization='Commit and push current progress to the development branch despite incomplete acceptance.',
    branch='codex/fsi-production-48h-20261107',full_qualification=False,pr_created=False,merge=False,
    raw_numerical_rerun=False,automatic_resume_authorized=False,copied_files=len(entries),copied_bytes=total,
    boundary='Small immutable stop/control/report snapshot. Already committed complete archives remain ordinary Git blobs. Interrupted large captures and unfinished raw trajectories remain on the local disks and are not represented as fully archived or qualified.'))
print(json.dumps(dict(output=str(OUT),copied_files=len(entries),bytes=total,partial_captures=partial)))
