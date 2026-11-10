"""Byte-preserving compression strictly before a complete accepted-step log record, written after output."""
from pathlib import Path
import argparse,json,hashlib,subprocess,os,stat,time,re
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--through',type=int,required=True);a=p.parse_args();w=a.work.resolve();out=w.parent/(w.name+f'-logged-frames-through{a.through}-compression.json');assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
marker,generation=(w/'checkpoint/current').read_text().split();manifest=w/'checkpoint'/generation/'manifest';tokens=manifest.read_text().split();assert marker==tokens[0]=='EONSim_checkpoint_v4';checkpoint=int(tokens[2])
logpath=w/'dense-019/solve.log';raw=logpath.read_bytes();complete=raw[:raw.rfind(b'\n')+1];text=complete.decode();accepted=list(map(int,re.findall(r'^fsi_step=(\d+) ',text,re.M)))
assert accepted and a.through<accepted[-1];last_logged=accepted[-1]
# Bind output-before-log ordering to the frozen study source as well as current source.
root=Path(__file__).resolve().parents[2];definition=json.loads((w/'definition.json').read_text())
old=subprocess.check_output(['git','show',definition['source_commit']+':src/physics/fsi.cpp'],cwd=root,text=True)
current=(root/'src/physics/fsi.cpp').read_text()
def ordered_block(source):
 end=source.index('        } catch(const StepRejected& error)',source.index('"fsi_step="'))
 start=source.rfind('        if(f.output_interval>0) {',0,end)
 block=source[start:end];assert block.index('write_fsi_fields(comm,path,result);')<block.index('"fsi_step="');return block
assert ordered_block(old)==ordered_block(current)
assert sha(w/'eonsim')==definition['binary_sha256']
cfg=json.loads((w/'definition.json').read_text());n=cfg['steps_per_cycle'];assert cfg['ranks']==1
assert json.loads((w/'early/receipt.json').read_text())['exit_code']==0
pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu$');selected=[];groups={}
for label in ['dense-019']:
 for q in sorted((w/label).glob('*.vtu')):
  m=pattern.fullmatch(q.name)
  if not m or int(m[1])>a.through:continue
  step=int(m[1]);assert step<last_logged and not q.is_symlink();groups.setdefault((label,step),set()).add(m[2] or '');selected.append(q)
assert accepted==list(range(51009,last_logged+1))
assert groups and all(v=={'','_boundary','_solid','_solid_boundary'} for v in groups.values())
assert {s for (label,s) in groups if label=='dense-019'}==set(range(51009,a.through+1))
root=Path(__file__).resolve().parents[2];proof=dict(work=str(w),checkpoint_generation=generation,checkpoint_step=checkpoint,last_logged_step=last_logged,accepted_log_prefix_sha256=hashlib.sha256(complete).hexdigest(),accepted_log_prefix_bytes=len(complete),frozen_source_commit=definition['source_commit'],checkpoint_manifest_sha256=sha(manifest),through=a.through,source_sha256=sha(root/'src/physics/fsi.cpp'),controller_sha256=sha(Path(__file__)),selected_frames=len(groups),selected_files=len(selected),scope='Frozen/current source output-before-accepted-log block matches byte-for-byte. Only steps strictly before complete contiguous dense accepted-log record selected. Four files required; each replacement verifies stable source size/mtime and SHA. Current/future outputs, indexes/logs/checkpoints untouched.')
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
