"""Stream completed evidence from either storage root into verified small archives."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile
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

def capture(name,paths,copies):
    out=root/'docs/research/data'/name;out.mkdir()
    entries={};skipped={};archives=[];groups=[];chunk=[];total=0
    for path in sorted(set(paths)):
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
        target=out/f'part{number:03d}.tar.xz'
        with tarfile.open(target,'x:xz',preset=3) as archive:
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
        source_checkpoint=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        scope='Immutable completed evidence; run-specific source hashes and original failures are preserved. No physical qualification implied.'),indent=2)+'\n')
    print(json.dumps(dict(evidence=str(out),verified_files=len(entries),skipped_binaries=len(skipped))),flush=True)

def tree(name):return list((work/name).rglob('*'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--part',choices=('time400','vector','alpha1','preflight'),required=True)
    a=p.parse_args();os.sched_setaffinity(0,{9})
    if a.part=='time400':
        status=[completed('elastic-n400-current.json'),completed('elastic-time400-fields-current.json')]
        capture('pressure-tube-n400-2026-11-08',tree('elastic-s12-l0-n400-ramp16-c32')+tree('elastic-time400-fields-054b64a')+status,
            [work/'elastic-time400-fields-054b64a/summary.json',work/'elastic-s12-l0-n400-ramp16-c32/comparison.json'])
    elif a.part=='vector':
        assert json.loads((work/'schur-vector-probe-fine-054b64a/report.json').read_text()).get('complete')
        assert json.loads((work/'gamg-probe-fine-6093f01/report.json').read_text()).get('complete')
        status=[completed('schur-vector-validation-retry3-current.json'),work/'schur-vector-validation-current.json',
            work/'schur-vector-validation-retry-current.json',work/'alpha1-option-window-current.json',work/'mpi-yield-option-054b64a.json']
        names=['schur-vector-validation-054b64a','schur-vector-validation-054b64a-attempt2',
            'schur-vector-validation-054b64a-attempt3','schur-vector-probe-fine-054b64a','gamg-probe-fine-6093f01']
        capture('womersley-vector-metadata-2026-11-08',sum((tree(n) for n in names),[])+status,
            [work/'schur-vector-probe-fine-054b64a/report.json',work/'schur-vector-validation-054b64a-attempt3/combined-release-evidence.json'])
    elif a.part=='preflight':
        capture('pressure-s24-preflight-2026-11-08',tree('elastic-s24-l1-n400-probe-6093f01')+
            [completed('elastic-geometry-probe-current.json')],[work/'elastic-s24-l1-n400-probe-6093f01/summary.json'])
    else:
        parent=work/'womersley-alpha1-0b9e980'
        files=list((parent/'source').rglob('*'))+[parent/'original-controller.py',parent/'provenance.json',parent/'affinity-preflight.json',parent/'mpiexec-cpus10-17']
        copies=[]
        for n,step in [('womersley-a1-s48-l1-n100',500),('womersley-a1-s48-l0-n200',1000)]:
            assert json.loads((work/n/'receipt.json').read_text())['step']==step
            analysis=parent/(n+'-analysis.json');assert json.loads(analysis.read_text())['last_cycle']==5
            files+=tree(n)+[analysis,parent/(n+'-command.json'),parent/(n+'.log'),parent/(n+'-analysis-command.json'),parent/(n+'-analysis.log')]
            copies.append(analysis)
        capture('womersley-alpha1-followup-2026-11-08',files,copies)

if __name__=='__main__':main()
