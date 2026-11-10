"""Bind completed native fields and inherited hardlink aliases before archival."""
from pathlib import Path
import json,hashlib
b=Path(__file__).resolve().parent;root=b.parents[1];w=b/'reference-kinematic-elastic-s24-l1-n800-nu0-native25500';old=b/'reference-kinematic-elastic-s24-l1-n800-nu0';out=b/'reference-native-n800-dual-path-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert json.loads((b/'reference-native-n800-budget/svfsi/budget.json').read_text())['passed']
assert json.loads((b/'reference-native-n800-full-fields.json').read_text())['common_phases']==800
assert json.loads((w/'completion.json').read_text())['process']['exit_code']==0
mp=root/'docs/research/data/macos-kinematic-fine-n800-physics-cross-2026-11-10/raw-manifest.json';m=json.loads(mp.read_text());expected={x['path']:x for x in m['files']};files=[];pairs=[]
for step in range(23201,25600):
 if step==25500:continue
 p=w/'results'/f'result_{step}.vtu';row=expected[str(p.relative_to(w))];st=p.stat();assert not p.is_symlink() and st.st_size==row['bytes'] and sha(p)==row['sha256']
 paths=[p];alias=old/'results'/p.name
 if step<25500:
  assert alias.is_file() and not alias.is_symlink() and alias.samefile(p) and st.st_nlink==2;paths.append(alias)
 else:assert st.st_nlink==1
 for index,path in enumerate(paths):files.append(dict(path=str(path.relative_to(b)),bytes=row['bytes'],sha256=row['sha256'],step=step,allocated_bytes=st.st_blocks*512 if index==0 else 0,device=st.st_dev,inode=st.st_ino,links=st.st_nlink))
 pairs.append([str(x.relative_to(b)) for x in paths])
assert len(pairs)==2398 and len(files)==4697
out.write_text(json.dumps(dict(work=str(b),files=files,groups=pairs,count=len(files),source_manifest=str(mp),source_manifest_sha256=sha(mp),retained_steps=[23200,25500,25600],scope='Completed native2398 fields plus2299 original inherited hardlink aliases. Same inode counted once for allocated bytes. Native/original restart boundary25500, audit endpoint23200 and final25600 retained. Original independent overlap25501..25534 and all checkpoints/logs/inputs retained.'),indent=2)+'\n');print('Verified2398 unique fields,4697 paths; allocated',sum(x['allocated_bytes'] for x in files))
