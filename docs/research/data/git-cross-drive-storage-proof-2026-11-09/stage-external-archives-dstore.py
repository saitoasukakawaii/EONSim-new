"""Stage sealed ordinary archive blobs on the verified D object store in bounded batches."""
import argparse,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('name');p.add_argument('--first',type=int);p.add_argument('--last',type=int);p.add_argument('--finalize',action='store_true')
a=p.parse_args();assert re.fullmatch(r'[a-z0-9-]+',a.name)
root=Path(__file__).resolve().parents[2];metadata=root/'docs/research/data'/a.name
record=json.loads((metadata/'archives.json').read_text(encoding='utf-8'))
source_store=Path('D:/EONSim-prod48-20261107/repository-archives')/a.name
storage_record=root/'docs/research/data/git-external-object-storage-2026-11-09/storage.json'
storage=json.loads(storage_record.read_text(encoding='utf-8'))
assert storage['adopted'] and not storage['existing_objects_moved'] and not storage['git_config_changed']
object_store=Path(storage['object_store_windows']);junction=root/storage['junction_relative']
assert junction.resolve()==object_store.resolve()
assert (root/'.git/objects/info/alternates').read_bytes()==storage['alternates_bytes'].encode()
assert record['local_archive_store']=='/mnt/d/EONSim-prod48-20261107/repository-archives/'+a.name
assert not any(k in os.environ for k in ('GIT_DIR','GIT_COMMON_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'))
assert not (root/'.git/index.lock').exists()
assert not (metadata/'index-staging.json').exists(), 'Already finalized'
reserve=4*1024**3;margin=64*1024**2;batch_limit=1500000000
assert shutil.disk_usage(root).free>reserve+margin
base=['git','-c','safe.directory='+root.as_posix(),'-c','gc.auto=0','-c','maintenance.auto=false','-C',str(root)]
commands=[]
def git(*args,external=False):
 env=os.environ.copy()
 if external:env['GIT_OBJECT_DIRECTORY']=str(junction)
 proc=subprocess.run(base+list(args),env=env,capture_output=True)
 commands.append(dict(argv=base+list(args),external_object_write=external,returncode=proc.returncode))
 assert proc.returncode==0,proc.stderr.decode('utf-8',errors='replace')
 return proc.stdout
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
head=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip()
assert branch=='codex/fsi-production-48h-20261107'
items=record['archives'];assert items and [x['file'] for x in items]==[f'part{i:03d}.tar.xz' for i in range(1,len(items)+1)]
assert all(0<x['bytes']<100000000 for x in items)
if a.finalize:
 assert a.first is None and a.last is None
 selected=[];receipt=metadata/'index-staging.json'
else:
 first=a.first or 1;last=a.last or len(items);assert 1<=first<=last<=len(items)
 selected=items[first-1:last];receipt=metadata/f'index-batch-{first:03d}-{last:03d}.json';assert not receipt.exists()
 staged=git('diff','--cached','--name-only','-z').split(b'\0');staged_bytes=0
 for name in filter(None,staged):
  line=git('ls-files','--stage','--',name.decode('utf-8')).decode().strip()
  if line:staged_bytes+=int(git('cat-file','-s',line.split()[1]))
 total=sum(x['bytes'] for x in selected)
 assert total+staged_bytes<=batch_limit, 'Split the batch and commit before the next one'
 assert shutil.disk_usage(object_store).free>reserve+total+margin
 # Validate every member before any index write, including the whole-batch space budget.
 for item in selected:
  src=source_store/item['file'];relative=(metadata/item['file']).relative_to(root).as_posix()
  assert not (root/relative).exists() and not git('ls-files','--',relative).strip()
  assert src.stat().st_size==item['bytes'] and sha(src)==item['sha256']
 results=[]
 for item in selected:
  src=source_store/item['file'];relative=(metadata/item['file']).relative_to(root).as_posix();before=src.stat()
  assert shutil.disk_usage(root).free>reserve+margin
  assert shutil.disk_usage(object_store).free>reserve+item['bytes']+margin
  oid=git('hash-object','-w','--no-filters',str(src),external=True).decode().strip();assert re.fullmatch('[0-9a-f]{40}',oid)
  assert (object_store/oid[:2]/oid[2:]).is_file()
  git('update-index','--add','--cacheinfo','100644,'+oid+','+relative)
  git('update-index','--skip-worktree','--',relative)
  raw=git('show',':'+relative);assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'];del raw
  assert git('ls-files','-v','--',relative).decode().strip()=='S '+relative
  after=src.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  results.append(dict(**item,blob_oid=oid,index_path=relative,indexed_bytes_match_manifest=True,local_source_retained=True,archive_absent_from_sparse_worktree=True,index_flags='S '+relative))
 dump(receipt,dict(passed=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),source_checkpoint=head,branch=branch,
  archives_json_sha256=sha(metadata/'archives.json'),storage_record_sha256=sha(storage_record),archives=results,
  whole_archive_complete=False,scope='Completed selected batch only; final receipt is required for the entire archive.',commands=commands))

if a.finalize:
 results=[]
 for item in items:
  src=source_store/item['file'];relative=(metadata/item['file']).relative_to(root).as_posix()
  line=git('ls-files','--stage','--',relative).decode().strip();assert line
  mode,oid,stagepath=line.split(maxsplit=2);assert mode=='100644' and stagepath=='0\t'+relative
  assert git('ls-files','-v','--',relative).decode().strip()=='S '+relative
  assert not (root/relative).exists() and src.stat().st_size==item['bytes'] and sha(src)==item['sha256']
  raw=git('show',':'+relative);assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'];del raw
  results.append(dict(**item,blob_oid=oid,index_path=relative,index_flags='S '+relative,indexed_bytes_match_manifest=True,local_source_retained=True,archive_absent_from_sparse_worktree=True))
 dump(receipt,dict(passed=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),source_checkpoint=head,branch=branch,
  archives_json_sha256=sha(metadata/'archives.json'),storage_record_sha256=sha(storage_record),archives=results,
  scope='Every archive is a complete regular100644 Git blob. Default Git readback matches every manifest SHA. D source archives retained; no pointer substitute, ref update, upload, move or deletion.',commands=commands))
shutil.copy2(__file__,metadata/Path(__file__).name)
assert git('rev-parse','HEAD').decode().strip()==head
print(json.dumps(dict(passed=True,receipt=str(receipt),parts=len(results),bytes=sum(x['bytes'] for x in results),finalized=a.finalize)))
