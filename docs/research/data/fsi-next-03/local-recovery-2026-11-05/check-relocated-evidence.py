import hashlib
import json
from pathlib import Path
import sys
import tarfile

root=Path.cwd();run=root/'build/resume-20261105'
sys.path.insert(0,str(root/'scripts'))
from analyze_fsi_error_budget import attached_estimate,dense_cycles,audit_cycle
from analyze_fsi_space import cycle_distance
target=Path('/home/tfblab633/EONSim-next03-20261105/relocated-evidence')
records=[]

def restore(label):
    archive=run/(label+'.tar.gz')
    index=json.loads(archive.with_suffix('.gz.manifest.json').read_text())
    destination=target/label
    if not destination.exists():
        with tarfile.open(archive) as stream:
            members=stream.getmembers()
            if len(members)!=len(index['files']) or {m.name for m in members}!=set(index['files']):
                raise RuntimeError('Archive inventory mismatch: '+label)
            if any(not m.isfile() for m in members):raise RuntimeError('Unexpected archive entry')
            destination.mkdir(parents=True)
            stream.extractall(destination,filter='data')
    for name,expected in index['files'].items():
        data=(destination/name).read_bytes()
        if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
            raise RuntimeError('Restored bytes do not match archive manifest: '+name)
    records.append(dict(archive=archive.name,files_verified=len(index['files'])))
    return destination

comparisons={};audits={}
for n in (2,4,8):
    fields={}
    for dt in ('001','0005'):
        label=f'fixed-n{n}-dt{dt}'
        if not all((run/(prefix+label+'.tar.gz')).exists() for prefix in ('','tail-','sampling-')):continue
        source=restore(label);tail=restore('tail-'+label);sample=restore('sampling-'+label)
        attached_estimate(tail/'transient-result.json',source,'transient')
        fields[dt]=dense_cycles(sample/'sampling-result.json',source)
        audits[label]=audit_cycle(source)
    if len(fields)==2:comparisons[str(n)]=cycle_distance(fields['001'],fields['0005'])
result=dict(restored_at=str(target),archives=records,temporal= comparisons,audits=audits,
            receipt_paths_rewritten=False)
(run/'relocation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(archives_verified=len(records),files_verified=sum(r['files_verified'] for r in records),
                     temporal=comparisons,receipt_paths_rewritten=False)),flush=True)
