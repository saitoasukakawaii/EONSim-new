"""Capture completed checks and first coupled results without altering raw files."""
import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def capture(name,groups,copies):
    out=root/'docs/research/data'/name;out.mkdir()
    entries={};archives=[]
    for label,files in groups:
        target=out/(label+'.tar.xz')
        with tarfile.open(target,'x:xz',preset=3) as archive:
            for path in sorted(set(files)):
                if not path.is_file():continue
                if path.name=='eonsim':continue
                relative=path.relative_to(work).as_posix()
                entries[relative]=dict(bytes=path.stat().st_size,sha256=sha(path))
                archive.add(path,arcname=relative,recursive=False)
        with tarfile.open(target) as archive:
            for member in archive.getmembers():
                data=archive.extractfile(member).read()
                assert entries[member.name]==dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        archives.append(dict(file=target.name,bytes=target.stat().st_size,sha256=sha(target)))
        print(json.dumps(archives[-1]),flush=True)
    extra={}
    for path in copies:
        shutil.copy2(path,out/path.name)
        assert sha(path)==sha(out/path.name)
        extra[path.name]=sha(path)
    shutil.copy2(__file__,out/'original-capture.py')
    (out/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n')
    (out/'archives.json').write_text(json.dumps(dict(archives=archives,verified_files=len(entries),
        copied_files=extra,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()),indent=2)+'\n')
    print(json.dumps(dict(evidence=str(out),verified_files=len(entries))),flush=True)
capture('pressure-tube-first-2026-11-08',[
    ('acceptance',list((work/'acceptance-2189a8c').rglob('*'))+[work/'next-acceptance-current.json']),
    ('stage-uniform',list((work/'reference/uniform-pressure-s12-stage').rglob('*'))),
    ('eonsim-six-cycles',list((work/'elastic-s12-l0-region20').rglob('*'))),
    ('svfsi-six-cycles',list((work/'reference/elastic-s12-l0-stage').rglob('*'))),
    ('fixed-reader',list((work/'elastic-reaudit-float32-865b101').rglob('*')))],
    [work/'elastic-reaudit-float32-865b101/summary.json',root/'scripts/audit_pressure_tube.py',
     root/'tests/test_pressure_tube_audit.py'])
names=['option-probe-coarse-865b101','option-probe-fine-865b101',
       'option-probe-coarse-lag2-865b101','option-probe-fine-lag2-865b101']
for name in names:assert json.loads((work/name/'report.json').read_text()).get('complete')
capture('womersley-options-2026-11-08',[(name,list((work/name).rglob('*'))) for name in names]+[
    ('handoff',[work/'scheduled-handoff-200.json'])],
    [root/'scripts/study_womersley.py',root/'build/prod48-20261107/fork-womersley-execution.py',
     root/'build/prod48-20261107/continue-womersley-after-probes.py'])
