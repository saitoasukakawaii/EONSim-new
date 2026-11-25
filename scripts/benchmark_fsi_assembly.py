"""Paired FSI assembly measurements with pinned binaries and physical output checks.

Both binaries run the same independent fluid/solid meshes, direct solver and
accepted time grid. One warmup pair precedes at least three alternating pairs.
Timing is evidence, never a pass criterion. Saved fields, every accepted step,
field acceptance and true linear residuals must agree before a pair is reported.
Execution-only flags can follow either --baseline-options or --candidate-options
until the next driver argument, or use --candidate-options='-fsi_threads 2'.
Use --baseline-assembly-report with a PR51-or-newer baseline to compare startup.
Only -fsi_threads controls element workers; dependency OpenMP/BLAS threads stay 1.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/fsi'))
from generate_domains import generate

TIMERS = ('setup_seconds', 'schur_setup_seconds', 'solve_seconds', 'assembly_seconds',
          'callback_seconds', 'failure_sync_seconds', 'assembly_finalize_seconds',
          'constraint_seconds', 'ghost_seconds', 'linear_seconds',
          'linear_diagnostic_seconds', 'finalize_seconds')
METRICS = ('wall_seconds', *TIMERS, 'peak_rss_max_bytes', 'peak_rss_sum_bytes')
INITIALIZATION_TIMERS = ('pattern_seconds', 'plan_seconds', 'system_seconds', 'setup_seconds')
INITIALIZATION_METRICS = tuple('initialization_'+key for key in INITIALIZATION_TIMERS)
FIELD_LIMIT = 2e-9


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(text, marker):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(marker)]


def number(row, key, minimum=None, integer=False):
    value = float(row[key])
    require(math.isfinite(value) and (minimum is None or value >= minimum),
            ('Invalid measurement', key, row[key]))
    require(not integer or value.is_integer(), ('Noninteger counter', key, value))
    return int(value) if integer else value


def option_arguments(arguments):
    """Group PETSc flags until the next driver argument; quoted groups also work."""
    result, index = [], 0
    while index < len(arguments):
        argument = arguments[index]
        index += 1
        if argument in ('--baseline-options', '--candidate-options'):
            values = []
            while index < len(arguments) and not arguments[index].startswith('--'):
                values.extend(shlex.split(arguments[index]))
                index += 1
            result.append(argument+'='+shlex.join(values))
        else:
            result.append(argument)
    return result


def execution_options(options):
    """Accept execution changes only; physics and solver inputs stay fixed."""
    settings = dict(fsi_coo=False, fsi_threads=1, fsi_residual_coo=None, nonlinear_reuse=None)
    booleans = {'-fsi_coo', '-fsi_residual_coo', '-nonlinear_reuse'}
    seen, index = set(), 0
    while index < len(options):
        option = options[index]
        index += 1
        if option not in booleans | {'-fsi_threads'} or option in seen:
            raise ValueError('Unsupported or duplicated execution option: '+option)
        seen.add(option)
        if option == '-fsi_threads':
            if index == len(options) or not re.fullmatch(r'[1-9][0-9]*', options[index]):
                raise ValueError('-fsi_threads requires an integer between 1 and 256')
            value = int(options[index])
            index += 1
            if value > 256:
                raise ValueError('-fsi_threads requires an integer between 1 and 256')
        else:
            value = True
            if index < len(options) and options[index] in ('true', 'false'):
                value = options[index] == 'true'
                index += 1
        settings[option[1:]] = value
    return settings


def parse_log(text, count, ranks, dt):
    require(text.count('status=success') == 1, 'Missing or duplicate success marker')
    require(not any(x in text for x in ('step_retry=', 'linear_residual_unavailable',
                                      'linear_iteration_limit_residual ')),
            'Unexpected rejected step or unavailable linear residual')
    reports, accepted = records(text, 'solver_report '), records(text, 'fsi_step=')
    events = [kind for line in text.splitlines() for prefix, kind in
              [('solver_report ', 'report'), ('fsi_step=', 'step')] if line.startswith(prefix)]
    require(events == ['report', 'step'] * count, 'Incomplete or out-of-order accepted trajectory')
    for i, (report, step) in enumerate(zip(reports, accepted), 1):
        require(number(step, 'fsi_step', 1, True) == i and
                math.isclose(number(step, 'time', 0), i * dt, rel_tol=0, abs_tol=1e-13) and
                math.isclose(number(step, 'accepted_dt', 0), dt, rel_tol=0, abs_tol=1e-13),
                ('Wrong accepted time', i, step))
        require(number(report, 'ranks', 1, True) == ranks, 'Wrong rank count')
        require(number(report, 'domain_rejections', 0, True) == 0, 'Rejected geometry evaluation')
        require(report['ksp'] == 'preonly' and report['pc'] == 'lu', 'Direct solver was overridden')
        for key in ('snes_reason', 'ksp_reason'):
            number(report, key, 1, True)
        for key in ('dofs', 'linear_iterations', 'linear_started', 'linear_completed'):
            report[key] = number(report, key, 0, True)
        require(report['linear_started'] == report['linear_completed'], 'Unfinished linear correction')
        report['snes_iterations'] = number(step, 'snes_iterations', 0, True)
        for key in (*TIMERS, 'nnz', 'peak_rss_max_bytes', 'peak_rss_sum_bytes'):
            report[key] = number(report, key, 0)
        require(all(report[key] <= report['assembly_seconds']*1.0001+1e-9 for key in
                    ('callback_seconds', 'failure_sync_seconds', 'assembly_finalize_seconds', 'constraint_seconds')),
                'A measured phase exceeds its enclosing assembly time')
        for key, value in step.items():
            number(step, key)
        number(step, 'residual', 0)
        require(min(number(step, key, 0) for key in
                    ('endpoint_min_fluid_j', 'endpoint_min_solid_j')) > 0,
                'Invalid accepted geometry')
        require(abs(number(step, 'body_balance')) <= FIELD_LIMIT and
                abs(number(step, 'power_balance')) <= FIELD_LIMIT,
                'Interface force or power balance failed')
    fields = records(text, 'field_residual ')
    require(len(fields) == 4 * count, 'Missing per-field acceptance evidence')
    for i in range(count):
        group = fields[4*i:4*i+4]
        require({x['name'] for x in group} == {'velocity', 'pressure', 'mesh', 'structure'},
                'Missing or duplicated physical acceptance field')
        for row in group:
            require(number(row, 'accepted', 0, True) == 1 and
                    number(row, 'rms', 0) <= number(row, 'limit', 0), 'Unaccepted physical field')
    corrections = records(text, 'linear_residual ')
    require(len(corrections) == sum(x['linear_completed'] for x in reports) and corrections,
            'Missing true linear correction residuals')
    worst = 0.
    for row in corrections:
        norm, rhs = number(row, 'norm', 0), number(row, 'rhs_norm', 0)
        target = 1e-12 + 1e-10 * rhs
        require(norm <= target, ('True linear residual exceeds fixed gate', norm, target))
        worst = max(worst, norm / target)
    return dict(steps=reports, accepted=accepted, fields=fields,
                linear_corrections=len(corrections), max_linear_residual_ratio=worst,
                plan=records(text, 'fsi_assembly_plan '), execution_plan=records(text, 'fsi_execution_plan '))


def check_plan(plans, coo, cells):
    require(len(plans) == 1, 'Expected one rank-zero assembly setup report')
    plan = plans[0]
    require(number(plan, 'coo', 0, True) == int(coo) and
            number(plan, 'cells', 1, True) == cells and
            0 <= number(plan, 'interface_cells', 0, True) <= cells,
            'Unexpected assembly backend or cell counts')
    entries = number(plan, 'coo_entries', 0, True)
    size = number(plan, 'coo_value_bytes', 0, True)
    largest = number(plan, 'coo_value_bytes_max', 0, True)
    require((entries > 0 and size >= 8*entries and 0 < largest <= size) if coo
            else entries == size == largest == 0, 'Invalid COO value storage report')
    times = [number(plan, key, 0) for key in ('pattern_seconds', 'plan_seconds', 'system_seconds')]
    total = number(plan, 'setup_seconds', 0)
    require(max(times) <= total*1.0001+1e-9 and total <= sum(times)*1.0001+1e-9,
            'Inconsistent maximum-rank setup timers')


def check_execution(row, settings, reported):
    plans = row['execution_plan']
    if plans:
        require(reported and len(plans) == 1, 'Unexpected or duplicated execution plan')
        plan = plans[0]
        require(number(plan, 'threads_requested', 1, True) == settings['fsi_threads'],
                'Requested kernel thread count was not used')
        residual_coo = number(plan, 'residual_coo', 0, True)
        require(residual_coo in (0, 1) and (settings['fsi_residual_coo'] is None or
                residual_coo == int(settings['fsi_residual_coo'])), 'Wrong residual assembly backend')
        size, largest = (number(plan, key, 0, True) for key in
                         ('residual_value_bytes', 'residual_value_bytes_max'))
        require((0 < largest <= size) if residual_coo else size == largest == 0,
                'Invalid residual COO storage report')
        batch = number(plan, 'batch_cells', 1, True)
        require(batch > 1 if settings['fsi_threads'] > 1 else batch == 1, 'Wrong kernel batch mode')
    elif reported:
        # PR51 can report its assembly plan but predates execution-plan fields.
        require(settings['fsi_threads'] == 1 and settings['fsi_residual_coo'] is None,
                'Requested execution mode has no runtime evidence')
    if any('solver_reused' in step or 'solver_generation' in step for step in row['steps']):
        expected = settings['nonlinear_reuse']
        previous = 0
        for step in row['steps']:
            reused = number(step, 'solver_reused', 0, True)
            generation = number(step, 'solver_generation', 1, True)
            require(reused in (0, 1), 'Invalid nonlinear session report')
            if previous == 0:
                require(reused == 0 and generation == 1, 'First solve did not construct a fresh session')
            else:
                if expected is None:
                    expected = bool(reused)
                require(reused == int(expected) and generation == previous+(not expected),
                        'Nonlinear session lifetime changed during an unchanged trajectory')
            previous = generation
        row['nonlinear_reuse_observed'] = expected
    else:
        require(settings['nonlinear_reuse'] is None, 'Requested nonlinear reuse mode has no runtime evidence')
        row['nonlinear_reuse_observed'] = None


def physical_fields(path, ranks):
    """Identify physical fields by domain/source node, independent of rank ordering."""
    owned, ghosts = {}, []
    for solid in ('', '_solid'):
        parts, support = [], set()
        for rank in range(ranks):
            suffix = solid + (f'_rank{rank}' if ranks > 1 else '') + '.vtu'
            piece = path.with_name(path.stem + suffix)
            tree = ET.parse(piece)
            arrays = {}
            for array in tree.findall('.//PointData/DataArray'):
                name = array.attrib['Name']
                require(name not in arrays, ('Duplicate output array', piece, name))
                arrays[name] = (int(array.attrib.get('NumberOfComponents', '1')),
                                list(map(float, (array.text or '').split())))
            require('mesh_node_id' in arrays and 'owner' in arrays, 'Missing output ownership')
            ids, owners = arrays['mesh_node_id'][1], arrays['owner'][1]
            count = len(ids)
            require(count and len(owners) == count, 'Invalid output identity lengths')
            arrays['coordinates'] = (3, list(map(float, tree.find('.//Points/DataArray').text.split())))
            for name, (width, values) in arrays.items():
                require(width > 0 and len(values) == width * count and all(map(math.isfinite, values)),
                        ('Invalid physical output', piece, name))
            connectivity = list(map(int, tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            require(all(0 <= i < count for i in connectivity), 'Invalid output connectivity')
            support.update(ids[i] for i in connectivity)
            parts.append(arrays)
        require(support, ('No physical domain cells', solid))
        for rank, arrays in enumerate(parts):
            ids, owners = arrays['mesh_node_id'][1], arrays['owner'][1]
            for i, (node, owner) in enumerate(zip(ids, owners)):
                require(node.is_integer() and owner.is_integer() and 0 <= owner < ranks,
                        ('Invalid node/owner identity', solid, rank, node, owner))
                if node not in support:
                    continue
                for name, (width, values) in arrays.items():
                    if name in ('mesh_node_id', 'owner', 'algebra_node_id'):
                        continue
                    key = (solid, int(node), name)
                    value = values[width*i:width*(i+1)]
                    if owner == rank:
                        require(key not in owned, ('Duplicate owned node', key))
                        owned[key] = value
                    else:
                        ghosts.append((key, value))
    require(owned, 'No owned physical fields')
    for key, value in ghosts:
        require(key in owned and len(value) == len(owned[key]) and
                max(abs(a-b) for a, b in zip(value, owned[key])) <= FIELD_LIMIT,
                ('Ghost field disagrees with owner', key))
    return owned


def compare_fields(expected, actual):
    require(expected.keys() == actual.keys(), 'Physical field/node sets differ')
    worst = 0.
    for key in expected:
        require(len(expected[key]) == len(actual[key]), ('Physical field width differs', key))
        worst = max(worst, max(abs(a-b) for a, b in zip(expected[key], actual[key])))
    require(worst <= FIELD_LIMIT, ('Saved physical field difference', worst))
    return worst


def history(path, steps, dt):
    with path.open() as stream:
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    require(len(rows) == steps and all(all(map(math.isfinite, row.values())) for row in rows),
            'Invalid accepted history')
    for i, row in enumerate(rows, 1):
        require(row['step'] == i and abs(row['time'] - i * dt) < 1e-13 and
                abs(row['accepted_dt'] - dt) < 1e-13, 'Incorrect history time grid')
        require(abs(row['evaluation_body_balance']) <= FIELD_LIMIT and
                abs(row['evaluation_power_balance']) <= FIELD_LIMIT, 'History force/power imbalance')
    return rows


def compare_history(first, second):
    require(len(first) == len(second), 'History lengths differ')
    worst = 0.
    for x, y in zip(first, second):
        require(x.keys() == y.keys(), 'History columns differ')
        for key in x:
            worst = max(worst, abs(x[key] - y[key]))
    require(worst <= FIELD_LIMIT, ('Accepted history discrepancy', worst))
    return worst


def stats(values):
    return dict(median=statistics.median(values), minimum=min(values), maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--baseline-commit', required=True, help='Actual baseline build source SHA')
    parser.add_argument('--candidate-commit', required=True, help='Actual candidate build source SHA')
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--subdivisions', type=int, nargs='+', default=[4, 8])
    parser.add_argument('--ranks', type=int, nargs='+', default=[1, 2])
    parser.add_argument('--steps', type=int, default=5)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--petsc-log', action='store_true', help='Equal event logging overhead in both modes')
    parser.add_argument('--baseline-assembly-report', action='store_true',
                        help='Report baseline initialization too; requires a PR51-or-newer baseline')
    for mode in ('baseline', 'candidate'):
        parser.add_argument('--'+mode+'-options', type=shlex.split, default=[], metavar='FLAGS',
                            help='Execution flags: -fsi_coo, -fsi_residual_coo, -fsi_threads, -nonlinear_reuse')
    try:
        args = parser.parse_args(option_arguments(sys.argv[1:]))
        options = {mode: getattr(args, mode+'_options') for mode in ('baseline', 'candidate')}
        settings = {mode: execution_options(value) for mode, value in options.items()}
    except ValueError as exc:
        parser.error(str(exc))
    if args.repeats < 3 or args.steps < 2:
        parser.error('Use at least three pairs and two accepted steps')
    if args.ranks != sorted(set(args.ranks)) or any(x not in (1, 2, 4) for x in args.ranks):
        parser.error('Use an ascending unique subset of ranks 1/2/4')
    if args.subdivisions != sorted(set(args.subdivisions)) or any(x < 2 for x in args.subdivisions):
        parser.error('Use ascending unique subdivisions >= 2')
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in
               (args.baseline_commit, args.candidate_commit)):
        parser.error('Provide complete 40-character build source SHAs')
    if ((settings['baseline']['fsi_threads'] != 1 or settings['baseline']['fsi_residual_coo'] is not None)
            and not args.baseline_assembly_report):
        parser.error('Baseline thread/residual options require --baseline-assembly-report for execution evidence')
    binaries = dict(baseline=args.baseline.resolve(), candidate=args.candidate.resolve())
    require(all(path.is_file() for path in binaries.values()), 'Executable not found')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', OMP_PROC_BIND='FALSE',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    binding = ['--bind-to', 'none'] if any(value['fsi_threads'] > 1 for value in settings.values()) else []
    comparison_metrics = (*METRICS, *INITIALIZATION_METRICS) if args.baseline_assembly_report else METRICS
    result = dict(status='running', source_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        source_script_sha256=digest(__file__),
        element_threads_per_rank={mode: value['fsi_threads'] for mode, value in settings.items()},
        library_threads_per_rank=1,
        baseline_options=args.baseline_options, candidate_options=args.candidate_options,
        execution_options=settings, mpi_binding_options=binding,
        baseline_assembly_reporting=args.baseline_assembly_report,
        field_absolute_limit=FIELD_LIMIT, linear_gate='1e-12 + 1e-10 * rhs_norm',
        timer_scope='Per-step maximum-rank timers may overlap; wall includes startup, output and shutdown. '
                    'initialization_* are once-per-run maximum-rank timers, separate from per-step solver setup.',
        wall_clock='Blocking child wait with an independent timeout watchdog; no timeout polling in the measured wait.',
        petsc_event_logging=args.petsc_log, binaries={}, commands=[], cases=[], runs=[], pairs=[])
    for mode, path in binaries.items():
        result['binaries'][mode] = dict(path=str(path), sha256=digest(path),
            build_source_commit=getattr(args, mode+'_commit'))
        for name, source in [('cmake_cache', path.parent/'CMakeCache.txt'),
                             ('build_receipt', path.parent/'evidence/summary.json')]:
            if source.is_file():
                target = work/(mode+'-'+name+source.suffix)
                target.write_bytes(source.read_bytes())
                result['binaries'][mode][name] = dict(path=target.name, sha256=digest(target))

    def save():
        (work/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')

    def run(command, label, timeout=600, threads=1):
        command = list(map(str, command))
        record = dict(command=command, log=label+'.log', returncode=None, timeout=False,
                      element_threads_per_rank=threads)
        result['commands'].append(record)
        begin = time.perf_counter()
        with (work/record['log']).open('w') as stream:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            expired = threading.Event()

            def stop_group():
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                # Also retire descendants if the MPI launcher exited first.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()

            def deadline():
                if process.poll() is None:
                    expired.set()
                    stop_group()

            # Popen.wait(timeout=...) polls on POSIX and quantizes short wall
            # measurements. A watchdog keeps the limit without polling the
            # successful command; its cleanup waits run only on failure.
            watchdog = threading.Timer(timeout, deadline)
            watchdog.daemon = True
            watchdog.start()
            try:
                record['returncode'] = process.wait()
                if expired.is_set():
                    raise subprocess.TimeoutExpired(command, timeout)
            except BaseException:
                stop_group()
                raise
            finally:
                watchdog.cancel()
                watchdog.join()
                record['returncode'] = process.returncode
                record['timeout'] = expired.is_set()
                record['seconds'] = time.perf_counter()-begin
                save()
        require(record['returncode'] == 0, ('Command failed', record))
        return record['seconds'], (work/record['log']).read_text()

    try:
        result['environment'] = []
        for command in ([args.mpiexec, '--version'], ['c++', '--version'],
                        ['pkg-config', '--modversion', 'PETSc'], ['cmake', '--version'], ['uname', '-a']):
            probe = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=20)
            require(probe.returncode == 0, ('Cannot record environment', command, probe.stdout))
            result['environment'].append(dict(command=command, output=probe.stdout))
        result['cpu_affinity'] = sorted(os.sched_getaffinity(0))
        result['cgroup'] = Path('/proc/self/cgroup').read_text()
        for name in ('cpu.max', 'memory.max'):
            path = Path('/sys/fs/cgroup')/name
            if path.exists():
                result[name] = path.read_text().strip()
        for n in args.subdivisions:
            case = generate(work/f'n{n}-input', n)
            config = json.loads(case.read_text())
            config['fsi'].update(steps=args.steps, output_interval=1)
            case.write_text(json.dumps(config, indent=2)+'\n')
            dt = config['fsi']['dt']
            result['cases'].append(dict(subdivisions=n, case=str(case.relative_to(work)),
                input_sha256={p.name: digest(p) for p in case.parent.iterdir() if p.is_file()},
                fluid_cells=6*n**3, solid_cells=6*n**3+3, config=config))
            for ranks in args.ranks:
                group = f'n{n}-r{ranks}'
                partition = work/(group+'-partition')
                run([binaries['baseline'], '-case', case, '-prepare', partition, '-parts', ranks], group+'-prepare')
                reference_fields = reference_history = reference_iterations = None
                for repeat in range(-1, args.repeats):
                    pair = {}
                    for mode in (('baseline', 'candidate') if repeat % 2 else ('candidate', 'baseline')):
                        label = group+f'-sample{repeat}-{mode}'
                        output = work/(label+'.vtu')
                        command = [args.mpiexec, *binding, '-n', ranks, binaries[mode], '-case', case,
                                   '-partition', partition, '-output', output, '-solver_report', '-linear_report',
                                   '-ksp_type', 'preonly', '-pc_type', 'lu', '-pc_factor_mat_solver_type', 'superlu_dist']
                        if args.petsc_log:
                            command += ['-log_view', ':'+str(work/(label+'-petsc.log'))]
                        reported = mode == 'candidate' or args.baseline_assembly_report
                        if reported:
                            command.append('-fsi_assembly_report')
                        command.extend(options[mode])
                        threads = settings[mode]['fsi_threads']
                        elapsed, text = run(command, label, threads=threads)
                        row = dict(subdivisions=n, ranks=ranks, repeat=repeat, mode=mode,
                                   element_threads_per_rank=threads, execution_options=options[mode],
                                   wall_seconds=elapsed, log=label+'.log', **parse_log(text, args.steps, ranks, dt))
                        if reported:
                            check_plan(row['plan'], settings[mode]['fsi_coo'], 12*n**3+3)
                            for key in INITIALIZATION_TIMERS:
                                row['initialization_'+key] = number(row['plan'][0], key, 0)
                        else:
                            require(not row['plan'], 'Baseline unexpectedly enabled assembly setup reporting')
                        check_execution(row, settings[mode], reported)
                        saved = [physical_fields(output.with_stem(output.stem+f'_step{step}'), ranks)
                                 for step in range(1, args.steps+1)]
                        final = physical_fields(output, ranks)
                        final_delta = compare_fields(saved[-1], final)
                        accepted_history = history(output.with_suffix('.csv'), args.steps, dt)
                        iterations = [(s['snes_iterations'], s['linear_iterations']) for s in row['steps']]
                        if reference_fields is None:
                            reference_fields, reference_history, reference_iterations = saved, accepted_history, iterations
                        row['field_max_delta'] = max(final_delta, *(compare_fields(x, y) for x, y in zip(reference_fields, saved)))
                        row['history_max_delta'] = compare_history(reference_history, accepted_history)
                        require(iterations == reference_iterations, ('Newton/Krylov trajectory changed', label, iterations, reference_iterations))
                        row['iteration_trajectory'] = iterations
                        row['saved_states_checked'] = len(saved)+1
                        for key in TIMERS:
                            row[key] = sum(s[key] for s in row['steps'])
                        for key in ('peak_rss_max_bytes', 'peak_rss_sum_bytes'):
                            row[key] = max(s[key] for s in row['steps'])
                        row['files'] = [dict(path=str(p.relative_to(work)), sha256=digest(p), bytes=p.stat().st_size)
                                        for p in sorted(work.glob(label+'*')) if p.is_file()]
                        result['runs'].append(row)
                        pair[mode] = row
                        save()
                    if repeat >= 0:
                        result['pairs'].append(dict(subdivisions=n, ranks=ranks, repeat=repeat,
                            relative_change={key: pair['candidate'][key]/pair['baseline'][key]-1
                                             for key in comparison_metrics if pair['baseline'][key] > 0}))
                    print(group, repeat, 'validated fields, accepted steps and linear residuals', flush=True)
                    save()
        result['summary'] = []
        for n in args.subdivisions:
            for ranks in args.ranks:
                runs = [r for r in result['runs'] if r['subdivisions'] == n and r['ranks'] == ranks and r['repeat'] >= 0]
                pairs = [p for p in result['pairs'] if p['subdivisions'] == n and p['ranks'] == ranks]
                paired_metrics = set.intersection(*(set(p['relative_change']) for p in pairs))
                result['summary'].append(dict(subdivisions=n, ranks=ranks,
                    modes={mode: {key: stats([r[key] for r in runs if r['mode'] == mode]) for key in comparison_metrics}
                           for mode in binaries},
                    paired_relative_change={key: stats([p['relative_change'][key] for p in pairs])
                                            for key in sorted(paired_metrics)}))
        require(all(digest(path) == result['binaries'][mode]['sha256'] for mode, path in binaries.items()),
                'An executable changed during measurement')
        result['status'] = 'passed'
        print(json.dumps(result['summary'], indent=2), flush=True)
    except BaseException as exc:
        result['status'] = 'failed'
        result['error'] = str(exc)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
