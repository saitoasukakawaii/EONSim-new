"""Run the first second of the two-ended Lamé tube on the pinned 48-sector mesh."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

DT = (.5, .25, .125)
# Median of the 1512 initial cell coefficients with the default BE startup at dt=.25.
FIXED_TAU = .007716762652107021
INPUT_SHA256 = {
    'case.json': '9095e0a94682c746a2e23a84741af875018e64c7bbe9178d3e717514e8980c03',
    'fluid.msh': '6a2eddd7ee53d6cd43d6c0706d21a3295b99d79431ec037e21a5d1149d8b8f7f',
    'solid.msh': 'ca61d566c848adb2bc41b9bbbebf5dff3454818008b921960d135e05a1a27016',
}


def cases():
    for load in ('step', 'ramp'):
        for tau in ('default', 'fixed'):
            for dt in DT:
                yield load, tau, dt, f'{load}-{tau}-{dt}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Extracted PR 42 raw.tar.xz')
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    source = args.archive/'coupled/sv05-s48'
    for name, digest in INPUT_SHA256.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Unexpected reference input {name}')
    exe = args.executable.resolve()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    for load, tau, dt, name in cases():
        directory = args.work/name
        directory.mkdir(parents=True)
        for mesh in ('fluid.msh', 'solid.msh'):
            shutil.copyfile(source/mesh, directory/mesh)
        cfg = json.loads((source/'case.json').read_text())
        cfg['fsi'].update(dt=dt, steps=round(1/dt), pressure_face_history=True)
        if load == 'ramp':
            cfg['fsi']['pressure_time'] = dict(amplitude=0., period=1., ramp_time=1.)
        if tau == 'fixed':
            cfg['fsi']['stabilization_tau'] = FIXED_TAU
        (directory/'case.json').write_text(json.dumps(cfg, indent=2)+'\n')
        with (directory/'solve.log').open('w') as log:
            subprocess.run([exe, '-case', 'case.json'], cwd=directory, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print(name, flush=True)


if __name__ == '__main__':
    main()
