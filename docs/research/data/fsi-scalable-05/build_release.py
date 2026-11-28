"""Incrementally rebuild the verified #72 Release archive on the benchmark host."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob(path):
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def output(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def main():
    source, build, old = [Path(arg).resolve(strict=True) for arg in sys.argv[1:4]]
    expected = sys.argv[4]
    os.chdir(source)
    commit = output(['git', 'rev-parse', 'HEAD'])
    if commit != expected:
        raise ValueError(f'Expected {expected}, found {commit}')
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'include', 'tests',
                    'CMakeLists.txt', 'cmake'], check=True)
    history = json.loads((source/'docs/research/data/fsi-scalable-04/environment.json').read_text())
    archive = old/'libeonsim_core.a'
    if (sha(old/'eonsim') != history['binary_sha256'] or
            sha(archive) != '1091a0a9a2be082531a4de7257a8cdb7b383f8e93320ba2d25e0ee64bd118177'):
        raise ValueError('Archived production build changed')
    target_list = (source/'CMakeLists.txt').read_text().split('add_library(eonsim_core\n', 1)[1].split(')', 1)[0].split()
    members = [Path(f).name+'.o' for f in target_list]
    if output(['ar', 't', archive]).splitlines() != members or len(set(members)) != len(members):
        raise ValueError('Core archive conflicts with current CMake target membership')
    stage = build/('job-'+os.environ['SLURM_JOB_ID'])
    stage.mkdir()
    compiler = '/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpicxx'

    def compile_or_reuse(item):
        filename, target = item
        spec = old/'CMakeFiles'/(target+'.dir')/'flags.make'
        flags = [tok for line in spec.read_text().splitlines() if line.startswith('CXX_')
                 for tok in shlex.split(line.split(' = ', 1)[1])]
        flags = [f.replace(str(old.parents[1]), str(source)) for f in flags]
        flags += ['-isystem', str(Path.home()/'software/petsc-3.23.7/arch-linux-c-opt/include')]
        dep = output([compiler, *flags, '-MM', '-MT', 'obj', filename]).replace('\\\n', ' ')
        inputs = [p for p in (Path(f).resolve() for f in shlex.split(dep.split(':', 1)[1]))
                  if source in p.parents]
        if source/filename not in inputs:
            raise ValueError(f'Compiler dependency scan missed {filename}')
        changed = sorted(str(p.relative_to(source)) for p in inputs
                         if history['source_blobs'].get(str(p.relative_to(source))) != blob(p))
        obj = stage/(Path(filename).name+'.o')
        if target == 'eonsim_core' and not changed:
            obj.write_bytes(subprocess.check_output(['ar', 'p', archive, obj.name]))
        else:
            print('compile', filename, changed, flush=True)
            subprocess.run([compiler, *flags, '-c', filename, '-o', obj], check=True)
        return dict(unit=filename, object=sha(obj), rebuilt=target!='eonsim_core' or bool(changed),
                    changed_inputs=changed)

    targets = [(f, 'eonsim_core') for f in target_list]
    targets += [('src/main.cpp','eonsim'), ('tests/verify_nonlinear_acceptance.cpp','verify_nonlinear_acceptance')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8,len(os.sched_getaffinity(0)))) as pool:
        objects = list(pool.map(compile_or_reuse, targets))
    archive_name = 'libeonsim_core.a'
    subprocess.run(['ar', 'rcs', archive_name, *members], check=True, cwd=stage)
    if output(['ar', 't', stage/archive_name]).splitlines() != members:
        raise ValueError('Rebuilt archive has duplicate or stale members')
    for target in ('eonsim', 'verify_nonlinear_acceptance'):
        link = shlex.split((old/'CMakeFiles'/(target+'.dir')/'link.txt').read_text())
        link = [Path(arg).name if arg.endswith('.o') else arg for arg in link]
        subprocess.run(link, check=True, cwd=stage)
    receipt = dict(source=commit, binary=sha(stage/'eonsim'), archive=sha(stage/archive_name),
                   base_archive=sha(archive), base_binary=history['binary_sha256'], job=os.environ['SLURM_JOB_ID'],
                   test_binary=sha(stage/'verify_nonlinear_acceptance'), objects=objects,
                   libraries=output(['ldd',stage/'eonsim']))
    # Publish atomically after both the build and the acceptance fixture pass.
    for ranks in (1, 2):
        log = stage/f'acceptance-{ranks}.log'
        with log.open('w') as stream:
            subprocess.run(['/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpiexec','--bind-to','core',
                            '-n',str(ranks),str(stage/'verify_nonlinear_acceptance')], cwd=stage,
                           stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
        receipt[f'test_{ranks}_log']=sha(log)
    if output(['git','rev-parse','HEAD'])!=commit:
        subprocess.run(['git','diff','--exit-code',commit,'HEAD','--','src','include','tests/verify_nonlinear_acceptance.cpp',
                        'CMakeLists.txt','cmake'],check=True)
    (stage/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for target in ('eonsim','verify_nonlinear_acceptance','build-receipt.json'):
        pending=build/(target+'.new')
        pending.symlink_to(Path(stage.name)/target)
        pending.replace(build/target)
    print(f'Verified Release {commit} {receipt["binary"]}',flush=True)


if __name__ == '__main__':
    main()
