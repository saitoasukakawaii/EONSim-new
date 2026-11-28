"""Run a cold-start LU correction or one evidence-selected native B20 configuration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

source = Path(__file__).resolve().parents[4]
data = source / 'docs/research/data'
sys.path.insert(0, str(data/'fsi-scalable-02'))
from paired_tube import digest, run, save


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=['A4', 'B32', 'native'])
    cli.add_argument('binary', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    ws = Path.home()/'workspace'
    past = ws/'fsi-scalable-03-runs'
    archive = ws/'fsi-scalable-02-runs/B20'
    archive_receipt = json.loads((archive/'summary.json').read_text())
    ranks = 4 if args.mode == 'A4' else 32
    if not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0)) != ranks:
        cli.error('requires one physical core per rank in Slurm')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binary = args.binary.resolve(strict=True)
    info = dict(mode=args.mode, job=os.environ['SLURM_JOB_ID'], affinity=sorted(os.sched_getaffinity(0)),
                binary_sha256=digest(binary), source=subprocess.check_output(
                    ['git','rev-parse','HEAD'],cwd=source,text=True).strip(), inputs={})
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    cmd = ['/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpiexec', '--map-by','core',
           '--bind-to','core','-n',str(ranks),str(binary)]
    if args.mode == 'native':
        if digest(binary) != archive_receipt['binaries']['svfsi']:
            raise ValueError('Native executable differs from frozen baseline')
        for name, sha in archive_receipt['inputs'].items():
            if name.startswith('svfsi/'):
                inp = archive/'prepared'/name
                if digest(inp) != sha:
                    raise ValueError(f'Archived input changed: {name}')
                shutil.copyfile(inp, out/inp.name)
        deck = out/'svFSI.inp'
        old = deck.read_text()
        marker = 'Krylov space dimension: 450'
        if old.count(marker) != 1:
            raise ValueError('Expected one FS GMRES dimension')
        deck.write_text(old.replace(marker,'Krylov space dimension: 850'))
        cmd += ['svFSI.inp']
    else:
        base = past/('A4-432/asm' if ranks == 4 else 'B-system/lu-refined')
        part = base.parent/'partition'
        for name in ('case.json','fluid.msh','solid.msh'):
            shutil.copyfile(base/name,out/name)
        info['partition'] = {p.name:digest(p) for p in sorted(part.glob('*')) if p.is_file()}
        cmd += ['-case','case.json','-partition',str(part),'-ksp_type','preonly','-pc_type','lu',
                '-pc_factor_mat_solver_type','superlu_dist','-ksp_rtol','1e-10','-ksp_atol','1e-23',
                '-linear_lu_refinement_steps','5','-linear_report','-solver_report','-options_view']
    info['inputs'] = {p.name:digest(p) for p in out.iterdir()}
    save(out/'probe.json',info)
    run(out,cmd,info,780 if args.mode == 'native' else 300,140*2**30)


if __name__ == '__main__':
    main()
