"""Collect completed C first-system and native MS probes without copying fields or AIJ files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tube_protocol import records


def identify(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):
            h.update(chunk)
    return dict(bytes=path.stat().st_size,sha256=h.hexdigest())


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('root',type=Path)
    cli.add_argument('output',type=Path)
    args = cli.parse_args()
    root = args.root.resolve()
    index, results, jobs = {}, {}, set()
    def register(path):
        name = '$HOME/'+path.relative_to(Path.home()).as_posix()
        index[name] = identify(path)
        return name
    for path in sorted([*root.glob('C-*/first.json'), *root.glob('C-*/replay.json'),
                        *root.glob('native-*/native-mesh.json'), *root.glob('C-*-snapshot.json'),
                        root/'native-mesh-438.json']):
        row = json.loads(path.read_text())
        name = register(path)
        results[name] = row
        if path.parent == root:
            continue
        job = row['job']
        jobs.add(str(job))
        for log in root.glob('*-'+str(job)+'.log'):
            register(log)
        for filename in ('run.json','solve.log','iterate.petsc','operator.petsc','rhs.petsc',
                         '32-procs/histor.dat','32-procs/RCR.dat','FSILS_NS.log'):
            f = path.parent/filename
            if f.exists():
                item = register(f)
                if filename=='solve.log' and row.get('log_sha256')!=index[item]['sha256']:
                    raise ValueError(f'Log changed {f}')
        if path.name=='first.json' or path.name=='replay.json':
            lines=(path.parent/'solve.log').read_text(errors='replace').splitlines()
            row['hierarchy_setup'] = records(lines,'pc_monolithic_mg ')
            row['transfers'] = records(lines,'pc_monolithic_mg_level ')
    scheduler = subprocess.check_output(['sacct','-X','-n','-P','-j',','.join(sorted(jobs)),
        '-o','JobID,State,ElapsedRaw,AllocCPUS,ReqCPUS'],text=True).strip().splitlines() if jobs else []
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    for file,value in [('c-native-receipts.json',dict(runs=results,slurm=scheduler,
                         slurm_columns=['JobID','State','ElapsedRaw','AllocCPUS','ReqCPUS'])),
                       ('c-native-log-index.json',index)]:
        text=json.dumps(value,allow_nan=False,indent=2).replace(str(Path.home())+'/', '$HOME/')
        (out/file).write_text(text+'\n')


if __name__=='__main__':
    main()
