"""Byte-preserving compression of immutable frames strictly before published checkpoint."""
from pathlib import Path
import argparse,json,hashlib,subprocess,os,stat,time,re
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--through',type=int,required=True);a=p.parse_args();w=a.work.resolve();out=w.parent/(w.name+f'-frames-through{a.through}-compression.json');assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
marker,generation=(w/'checkpoint/current').read_text().split();manifest=w/'checkpoint'/generation/'manifest';tokens=manifest.read_text().split();assert marker==tokens[0]=='EONSim_checkpoint_v4';checkpoint=int(tokens[2]);assert a.through<checkpoint
cfg=json.loads((w/'definition.json').read_text());n=cfg['steps_per_cycle'];assert cfg['ranks']==1
assert json.loads((w/'early/receipt.json').read_text())['exit_code']==0
pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu$');selected=[];groups={}
for label in ['early','dense']:
 for q in sorted((w/label).glob('*.vtu')):
  m=pattern.fullmatch(q.name)
  if not m or int(m[1])>a.through:continue
  step=int(m[1]);assert step<checkpoint and not q.is_symlink();groups.setdefault((label,step),set()).add(m[2] or '');selected.append(q)
assert groups and all(v=={'','_boundary','_solid','_solid_boundary'} for v in groups.values())
assert {s for (label,s) in groups if label=='dense'}==set(range(29*n+1,a.through+1))
root=Path(__file__).resolve().parents[2];proof=dict(work=str(w),checkpoint_generation=generation,checkpoint_step=checkpoint,checkpoint_manifest_sha256=sha(manifest),through=a.through,source_sha256=sha(root/'src/physics/fsi.cpp'),controller_sha256=sha(Path(__file__)),selected_frames=len(groups),selected_files=len(selected),scope='src/physics/fsi.cpp writes per-step snapshots once and publishes checkpoint before that step output; only strictly earlier steps selected. Current-step/future files, indexes, logs and checkpoints untouched. All replaced bytes individually verified.')
rows=[];start=time.time()
try:
 for q in selected:
  before=q.stat()
  if before.st_flags&stat.UF_COMPRESSED:continue
  digest=sha(q);pending=q.with_name(q.name+'.compressed-pending');assert not pending.exists()
  subprocess.run(['ditto','--hfsCompression',str(q),str(pending)],check=True)
  assert pending.stat().st_size==before.st_size and sha(pending)==digest
  assert (q.stat().st_size,q.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns) and sha(q)==digest
  compressed=pending.stat()
  if compressed.st_blocks<before.st_blocks:
   os.replace(pending,q);assert sha(q)==digest
   rows.append(dict(path=str(q.relative_to(w)),sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=q.stat().st_blocks*512))
  else:pending.unlink()
 result=dict(proof=proof,files=rows,saved_allocated_bytes=sum(v['allocated_before']-v['allocated_after'] for v in rows),seconds=time.time()-start,logical_content_unchanged=True);out.write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='files'},'compressed_files',len(rows))
except BaseException as e:
 out.with_suffix('.failure.json').write_text(json.dumps(dict(error=repr(e),proof=proof,verified_replacements=rows),indent=2)+'\n');raise
