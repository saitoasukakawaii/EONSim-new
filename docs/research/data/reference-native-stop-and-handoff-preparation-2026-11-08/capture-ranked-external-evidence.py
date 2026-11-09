"""Keep completed large archives on D while preserving regular Git-blob contents.

Archive HDF members by checkpoint family and rank, with the original byte/hash
readback. Only metadata/copies are materialized in the sparse C worktree. The
caller must separately stage every external part as a regular Git blob before
committing; this capture helper does not modify Git or claim publication.
"""
import argparse,hashlib,json,os,re,shutil,subprocess,tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
storage=Path('/mnt/d/EONSim-prod48-20261107')
origins={'work':work,'host-d':storage}

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def source_name(path):
    path=path.resolve(strict=True)
    for label,base in origins.items():
        if path.is_relative_to(base):return label+'/'+path.relative_to(base).as_posix()
    raise ValueError('Input outside declared evidence roots: '+str(path))

def completed(name):
    value=json.loads((work/name).read_text())
    assert value['state']=='completed',(name,value)
    return work/name

def member_order(path):
    match=re.fullmatch(r'state_rank(\d+)\.h5',path.name)
    if match:return (0,source_name(path.parent.parent),int(match[1]),path.parent.name,path.name)
    return (1,source_name(path),0,'','')


def capture(name,paths,copies):
    assert re.fullmatch(r'[a-z0-9][a-z0-9-]*',name)
    out=root/'docs/research/data'/name
    archive_store=storage/'repository-archives'/name
    assert not out.exists() and not archive_store.exists()
    assert shutil.disk_usage(root).free>4*1024**3 and shutil.disk_usage(storage).free>32*1024**3
    out.mkdir();archive_store.mkdir(parents=True)
    entries={};skipped={};archives=[];groups=[];chunk=[];total=0
    for path in sorted(set(paths),key=member_order):
        if not path.is_file() or '__pycache__' in path.parts:continue
        if path.is_symlink():raise ValueError('Unexpected symlink: '+str(path))
        relative=source_name(path);size=path.stat().st_size
        with path.open('rb') as f:binary=f.read(4)==b'\x7fELF'
        if binary:
            skipped[relative]=dict(bytes=size,sha256=digest(path),reason='Executable identified by ELF magic; exact hash retained, source/build evidence archived')
            continue
        if size>64*1024**2:raise ValueError('One source exceeds the bounded archive size: '+str(path))
        if chunk and total+size>64*1024**2:groups.append(chunk);chunk=[];total=0
        chunk.append(path);total+=size
    if chunk:groups.append(chunk)
    for number,group in enumerate(groups,1):
        target=archive_store/f'part{number:03d}.tar.xz'
        # svFSI's last-state file can be a hard link. Store each declared
        # pathname as regular bytes so per-member verification stays exact.
        with tarfile.open(target,'x:xz',preset=3,dereference=True) as archive:
            for path in group:
                relative=source_name(path);before=path.stat()
                entries[relative]=dict(bytes=before.st_size,sha256=digest(path))
                archive.add(path,arcname=relative,recursive=False)
                after=path.stat()
                assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Input changed during capture'
        verified=set()
        with tarfile.open(target,'r:xz') as archive:
            for member in archive:
                assert member.isfile() and member.name not in verified
                stream=archive.extractfile(member)
                assert dict(bytes=member.size,sha256=hashlib.file_digest(stream,'sha256').hexdigest())==entries[member.name]
                verified.add(member.name)
        assert verified=={source_name(path) for path in group}
        archives.append(dict(file=target.name,bytes=target.stat().st_size,sha256=digest(target),verified_files=len(verified)))
        print(json.dumps(archives[-1]),flush=True)
    copied={}
    for path in [*copies,Path(__file__)]:
        assert path.name not in copied,'Copy name collision'
        shutil.copy2(path,out/path.name);assert digest(path)==digest(out/path.name)
        copied[path.name]=dict(source=str(path),sha256=digest(path))
    (out/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n')
    (out/'archives.json').write_text(json.dumps(dict(archives=archives,verified_files=len(entries),
        source_roots={k:str(v) for k,v in origins.items()},skipped_binaries=skipped,copied_files=copied,
        local_archive_store=str(archive_store),archive_member_order='HDF files grouped by checkpoint family, rank, generation; other files by source path',
        git_storage_contract='Every listed archive must be staged as a regular100644 Git blob at this metadata directory before committing. Local archive bytes stay on D; this sparse worktree need not materialize duplicate archive files.',
        source_checkpoint=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        scope='Immutable completed evidence; run-specific source hashes and original failures are preserved. No physical qualification implied.'),indent=2)+'\n')
    print(json.dumps(dict(evidence=str(out),verified_files=len(entries),skipped_binaries=len(skipped))),flush=True)

def tree(name):return list((work/name).rglob('*'))
