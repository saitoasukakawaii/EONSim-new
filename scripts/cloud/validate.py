"""Run existing CMake/CTest contracts and preserve failure evidence (Linux cloud)."""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def resources():
    cpus = len(os.sched_getaffinity(0))
    memory = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    limits = {}
    # Locate this process in each visible cgroup-v2 mount, then honor ancestors.
    group = next((line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                  if line.startswith('0::')), None)
    directories = set()
    if group is not None:
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            before, after = line.split(' - ', 1)
            if after.split()[0] != 'cgroup2':
                continue
            fields = before.split()
            mount = Path(fields[4])
            directories.add(mount)
            try:
                relative = Path(group).relative_to(fields[3])
            except ValueError:
                continue
            current = mount / relative
            while current.is_relative_to(mount):
                directories.add(current)
                if current == mount:
                    break
                current = current.parent
    for directory in sorted(directories):
        values = {}
        for key in ('cpu.max', 'memory.max'):
            path = directory / key
            if path.exists():
                values[key] = path.read_text().strip()
        limits[str(directory)] = values
        quota = values.get('cpu.max', 'max 100000').split()
        if quota[0] != 'max':
            cpus = min(cpus, max(1, math.floor(int(quota[0]) / int(quota[1]))))
        if values.get('memory.max', 'max') != 'max':
            memory = min(memory, int(values['memory.max']))
    return dict(cpu_budget=cpus, memory_bytes=memory, cgroup=limits,
                build_jobs=max(1, min(4, cpus, memory // (2 * 1024**3))))


def enable_child_reaping():
    # CTest/Python/MPI launch descendants; adopt them if their launcher exits first.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot enable Linux child subreaper')


def reap_children():
    """Only descendants of this validator; never kill unrelated MPI jobs."""
    killed = []
    deadline = time.monotonic() + 5
    while True:
        for stat in Path('/proc').glob('[0-9]*/stat'):
            try:
                fields = stat.read_text().rsplit(')', 1)[1].split()
                if int(fields[1]) == os.getpid() and fields[0] != 'Z':
                    pid = int(stat.parent.name)
                    os.kill(pid, signal.SIGKILL)
                    killed.append(pid)
            except (FileNotFoundError, ProcessLookupError):
                pass
        try:
            # A killed adopted parent may leave its own children: scan again.
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            return killed
        if time.monotonic() > deadline:
            raise RuntimeError('Could not reap all validation descendants')
        time.sleep(0.01)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['debug', 'release'], required=True)
    ap.add_argument('--selection', choices=['core', 'all', 'mpi-failure'], required=True)
    ap.add_argument('--version', choices=['3.23.7', '3.19.6'], required=True)
    a = ap.parse_args()
    enable_child_reaping()
    def terminated(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminated)
    prefix = Path(os.environ['CONDA_PREFIX']).resolve()
    build = ROOT / 'build' / f'cloud-{a.version}-{a.mode}'
    evidence = build / 'evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    summary = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                   mode=a.mode, selection=a.selection, petsc=a.version, platform=platform.platform(),
                   resources=resources(), commands=[], tests=[], status='running')

    def run(cmd, name, timeout=1800, check=True):
        start = time.monotonic()
        log = evidence / (name + '.log')
        timed_out = False
        with log.open('w') as stream:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                # The leader may exit before a descendant that ignores TERM.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                code = 124
        leftovers = reap_children()
        if leftovers and code == 0:
            code = 1
        summary['commands'].append(dict(cleaned_live_descendants=leftovers, command=cmd, exit_code=code, timeout=timed_out,
                                        seconds=time.monotonic()-start, log=str(log.relative_to(build))))
        print(f'{name}: exit={code}, log={log}', flush=True)
        if code and os.environ.get('GITHUB_ACTIONS') == 'true':
            detail = '\n'.join(log.read_text(errors='replace').splitlines()[-35:])
            detail = detail.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=EONSim {name}::{detail}', flush=True)
        if check and code:
            raise RuntimeError(f'{name} failed; see {log}')
        return code, log

    try:
        if sys.flags.optimize:
            raise RuntimeError('Python optimization disables numerical assertions; unset PYTHONOPTIMIZE')
        lock = ROOT / 'environments' / f'petsc-{a.version}-linux-64.lock'
        summary['lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
        packages = [json.loads(p.read_text()) for p in (prefix / 'conda-meta').glob('*.json')]
        actual = {p['name']: p for p in packages}
        for line in lock.read_text().splitlines():
            if not line.startswith('https://'):
                continue
            url, sha = line.split('#')
            package = next((p for p in packages if p.get('url') == url), None)
            if package is None or package.get('sha256') != sha:
                raise RuntimeError(f'Environment differs from lock: {url}')
        for filename in ('include/petscconf.h', 'lib/petsc/conf/petscvariables'):
            shutil.copy2(prefix/filename, evidence/Path(filename).name)
        summary['dependencies'] = [{k: p.get(k) for k in ('name', 'version', 'build', 'url', 'sha256')} for p in packages]
        if actual['petsc']['version'] != a.version or not actual['petsc']['build'].startswith('real_'):
            raise RuntimeError('Expected locked real PETSc')
        for command in [('compiler', [os.environ['CXX'], '--version']), ('mpi-compiler', [str(prefix/'bin/mpicxx'), '--showme']),
                        ('mpi-runtime', [str(prefix/'bin/mpiexec'), '--version']), ('cmake', ['cmake', '--version'])]:
            run(command[1], command[0], 30)
        run(['cmake', '--preset', a.mode, '-B', str(build), '-DBUILD_TESTING=ON',
             '-DCMAKE_PREFIX_PATH='+str(prefix), '-DMPIEXEC_EXECUTABLE='+str(prefix/'bin/mpiexec'),
             '-DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS'], 'configure', 180)
        run(['cmake', '--build', str(build), '--parallel', str(summary['resources']['build_jobs'])], 'build')
        _, linkage = run(['ldd', str(build/'eonsim')], 'runtime-linkage', 30)
        libs = linkage.read_text().splitlines()
        for name in ('libmpi.so', 'libpetsc'):
            matches = [line for line in libs if name in line]
            if len(matches) != 1 or str(prefix/'lib') not in matches[0]:
                raise RuntimeError(f'MPI/PETSc linkage outside locked prefix: {name}')
        run([str(prefix/'bin/mpiexec'), '-n', '2', str(build/'verify_runtime')], 'runtime-preflight', 30)
        select = [] if a.selection == 'all' else ['-L', '^'+a.selection+'$']
        _, inventory = run(['ctest', '--test-dir', str(build), '--show-only=json-v1', *select], 'test-inventory', 30)
        tests = json.loads(inventory.read_text())['tests']
        if not tests:
            raise RuntimeError('Empty test selection')
        # Remove prior results so a failed invocation cannot reuse stale evidence.
        junit = evidence/'junit.xml'
        junit.unlink(missing_ok=True)
        code, _ = run(['ctest', '--test-dir', str(build), '-T', 'Test', '--no-compress-output',
                       '--output-junit', str(junit), '--no-tests=error', '-j', '1', '-V', *select],
                      'ctest', 3600, check=False)
        tree = ET.parse(junit)
        inventory_by_name = {t['name']: t for t in tests}
        for case in tree.findall('.//testcase'):
            name = case.attrib['name']
            props = {p['name']: p['value'] for p in inventory_by_name[name]['properties']}
            failed = case.find('failure') is not None
            skipped = case.find('skipped') is not None or case.get('status') in ('notrun', 'disabled')
            status = 'skipped' if skipped else 'failed' if failed else 'passed'
            summary['tests'].append(dict(name=name, status=status,
                ranks=[int(x.removeprefix('rank-')) for x in props.get('LABELS', []) if x.startswith('rank-')],
                exit_code=0 if status=='passed' else None,
                timeout='timeout' in ET.tostring(case, encoding='unicode').lower(),
                seconds=float(case.get('time', 0)), log='evidence/junit.xml#'+name))
        tag = (build/'Testing/TAG').read_text().splitlines()[0]
        details = ET.parse(build/'Testing'/tag/'Test.xml')
        by_name = {t['name']: t for t in summary['tests']}
        for test in details.findall('.//Testing/Test'):
            name = test.findtext('Name')
            if name not in by_name:
                continue
            measurements = {v.get('name'): v.findtext('Value') for v in test.findall('./Results/NamedMeasurement')}
            if 'Exit Value' in measurements:
                by_name[name]['exit_code'] = int(measurements['Exit Value'])
            by_name[name]['exit_behavior'] = measurements.get('Exit Code', 'Completed')
            by_name[name]['timeout'] = measurements.get('Exit Code') == 'Timeout'
        if code or len(summary['tests']) != len(tests) or any(t['status'] != 'passed' for t in summary['tests']):
            raise RuntimeError('CTest failure, unexpected skip, or incomplete results')
        summary['status'] = 'passed'
    except Exception as error:
        summary['status'] = 'failed'
        summary['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        (evidence/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return 0 if summary['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
