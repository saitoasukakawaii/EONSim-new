"""Prepare a new snapshot commit without transferring intermediate generated blobs."""
from pathlib import Path
import subprocess,json,os,tempfile,hashlib
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109'
def git(*args,input=None,env=None):return subprocess.check_output(['git',*args],cwd=root,input=input,env=env)
receipt=json.loads((b/'elastic-s24-l1-n800-tautime-n400/dense-recovery/receipt.json').read_text());assert receipt['exit_code']==0 and receipt['accepted_last']==25600
assert json.loads((b/'alpha2-n800-budget.json').read_text())['eligible']
assert not git('status','--porcelain').strip(),'Commit local evidence first'
base='92fef88ec6c7dad48cfe8a25ecdb79db48f9a8cc';head=git('rev-parse','HEAD').decode().strip();branch='codex/fsi-progress-snapshot-20261110';ref='refs/heads/'+branch
assert subprocess.run(['git','show-ref','--verify','--quiet',ref],cwd=root).returncode==1
changed={s.decode() for s in git('diff','--name-only','-z',base,head).split(b'\0') if s}
def tree(ref):
 result={}
 for row in git('ls-tree','-rlz',ref).split(b'\0'):
  if not row:continue
  meta,path=row.split(b'\t',1);mode,kind,oid,size=meta.decode().split()
  if kind=='blob':result[path.decode()]=(mode,oid,int(size))
 return result
current=tree(head);baseline=tree(base);omit=[]
for path in sorted(changed&current.keys()):
 mode,oid,size=current[path]
 if size>1024**2 or path.endswith(('.vtu','.h5','.bin','.tar.zst','.tar.gz','.tar.xz')):
  assert path.startswith('docs/research/data/'),('Unexpected non-evidence large file',path)
  omit.append(dict(path=path,bytes=size,git_blob=oid,sha256=hashlib.sha256(git('show',head+':'+path)).hexdigest()))
fd,index=tempfile.mkstemp(prefix='eonsim-push-index-');os.close(fd);os.unlink(index);env=dict(os.environ,GIT_INDEX_FILE=index)
try:
 git('read-tree',head,env=env)
 for row in omit:
  path=row['path']
  if path in baseline:
   mode,oid,_=baseline[path];git('update-index','--add','--cacheinfo',mode,oid,path,env=env)
  else:git('update-index','--force-remove','--',path,env=env)
 metadata=dict(source_local_commit=head,parent_snapshot=base,omitted_generated_files=omit,scope='Code, documents and small verification evidence snapshot. No new raw VTU/HDF/checkpoint/archive payloads or blobs over1MiB. Local history and full computed data retained; omitted-file references in historical records resolve only locally. Existing parent history is already remote, unchanged. Numerical failures remain failures; this is a progress snapshot, not qualification.')
 data=(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode();oid=git('hash-object','-w','--stdin',input=data).decode().strip();git('update-index','--add','--cacheinfo','100644',oid,'docs/research/PUSH_SNAPSHOT_20261110.json',env=env)
 treesha=git('write-tree',env=env).decode().strip();message=b'Snapshot FSI recomputation progress after tau completion without large generated files\n';commit=git('commit-tree',treesha,'-p',base,input=message).decode().strip()
 objects=git('rev-list','--objects',commit,'^'+base);check=git('cat-file','--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)',input=objects)
 blobs=[]
 for line in check.decode().splitlines():
  parts=line.split(' ',3)
  if parts[0]=='blob':
   assert int(parts[2])<=1024**2,line;blobs.append(dict(oid=parts[1],bytes=int(parts[2]),path=parts[3] if len(parts)>3 else ''))
 git('update-ref',ref,commit,'0'*40)
 report=dict(branch=branch,commit=commit,parent=base,source=head,omitted=len(omit),new_blobs=len(blobs),new_blob_bytes=sum(r['bytes'] for r in blobs),max_blob_bytes=max(r['bytes'] for r in blobs),push_executed=False)
 (b/'lightweight-push-snapshot.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
 if Path(index).exists():Path(index).unlink()
