from pathlib import Path
import hashlib,json,tarfile,shutil,subprocess
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109';d=root/'docs/research/data/macos-fsi-tau-debug-2026-11-10';assert not d.exists();d.mkdir()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
r=json.loads((b/'fsi-tau-debug-check.log').read_text());old=json.loads((b/'fsi-tau-debug-old-checkpoint/summary.json').read_text());assert old['passed']
files=sorted([p for folder in [Path(r['work']),b/'fsi-tau-debug-old-checkpoint'] for p in folder.rglob('*') if p.is_file()]);rows=[dict(path=str(p.relative_to(b)),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
a=b/'archives/fsi-tau-debug-raw.tar.gz';assert not a.exists()
with tarfile.open(a,'w:gz') as t:
 for p in files:t.add(p,arcname=str(p.relative_to(b)),recursive=False)
with tarfile.open(a,'r:gz') as t:
 members=t.getmembers();assert len(members)==len(rows)
 for member,row in zip(members,rows):
  assert member.name==row['path'] and member.size==row['bytes']
  with t.extractfile(member) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256']
for name in ['fsi-tau-debug-build.log','fsi-tau-debug-check.log','fsi-tau-debug-old-checkpoint.log','check-fsi-tau-debug-default-restart.py','capture-fsi-tau-debug.py']:
 shutil.copy2(b/name,d/name)
shutil.copy2(root/'build/macos-debug/CMakeCache.txt',d/'CMakeCache.txt')
shutil.copy2(Path(r['work'])/'summary.json',d/'option-summary.json');shutil.copy2(b/'fsi-tau-debug-old-checkpoint/summary.json',d/'old-checkpoint-summary.json')
for name in ['verify_fsi_stabilization_time.py','verify_fsi_lu_reuse.py']:shutil.copy2(root/'tests'/name,d/name)
manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),build_mode='Debug',petsc='3.25.6',platform='macOS arm64',ranks=[1,2],binary_sha256={name:sha(root/name) for name in ['build/macos-debug/eonsim','build/macos-release/eonsim']},source_sha256={name:sha(root/name) for name in ['src/physics/fsi.cpp','src/physics/fsi_element.cpp','tests/verify_fsi_stabilization_time.py','tests/verify_fsi_lu_reuse.py']},archive=dict(path=str(a.relative_to(root)),bytes=a.stat().st_size,sha256=sha(a),all_members_verified=True),files=rows)
(d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(dict(files=len(rows),archive_bytes=a.stat().st_size,passed=True)))
