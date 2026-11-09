"""Execute only the separately prepared and reviewed alpha1 S96 family.

Inspection is read-only. No plan, status, numerical directory, or process is
created until the real three-mode screen and its raw review have completed.
The preparation and execution decisions remain separate immutable records.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import tempfile
import time
import traceback

W = Path('/home/tfblab633/EONSim-prod48-20261107')
D = Path('/mnt/d/EONSim-prod48-20261107')
C = W/'alpha1-s96-fine-family-plan-b0fd881'
STATUS = W/'alpha1-s96-fine-family-current.json'
SCREEN = D/'alpha1-s96-fine-execution-screen-a341bc6'
RAW = W/'alpha1-s96-fine-execution-review-a341bc6'
COARSE = D/'womersley-a1-s96-r8-a8-l0-n400-native32-fcc2956'
CC = W/'alpha1-s96-coarse-n400-fcc2956'
RUNTIME = Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
BINARY = '60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07'
PREPARER = '76af0c77f797dda4f4bec675488c454e7b4663e563b1fb0f6fb45b8ef709f7aa'
KERNEL = 'a7e775f3d2896ba1b7f65f963aa25055bcea5de215141651710730119650d2da'
GIB = 1024**3
DEPENDENCIES = ('alpha1-native200-lu32-recovery', 'alpha1-s96-coarse-n400',
                'alpha1-s96-fine-execution-screen', 'alpha1-s96-fine-execution-review')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pending():
    states = {name: read(W/(name+'-current.json'))['state'] for name in DEPENDENCIES}
    return {name: value for name, value in states.items() if value != 'completed'}


def check_configuration(plan):
    assert plan['prepared'] and not plan['adopted']
    selected = plan['selected']
    assert selected in ('native32', 'four32')
    ranks = 1 if selected == 'native32' else 4
    assert plan['ranks'] == ranks
    assert plan['cpus'] == ([0] if ranks == 1 else list(range(8)))
    assert plan['coarse'] == str(COARSE)
    assert plan['fine'] == str(D/('womersley-a1-s96-r8-a8-l1-n400-'+selected+'-b0fd881'))
    assert plan['time_control'] == str(D/('womersley-a1-s96-r8-a8-l1-n800-'+selected+'-b0fd881'))
    assert plan['steps_per_cycle'] == plan['phases'] == [400, 400, 800]
    assert plan['cycles'] == 6 and plan['warmup'] == 2 and plan['window'] == 32
    assert plan['memory_max_bytes'] == 6*GIB and plan['swap_max_bytes'] == 0
    assert plan['admission_bytes'] == 22*GIB and plan['global_floor_bytes'] == 8*GIB
    assert plan['required_locks'] == ['womersley-direct-memory.lock', 'mpi-queue.lock']
    assert plan['independent_run_review_required'] and plan['numerical_kernel_byte_identical']
    assert plan['coarse_flow_amplitude_failed'] is True


def expected_commands(plan):
    source = C/'source'
    commands = {}
    for n, target in ((400, Path(plan['fine'])), (800, Path(plan['time_control']))):
        commands[f'fine-n{n}'] = [sys.executable, source/'scripts/study_womersley.py',
            '--executable', C/'eonsim', '--work', target, '--seed', '96', '8', '8',
            '--level', '1', '--alpha', '1', '--steps-per-cycle', str(n), '--phases', str(n),
            '--warmup', '2', '--cycles', '6', '--cycles-per-solve', '1', '--ranks', str(plan['ranks']),
            '--mumps', '--lu-reuse-window', '32', '--chord', '--timeout', '86400']
        if plan['ranks'] == 4:
            commands[f'fine-n{n}'] += ['--mpiexec', C/'mpiexec-fixed']
        commands[f'n{n}-analysis'] = [sys.executable, source/'scripts/analyze_womersley.py',
            '--work', target, '--output', C/f'n{n}-analysis.json']
        commands[f'tail-n{n}'] = [sys.executable, source/'scripts/compare_womersley.py',
            '--coarse', target, '--fine', target, '--coarse-cycle', '5', '--fine-cycle', '6',
            '--output', C/f'tail-n{n}.json']
        if n == 400:
            commands['space-n400'] = [sys.executable, source/'scripts/compare_womersley.py',
                '--coarse', COARSE, '--fine', target, '--coarse-cycle', '6', '--fine-cycle', '6',
                '--output', C/'space-n400.json']
    commands['time-n400-n800'] = [sys.executable, source/'scripts/compare_womersley.py',
        '--coarse', plan['fine'], '--fine', plan['time_control'], '--coarse-cycle', '6',
        '--fine-cycle', '6', '--output', C/'time-n400-n800.json']
    commands['budget'] = [sys.executable, C/'budget.py']
    return {label: list(map(str, command)) for label, command in commands.items()}


def check_commands(plan, commands):
    expected = expected_commands(plan)
    assert list(commands) == list(expected) and commands == expected


def clean_resource(path, limit):
    resource = read(path)
    assert resource['returncode'] == 0 and resource['scope_seen']
    assert resource['remaining_scope_members'] == []
    assert resource['memory_max_bytes'] == limit and resource['memory_swap_max_bytes'] == 0
    assert all(int(row.split()[1]) == 0 for row in resource['memory_events'].splitlines())
    assert resource['minimum_available_bytes'] >= 8*GIB
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            assert resource['unit'] not in (proc/'cgroup').read_text()
        except (FileNotFoundError, ProcessLookupError):
            pass
    return sha(path)


def validate_plan():
    assert not pending(), 'Existing family, actual screen, and raw review must all finish first'
    plan = read(C/'definition.json')
    check_configuration(plan)
    assert sha(C/'preparer.py') == plan['preparer_sha256'] == PREPARER
    assert sha(C/'eonsim') == plan['binary_sha256'] == BINARY
    for name, digest in plan['file_hashes'].items():
        assert sha(C/name) == digest
    for name, digest in plan['source_hashes'].items():
        assert sha(C/'source'/name) == sha(SCREEN/'source'/name) == digest
        # Coarse/fine analytics use exactly the same frozen implementation.
        assert sha(CC/'source'/name) == read(CC/'definition.json')['source_hashes'][name] == digest
    for name, digest in plan['input_hashes'].items():
        assert sha(name) == digest
    for name, value in plan['snapshots'].items():
        assert sha(C/name) == sha(value['path']) == value['sha256']
    assert sha(C/'budget-kernel.py') == KERNEL
    check_commands(plan, read(C/'commands.json'))
    definition = read(SCREEN/'definition.json')
    report, raw = read(SCREEN/'report.json'), read(RAW/'review.json')
    assert report['passed'] and report['numerical_passed'] and report['eligible'] and not report['adopted']
    assert raw['passed'] and raw['eligible'] and not raw['adopted']
    assert raw['selected'] == report['selected'] == plan['selected']
    assert raw['definition_sha256'] == sha(SCREEN/'definition.json')
    assert raw['report_sha256'] == sha(SCREEN/'report.json')
    assert raw['candidate_sha256'] == definition['candidate_sha256'] == BINARY
    assert sha(SCREEN/'controller.py') == definition['controller_sha256']
    assert sha(RAW/'controller.py') == raw['controller_sha256']
    assert raw['datasets_reopened'] == 1440 and raw['states_per_mode'] == 32
    assert raw['comparisons'] == report['comparisons'] and raw['raw_state_hashes'] == report['raw_state_hashes']
    assert plan['expected_fine_mesh_sha256'] == definition['mesh_sha256'] == sha(SCREEN/'fluid.msh')
    assert sha(C/'bounded_cgroup_job_6g.py') == definition['cap_sha256']
    assert sha(C/'rank-guard.py') == definition['guard_sha256']
    seconds = raw['seconds']
    assert all(math.isfinite(value) and value > 0 for value in seconds.values())
    assert all(seconds[plan['selected']] <= .9*seconds[name] for name in seconds if name != plan['selected'])
    resources = {}
    for name in ('prepare', 'four8', 'native32', 'four32'):
        path = SCREEN/(name+'.resource.json')
        resources[str(path)] = clean_resource(path, 6*GIB)
        if name != 'prepare':
            assert read(path) == report['runs'][name]['resource']
            assert seconds[name] == read(path)['wall_seconds']
    path = RAW/'review.resource.json'
    resources[str(path)] = clean_resource(path, 2*GIB)
    for name, digest in raw['raw_state_hashes'].items():
        assert sha(name) == digest
    assert read(COARSE/'receipt.json')['step'] == 2400
    gates = read(CC/'analysis.json')['preliminary_gates']
    assert gates['periodic'] and gates['global_mass'] and gates['flow_amplitude'] is False
    return plan, resources


def resources_free():
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc/'cmdline').read_bytes().split(b'\0')
            if argv and Path(os.fsdecode(argv[0])).name.startswith(('eonsim', 'svFSI')):
                assert not set(range(8)).intersection(os.sched_getaffinity(int(proc.name)))
        except (FileNotFoundError, ProcessLookupError):
            pass
    assert shutil.disk_usage(D).free > 80*GIB


def check_finished_study(path, n, plan):
    assert sha(path/'fluid.msh') == plan['expected_fine_mesh_sha256']
    assert sha(path/'eonsim') == BINARY
    definition = read(path/'definition.json')
    coarse = dict(read(COARSE/'definition.json'))
    coarse.update(level=1, ranks=plan['ranks'], steps_per_cycle=n, phases=n)
    assert definition == coarse
    assert read(path/'receipt.json')['step'] == 6*n
    attempts = sorted(path.glob('attempt-*'))
    assert len(attempts) == 6
    residual_max = 0.
    for cycle, attempt in enumerate(attempts, 1):
        receipt = read(attempt/'receipt.json')
        assert receipt['step'] == cycle*n and receipt['cycles_per_solve'] == 1
        assert receipt['definition'] == definition
        log = (attempt/'solve.log').read_text()
        assert 'status=success' in log
        rows = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in log.splitlines()
                if line.startswith('fluid_step=')]
        assert [int(row['fluid_step']) for row in rows] == list(range((cycle-1)*n+1, cycle*n+1))
        assert all(int(row['snes_iterations']) >= 0 and math.isfinite(float(row['residual'])) for row in rows)
        residual_max = max(residual_max, max(float(row['residual']) for row in rows))
    # The frozen solver throws on non-positive convergence reasons before these
    # accepted-step records. This log does not emit optional solver_report rows.
    return dict(steps=6*n,cycles=6,accepted_rows=6*n,maximum_reported_residual=residual_max,
                mesh_sha256=sha(path/'fluid.msh'),definition_sha256=sha(path/'definition.json'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('inspect', 'review', 'run'))
    args = parser.parse_args()
    if args.action == 'inspect':
        missing = pending()
        existing = read(STATUS) if STATUS.exists() else None
        print(json.dumps(dict(ready=not missing and (C/'definition.json').is_file() and existing is None,
                              pending=missing,plan_exists=C.exists(),execution_state=existing,
                              adopted=existing.get('adopted',False) if existing else False)))
        return
    plan, resources = validate_plan()
    assert not STATUS.exists(), 'Never restart or replace an existing execution controller'
    assert not Path(plan['fine']).exists() and not Path(plan['time_control']).exists()
    if args.action == 'review':
        assert not (C/'execution-review.json').exists() and not (C/'execution-controller.py').exists()
        shutil.copy2(__file__, C/'execution-controller.py')
        dump(C/'execution-review.json', dict(passed=True,adopted=False,
            decision='run_alpha1_s96_fine_n400_n800_measured_policy',
            definition_sha256=sha(C/'definition.json'),controller_sha256=sha(C/'execution-controller.py'),
            candidate_sha256=BINARY,screen_report_sha256=sha(SCREEN/'report.json'),
            raw_review_sha256=sha(RAW/'review.json'),resource_sha256=resources,
            scope='Executing-agent pre-execution review of the concrete plan. Reuses the separate1440-dataset raw review; no external independent review or physical qualification claimed.'))
        print(json.dumps(dict(reviewed=True,adopted=False,definition_sha256=sha(C/'definition.json'))))
        return
    review = read(C/'execution-review.json')
    assert review['passed'] and not review['adopted']
    assert review['decision'] == 'run_alpha1_s96_fine_n400_n800_measured_policy'
    assert review['definition_sha256'] == sha(C/'definition.json')
    assert review['controller_sha256'] == sha(C/'execution-controller.py') == sha(__file__)
    assert review['resource_sha256'] == resources
    assert review['candidate_sha256'] == BINARY and review['raw_review_sha256'] == sha(RAW/'review.json')
    assert review['screen_report_sha256'] == sha(SCREEN/'report.json')
    spec = importlib.util.spec_from_file_location('cap', C/'bounded_cgroup_job_6g.py')
    cap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cap)
    assert cap.LIMIT == 6*GIB
    env = {key:value for key,value in os.environ.items() if not key.startswith(('OMPI_', 'PMIX_', 'PRTE_'))
           and key not in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH')}
    env.update(PATH=str(RUNTIME/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(RUNTIME/'lib'),
               OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
               OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',OMPI_MCA_mpi_yield_when_idle='1',
               TMPDIR=tempfile.mkdtemp(prefix='eonsim-alpha1-s96-family-'))
    adopted = False

    def update(state, **values):
        value = dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                     control=str(C),adopted=adopted,**values)
        temporary = STATUS.with_suffix('.tmp')
        dump(temporary,value)
        temporary.replace(STATUS)
        print(json.dumps(value),flush=True)

    def interrupted(signum, frame):
        raise KeyboardInterrupt('Alpha1 S96 family interrupted; no automatic retry')

    signal.signal(signal.SIGINT,interrupted)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        import fcntl
        update('waiting_for_resources')
        with (W/'womersley-direct-memory.lock').open('a') as memory, (W/'mpi-queue.lock').open('a') as cpu:
            fcntl.flock(memory,fcntl.LOCK_EX)
            fcntl.flock(cpu,fcntl.LOCK_EX)
            resources_free()
            os.sched_setaffinity(0,set(plan['cpus']))
            assert not pending()
            adopted = True
            dump(C/'adoption.json',dict(adopted=True,definition_sha256=sha(C/'definition.json'),
                review_sha256=sha(C/'execution-review.json'),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                full_qualification=False))
            for label, command in read(C/'commands.json').items():
                resources_free()
                while cap.available() <= 22*GIB:
                    update('waiting_for_memory_admission',job=label)
                    time.sleep(5)
                dump(C/(label+'-command.json'),command)
                update('running',job=label)
                cap.run([sys.executable,C/'workflow-guard.py',*command],C/'source',C/(label+'.log'),env,
                        f'eonsim-a1-s96-family-{label}-{os.getpid()}.scope',
                        172800 if label.startswith('fine-n') else 14400)
                clean_resource(C/(label+'.resource.json'),6*GIB)
                if label in ('fine-n400','fine-n800'):
                    n = int(label.split('n')[-1])
                    path = Path(plan['fine'] if n == 400 else plan['time_control'])
                    dump(C/(label+'-accepted-steps.json'),check_finished_study(path,n,plan))
            for path, digest in plan['input_hashes'].items():
                assert sha(path) == digest
            for name, value in plan['snapshots'].items():
                assert sha(value['path']) == value['sha256']
            budget = read(C/'budget.json')
            dump(C/'completion.json',dict(completed=True,adopted=True,passed=budget['passed'],
                full_project_qualification=False,definition_sha256=sha(C/'definition.json'),
                budget_sha256=sha(C/'budget.json'),coarse_flow_failure_preserved=True))
        update('completed',passed=budget['passed'],full_project_qualification=False)
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc(),adopted=adopted))
        update('failed',error=str(error))
        raise


if __name__ == '__main__':
    main()
