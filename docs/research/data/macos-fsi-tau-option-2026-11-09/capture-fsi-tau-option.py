from pathlib import Path
import hashlib,json,tarfile,subprocess,shutil
root=Path.cwd(); run=root/'build/recompute-20261109'; out=root/'docs/research/data/macos-fsi-tau-option-2026-11-09';out.mkdir(exist_ok=False)
inputs=[run/'fsi-tau-option-check/run-v7aufg4r',run/'fsi-tau-old-checkpoint']
files=sorted(p for d in inputs for p in d.rglob('*') if p.is_file())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p.relative_to(root)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files}
archive=run/'archives/fsi-tau-option-tests.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for p in files:t.add(p,arcname=str(p.relative_to(root)),recursive=False)
with tarfile.open(archive,'r:gz') as t:
 assert set(t.getnames())==set(manifest)
 for m in t:
  data=t.extractfile(m).read();assert len(data)==manifest[m.name]['bytes'] and hashlib.sha256(data).hexdigest()==manifest[m.name]['sha256']
for src,name in [(inputs[0]/'summary.json','option-summary.json'),(inputs[1]/'summary.json','old-checkpoint-summary.json')]:shutil.copy2(src,out/name)
for name in ['fsi-tau-configure.log','fsi-tau-build.log','fsi-tau-option-check.log','check-fsi-tau-default-restart.py','check-fsi-tau-default-restart.log','capture-fsi-tau-option.py']:
 shutil.copy2(run/name,out/name)
(out/'source.patch').write_bytes(subprocess.check_output(['git','diff','--','CMakeLists.txt','include/eonsim/config.hpp','src/core/config.cpp','src/physics/fsi.cpp','scripts/cloud/selection.json']))
shutil.copy2(root/'tests/verify_fsi_stabilization_time.py',out/'verify_fsi_stabilization_time.py')
record=dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),files=manifest,archive=str(archive.relative_to(root)),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,decoded_all_members_verified=True,source_removed=False,scope='Release PETSc 3.25.6 macOS arm64; 1/2 ranks; explicit MUMPS icntl20=0. Debug and main-lock PETSc3.23.7 not run in this check.')
(out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='files'}));print('files',len(files))
