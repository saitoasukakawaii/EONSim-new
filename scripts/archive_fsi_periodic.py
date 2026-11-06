"""Archive a complete-cycle restart and its accepted history, including partial studies.

All scalar histories and PVD indices are retained; only the last four cycles of
field snapshots are retained. Older PVD references therefore need a replay for
visualization, but checkpoint continuation and the last-cycle audit remain valid.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET
from fsi_cycle_metrics import volume_budget
from fsi_field_cycles import series


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    work=a.work.resolve();receipt=json.loads((work/'periodic-result.json').read_text());definition=json.loads((work/'study-definition.json').read_text())
    last=receipt['metrics'][-1]['cycle'];steps=round(.1/receipt['config']['fsi']['dt']);files=set();rows=[]
    for name in ('periodic-result.json','study-definition.json','fluid.msh','solid.msh'):files.add(work/name)
    for cycle in range(1,last+1):
        label=f'cycle{cycle}';stem=label+(f'_restart{(cycle-1)*steps}' if cycle>1 else '')
        for name in (label+'.json',label+'.log',stem+'.csv',stem+'.pvd',stem+'_solid.pvd'):files.add(work/name)
        with (work/(stem+'.csv')).open() as stream:rows.extend({k:float(v) for k,v in row.items()} for row in csv.DictReader(stream))
        if cycle>=max(1,last-3):
            for suffix in ('','_solid'):
                for _,path in series(work/(stem+suffix+'.pvd')):
                    files.add(path)
                    if path.suffix=='.pvtu':files.update(path.parent/p.attrib['Source'] for p in ET.parse(path).findall('.//Piece'))
    budget=volume_budget(rows)
    if abs(rows[-1]['time']-last*.1)>1e-10:raise ValueError('History does not reach archived checkpoint')
    generation=work/'checkpoint'/receipt['checkpoint_generation']
    manifest=(generation/'manifest').read_text().split()
    if int(manifest[2])!=last*steps or int(manifest[1])!=definition['ranks']:raise ValueError('Checkpoint/receipt mismatch')
    files.update(p for p in generation.rglob('*') if p.is_file())
    previous=None
    if last>1:
        for candidate in sorted((work/'checkpoint').glob('generation_*'),reverse=True):
            path=candidate/'manifest'
            if path.exists() and int(path.read_text().split()[2])==(last-1)*steps:
                previous=candidate.name;files.update(p for p in candidate.rglob('*') if p.is_file());break
        if previous is None:raise ValueError('Preceding complete-cycle checkpoint is missing')
    partition=work/f"part-{definition['ranks']}"
    if not partition.is_dir() or not (partition/'manifest.yaml').is_file():raise ValueError('Original partition is missing')
    files.update(p for p in partition.rglob('*') if p.is_file())
    index=dict(converged=receipt['converged'],last_complete_cycle=last,checkpoint_generation=receipt['checkpoint_generation'],replay_generation=previous,
               field_cycles=list(range(max(1,last-3),last+1)),accepted_rows=len(rows),mass_budget=budget,
               restart_note='Restart from explicit checkpoint generation path; no mutable current pointer is archived',files={})
    a.output.parent.mkdir(parents=True,exist_ok=True);temporary=a.output.with_suffix('.tmp')
    with tarfile.open(temporary,'w:gz') as archive:
        for path in sorted(files):
            relative=path.resolve().relative_to(work);data=path.read_bytes()
            index['files'][str(relative)]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
            archive.add(path,arcname=str(relative),recursive=False)
    temporary.replace(a.output)
    a.output.with_suffix(a.output.suffix+'.manifest.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps(dict(archive=str(a.output),converged=receipt['converged'],last_complete_cycle=last,files=len(files),bytes=a.output.stat().st_size)))


if __name__=='__main__':main()
