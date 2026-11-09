"""Add append-only D storage for future blobs after the isolated transport proof."""
import hashlib,json,os,shutil,subprocess,time,zlib
from pathlib import Path

root=Path(__file__).resolve().parents[2]
proof=root/'build/prod48-20261107/git-cross-drive-proof-224aad5'
out=root/'docs/research/data/git-external-object-storage-2026-11-09'
store=Path('D:/EONSim-prod48-20261107/repository-git-objects-20261109/objects')
junction=root/'.git/objects/external-evidence-20261109'
alternates=root/'.git/objects/info/alternates'
commands=[]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def call(args,env=None):
 p=subprocess.run(args,env=env,capture_output=True);commands.append(dict(argv=list(map(str,args)),returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace')))
 assert p.returncode==0,commands[-1]
 return p.stdout
def git(where,*args,env=None):return call(['git','-c','safe.directory='+where.as_posix(),'-c','gc.auto=0','-c','maintenance.auto=false','-C',str(where),*args],env)
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
assert not any(k in os.environ for k in ('GIT_DIR','GIT_COMMON_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'))
assert not out.exists() and not store.parent.exists() and not junction.exists() and not alternates.exists()
assert not (root/'.git/index.lock').exists()
assert shutil.disk_usage(root).free>4*1024**3+64*1024**2
assert shutil.disk_usage(store.parents[1]).free>32*1024**3
report=json.loads((proof/'report.json').read_text(encoding='utf-8'))
assert report['passed'] and report['project_unchanged'] and report['windows_and_wsl_default_readback']
assert report['ordinary_blob'] and report['independent_clone_has_no_alternates']
head=git(root,'rev-parse','HEAD').decode().strip()
assert head==report['project_head']=='224aad53d012f8aa4c661b61089eb0b070ce16e9'
assert not git(root,'status','--porcelain').strip()
before={n:sha(root/'.git'/n) for n in ('HEAD','index','config')}
assert before==report['project_before']
fixture=Path(report['fixture']);clone=Path(report['independent_clone'])
assert not (clone/'.git/objects/info/alternates').exists()
for path in (fixture,clone):
 raw=git(path,'show','HEAD:evidence/part001.tar.xz')
 assert len(raw)==report['archive']['bytes'] and hashlib.sha256(raw).hexdigest()==report['archive']['sha256']
 assert git(path,'rev-parse','HEAD').decode().strip()==report['fixture_head']
loose=Path(report['external_store'])/report['blob_oid'][:2]/report['blob_oid'][2:]
decoded=zlib.decompress(loose.read_bytes());header,raw=decoded.split(b'\0',1)
assert header==b'blob '+str(len(raw)).encode() and hashlib.sha1(decoded).hexdigest()==report['blob_oid']
assert hashlib.sha256(raw).hexdigest()==report['archive']['sha256']
review=dict(passed=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),proof_report_sha256=sha(proof/'report.json'),
 commands_sha256=sha(proof/'commands.json'),complete_blob_decoded=True,independent_clone_readback=True,
 project_head=head,project_before=before,decision='add_only_new_append_only_object_store; no existing objects moved')
out.mkdir()
dump(out/'independent-review.json',review)
(store/'info').mkdir(parents=True);(store/'pack').mkdir()
cmd="New-Item -ItemType Junction -Path '"+str(junction).replace("'","''")+"' -Target '"+str(store).replace("'","''")+"' | Select-Object -ExpandProperty FullName"
call(['powershell.exe','-NoProfile','-NonInteractive','-Command',cmd])
assert junction.resolve()==store.resolve()
with alternates.open('xb') as f:f.write(b'./external-evidence-20261109\n')
probe=dict(schema=1,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),source_head=head,
 purpose='Verify a complete ordinary blob stored only in the new D object database',
 archive_sha256=report['archive']['sha256'],isolated_proof_head=report['fixture_head'])
probe_path=out/'storage-probe.json';dump(probe_path,probe)
env=os.environ.copy();env['GIT_OBJECT_DIRECTORY']=str(junction)
oid=git(root,'hash-object','-w','--no-filters',str(probe_path),env=env).decode().strip()
assert (store/oid[:2]/oid[2:]).is_file() and not (root/'.git/objects'/oid[:2]/oid[2:]).exists()
relative=probe_path.relative_to(root).as_posix()
assert not git(root,'ls-files','--',relative).strip()
git(root,'update-index','--add','--cacheinfo','100644,'+oid+','+relative)
assert git(root,'show',':'+relative)==probe_path.read_bytes()
linux='/mnt/c/'+root.as_posix()[3:]
raw=call(['wsl.exe','-d','Ubuntu-24.04','--exec','/usr/bin/git','-c','safe.directory='+linux,'-C',linux,'show',':'+relative])
assert raw==probe_path.read_bytes()
assert {n:sha(root/'.git'/n) for n in ('HEAD','config')}=={n:before[n] for n in ('HEAD','config')}
for name in ('controller.py','report.json','commands.json','windows-fixture-fsck.txt','wsl-fixture-fsck.txt','windows-independent-clone-fsck.txt','wsl-independent-clone-fsck.txt'):
 shutil.copy2(proof/name,out/('isolated-'+name))
shutil.copy2(__file__,out/Path(__file__).name)
for name in ('validate-cross-drive-git-objects-initial-rejected.py','git-cross-drive-preflight-failure.json'):
 shutil.copy2(root/'build/prod48-20261107'/name,out/name)
dump(out/'storage.json',dict(adopted=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),source_head=head,
 object_store_windows=str(store),object_store_wsl='/mnt/d/EONSim-prod48-20261107/repository-git-objects-20261109/objects',
 junction_relative='.git/objects/external-evidence-20261109',alternates_bytes='./external-evidence-20261109\n',
 probe_blob_oid=oid,probe_index_path=relative,probe_sha256=sha(probe_path),project_before=before,
 existing_objects_moved=False,existing_objects_deleted=False,git_config_changed=False,refs_changed=False,uploaded=False,
 scope='Future selected archive blobs may be written to this append-only object store. Standard Git reads through the relative alternate. D originals and existing C objects remain intact. Store remains required by this local checkout; ordinary Git transport copies full objects.'))
dump(out/'adoption-commands.json',commands)
print(json.dumps(dict(adopted=True,probe_blob_oid=oid,default_windows_and_wsl_index_readback=True,head_unchanged=head,metadata=str(out))))
