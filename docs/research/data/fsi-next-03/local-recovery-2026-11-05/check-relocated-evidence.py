import hashlib
import json
from pathlib import Path
import sys
import tarfile
import subprocess

root=Path.cwd();run=root/'build/resume-20261105'
sys.path.insert(0,str(root/'scripts'))
from analyze_fsi_error_budget import attached_estimate,dense_cycles,audit_cycle
from analyze_fsi_space import cycle_distance,cycle_paths,phase_paths
from fsi_field_cycles import series
from study_fsi_transient_tail import tail_estimate
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
    actual={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if actual!=set(index['files']):raise RuntimeError('Restored inventory differs: '+label)
    for name,expected in index['files'].items():
        data=(destination/name).read_bytes()
        if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
            raise RuntimeError('Restored bytes do not match archive manifest: '+name)
    records.append(dict(archive=archive.name,files_verified=len(index['files'])))
    return destination

comparisons={};audits={};tail_checks={}
for n in (2,4,8):
    fields={}
    for dt in ('001','0005'):
        label=f'fixed-n{n}-dt{dt}'
        if not all((run/(prefix+label+'.tar.gz')).exists() for prefix in ('','tail-','sampling-')):continue
        source=restore(label);tail=restore('tail-'+label);sample=restore('sampling-'+label)
        attached_estimate(tail/'transient-result.json',source,'transient')
        saved=json.loads((source/'periodic-result.json').read_text())
        result=json.loads((tail/'transient-result.json').read_text())
        cycle=saved['metrics'][-1]['cycle'];steps=round(.1/saved['config']['fsi']['dt'])
        previous={solid:cycle_paths(source,cycle,solid) for solid in (False,True)}
        changes=[]
        for i,block in enumerate(result['blocks'],1):
            end=block['end_cycle'];start=end-result['definition']['block_cycles']
            current={solid:phase_paths(series(tail/(f'block{i}_restart{start*steps}'+('_solid' if solid else '')+'.pvd')),end) for solid in (False,True)}
            delta=cycle_distance(previous,current);changes.append(delta);previous=current
        for expected,actual in zip(result['block_changes'],changes):
            if expected.keys()!=actual.keys() or any(abs(actual[k]-expected[k])>1e-12*max(1.,abs(expected[k])) for k in expected):
                raise RuntimeError('Restored transient fields do not reproduce the estimate')
        recomputed=tail_estimate(changes)
        for field,values in recomputed.items():
            if abs(values['remaining_at_source']-result['estimate'][field]['remaining_at_source'])>1e-12:
                raise RuntimeError('Restored tail estimate differs')
        tail_checks[label]=dict(blocks_recomputed=len(changes),
                               maximum_absolute_difference=max(abs(actual[k]-expected[k])
                               for expected,actual in zip(result['block_changes'],changes) for k in expected),
                               estimates_match=True)
        fields[dt]=dense_cycles(sample/'sampling-result.json',source)
        audits[label]=audit_cycle(source)
    if len(fields)==2:comparisons[str(n)]=cycle_distance(fields['001'],fields['0005'])
full_budget=None
if len(records)==18 and (run/'fixed-budget.json').is_file():
    command=[sys.executable,str(root/'scripts/analyze_fsi_error_budget.py'),
             '--policy','fixed','--output',str(run/'relocated-budget.json')]
    for name,suffix,kind,receipt in [
        ('space-cases','001','',None),('time-cases','0005','',None),
        ('transient-results','001','tail-','transient-result.json'),
        ('sampling-results','001','sampling-','sampling-result.json'),
        ('time-transient-results','0005','tail-','transient-result.json'),
        ('time-sampling-results','0005','sampling-','sampling-result.json')]:
        paths=[target/(kind+f'fixed-n{n}-dt{suffix}') for n in (2,4,8)]
        command+=['--'+name,*[str(p/receipt if receipt else p) for p in paths]]
    with (run/'relocated-budget.log').open('w') as stream:
        subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
    original=json.loads((run/'fixed-budget.json').read_text())
    restored=json.loads((run/'relocated-budget.json').read_text())
    keys=('budget','estimates','observed_spatial_orders','difference_2_4','difference_4_8',
          'temporal_by_mesh','transient_by_mesh','time_transient_by_mesh','sampling_changes')
    if any(original[key]!=restored[key] for key in keys):
        raise RuntimeError('Complete relocated numerical budget differs')
    full_budget=dict(passed=restored['budget']['passed'],numerical_results_exactly_equal=True,
                     command=command,compared_keys=keys)
result=dict(restored_at=str(target),archives=records,temporal=comparisons,audits=audits,
            tail_recomputation=tail_checks,complete_budget=full_budget,
            receipt_paths_rewritten=False)
(run/'relocation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(archives_verified=len(records),files_verified=sum(r['files_verified'] for r in records),
                     temporal=comparisons,receipt_paths_rewritten=False)),flush=True)
