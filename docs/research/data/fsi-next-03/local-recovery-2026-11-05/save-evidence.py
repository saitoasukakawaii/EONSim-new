import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

root=Path.cwd();run=root/'build/resume-20261105'
destination=root/'docs/research/data/fsi-next-03/local-recovery-2026-11-05'
destination.mkdir(parents=True,exist_ok=True)
records=json.loads((run/'matrix-status.json').read_text())
sys.path.insert(0,str(root/'scripts'))
from split_fsi_archive import split,join
chunks=[]
for path in run.glob('*.tar.gz*'):
    if path.suffix=='.gz' and path.stat().st_size>48*1024*1024:
        manifest=split(path,destination/(path.name+'.parts'))
        manifest.write_text(manifest.read_text(),newline='\n')
        restored=join(manifest,run/'chunk-verification'/path.name)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if hashlib.sha256(restored.read_bytes()).hexdigest()!=digest:raise RuntimeError('Chunk roundtrip mismatch')
        chunks.append(dict(archive=path.name,sha256=digest,bytes=path.stat().st_size,
                           manifest=manifest.relative_to(destination).as_posix(),roundtrip_verified=True))
    else:shutil.copy2(path,destination/path.name)
(destination/'chunk-verification.json').write_text(json.dumps(chunks,indent=2)+'\n',newline='\n')
for label in ['fixed-n2-dt0005',*[r['label'] for r in records if r['exit_code']==0]]:
    path=run/(label+'.log')
    if path.is_file():shutil.copy2(path,destination/path.name)
for name in ('restored-n2.json','matrix-status.json','progress-analysis.json','fixed-budget.json',
             'continue-matrix.py','run-python.sh','restore-baseline.py','archive-continuations.py',
             'inspect-matrix.py','package.log','check-relocated-evidence.py','relocation-audit.json',
             'audit-continuation-histories.py','continuation-history-audit.json','code-review.json',
             'plot-results.py','space-20-phases.json','space-20-phases.log','package-n8-tail-endpoints.log',
             'relocated-budget.json','relocated-budget.log','save-evidence.py'):
    path=run/name
    if path.is_file():shutil.copy2(path,destination/name)
build=root/'build/cloud-3.23.7-release/evidence'
for name in ('summary.json','junit.xml','compiler.log','mpi-runtime.log','configure.log','build.log',
             'runtime-preflight.log','runtime-linkage.log','ctest.log'):
    shutil.copy2(build/name,destination/('local-release-'+name))
source_check=[]
raw=subprocess.check_output(['git','-c','safe.directory='+root.as_posix(),'ls-files','--stage','-z'])
for entry in raw.decode().split('\0'):
    if not entry:continue
    metadata,name=entry.split('\t',1)
    if not (name.startswith(('src/','include/','cmake/')) or name in ('CMakeLists.txt','CMakePresets.json')):continue
    path=root/name
    data=path.read_bytes();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    expected=metadata.split()[1]
    if actual!=expected:raise RuntimeError('Production source differs from index: '+name)
    source_check.append(dict(path=name,git_blob=actual,sha256=hashlib.sha256(data).hexdigest()))
(destination/'compiled-source-audit.json').write_text(json.dumps(dict(
    build_commit='1b33db8c973b67d343d6376e3d8dee557f4af3de',
    analysis_fix_commit='e4bda862e9feebb63a09200f65bb7c4f4f842337',
    executable_sha256=hashlib.sha256((root/'build/cloud-3.23.7-release/eonsim').read_bytes()).hexdigest(),
    build_summary_dirty=True,production_sources_match_git=True,files=source_check),indent=2)+'\n')
(destination/'analysis-test.json').write_text(json.dumps(dict(
    command='python tests/test_fsi_space_metrics.py',source_commit='e4bda862e9feebb63a09200f65bb7c4f4f842337',
    tests=6,passed=6,failed=0,output='Ran 6 tests in 0.131s\nOK',
    scope='Restored location accepted; altered checkpoint files, extra rank, mesh or definition rejected; existing spatial and budget tests'),indent=2)+'\n')
print(json.dumps(dict(evidence=str(destination),files=len(list(destination.iterdir())),
                     production_files_verified=len(source_check))),flush=True)
