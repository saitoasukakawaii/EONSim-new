"""Collect this campaign's raw numerical receipts without copying binaries or field files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('root', type=Path)
    cli.add_argument('output', type=Path)
    cli.add_argument('production_commit')
    cli.add_argument('--screens', nargs=2, required=True)
    cli.add_argument('--production-runs',nargs=2,required=True)
    cli.add_argument('--release',required=True,type=Path)
    a = cli.parse_args()
    root = a.root.resolve()
    src = Path(__file__).resolve().parents[4]
    out = a.output
    out.mkdir(exist_ok=True, parents=True)
    index = {}

    def identify(p):
        key = str(p).replace(str(Path.home())+'/', '$HOME/', 1)
        index[key] = dict(bytes=p.stat().st_size, sha256=digest(p))
        return key

    def read(p):
        identify(p)
        return json.loads(p.read_text())

    def git(*args):
        return subprocess.check_output(['git',*args], cwd=src, text=True).strip()

    compiled = a.release.resolve()
    build = compiled/'build/release'
    verified = {}
    for line in git('ls-tree','-r',a.production_commit,'--','src','include').splitlines():
        fields, name = line.split('\t',1)
        p = compiled/name
        if git('hash-object',str(p)) != fields.split()[-1]:
            raise ValueError('Release source differs from commit: '+name)
        verified[name] = fields.split()[-1]
    exe = build/'eonsim'
    environment = dict(production_commit=a.production_commit,production_tree=git('rev-parse',a.production_commit+'^{tree}'),
                       collector_commit=git('rev-parse','HEAD'),source_blobs=verified,binary=identify(exe),
                       binary_sha256=digest(exe),libraries=subprocess.check_output(['ldd',str(exe)],text=True),
                       lscpu=subprocess.check_output(['lscpu'],text=True),slurm_node=subprocess.check_output(
                           ['scontrol','show','node'],text=True),cache=identify(build/'CMakeCache.txt'))
    (out/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
    report = {}
    for name in ('B-refine','B-polish','B-block','B-layout','C-layout','B-returned'):
        report[name] = read(root/(name+'.json'))
    for p in root.glob('*.petsc'):
        identify(p)
    for p in root.glob('*.log'):
        identify(p)
    for name in [*a.production_runs,'native-B850',*a.screens]:
        folder = root/name
        for file in folder.rglob('*'):
            if file.is_file():
                identify(file)
        if (folder/'run.json').exists():
            row = read(folder/'run.json')
            if digest(folder/'solve.log') != row['log_sha256']:
                raise ValueError('Log digest mismatch '+name)
            log = (folder/'solve.log').read_text(errors='replace')
            row['linear_refinement'] = [line for line in log.splitlines() if line.startswith('lu_refinement ')]
            row['accepted_steps'] = [int(x) for x in re.findall(r'^fsi_step=(\d+)',log,re.M)]
            if name == 'native-B850':
                histories = (folder/'32-procs/histor.dat').read_text(errors='replace')
                row['native_first_and_last'] = {eq:[lines[0],lines[-1]] for eq in ('FS','MS')
                    for lines in [[s.strip() for s in histories.splitlines() if s.strip().startswith(eq+' ')]] if lines}
                row['accepted_steps'] = None
            report[name] = row
        else:
            report[name] = read(folder/'summary.json')
    for name in ('A4-lu','B32-lu'):
        identify(root/name/'solve.log')
    (out/'tube-validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (out/'tube-log-index.json').write_text(json.dumps(index,indent=2)+'\n')


if __name__ == '__main__':
    main()
