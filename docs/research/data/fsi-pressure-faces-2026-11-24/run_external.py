"""Run the archived 0.25 s step as a rebuild control and refine it to 0.125 s."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


def input_text(source, dt):
    lines = (source/'svFSI.inp').read_text().splitlines()
    steps = round(1/dt)
    replacements = {'Number of time steps: 48': f'Number of time steps: {steps}',
                    'Time step size: 0.25': f'Time step size: {dt}',
                    'Increment in saving restart files: 48': f'Increment in saving restart files: {steps}'}
    if any(lines.count(line) != 1 for line in replacements):
        raise ValueError('Unexpected archived input')
    return '\n'.join(replacements.get(line,line) for line in lines)+'\n'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--archive', type=Path, required=True)
    cli.add_argument('--executable', type=Path, required=True)
    cli.add_argument('--work', type=Path, required=True)
    args = cli.parse_args()
    source = args.archive/'svfsi/alpha05-medium-dt025'
    exe = args.executable.resolve()
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    for dt in (.25, .125):
        directory = args.work/str(dt)
        directory.mkdir(parents=True)
        for mesh in (*source.glob('*.vtu'), *source.glob('*.vtp')):
            shutil.copyfile(mesh, directory/mesh.name)
        (directory/'svFSI.inp').write_text(input_text(source,dt))
        (directory/'executable.sha256').write_text(digest+'\n')
        with (directory/'solve.log').open('w') as stream:
            subprocess.run([exe,'svFSI.inp'], cwd=directory, env=env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        print(f'svFSI {dt} s',flush=True)


if __name__ == '__main__':
    main()
