"""FSI execution parity: sparse assembly, threads, solver reuse and accepted state."""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from verify_fsi_inlet import Runner, check_rcr_history
from verify_fsi_moving_port import cap, circular_case, verify_volume_rates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'cases/fsi'))
from generate_domains import generate


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def records(text, marker):
    prefix = marker if marker.endswith('=') else marker + ' '
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(prefix)]


def check_batch_injection(text, mode):
    """Validate one complete injection record despite merged MPI stream prefixes."""
    # A different rank's partial stderr write can precede this flushed stdout
    # record on the same line. Match the complete token sequence, while still
    # counting every marker so duplicate or malformed records cannot disappear.
    marker = 'fsi_batch_failure'
    matches = list(re.finditer(
        r'(?<!\w)fsi_batch_failure mode=(?P<mode>\w+) thread=(?P<thread>\d+) '
        r'team=(?P<team>\d+) batch=(?P<batch>\d+)(?=\s|$)', text))
    require(text.count(marker) == 1 and len(matches) == 1,
            f'{mode}: missing, duplicate or malformed batch injection record')
    fault = matches[0].groupdict()
    team, thread = int(fault['team']), int(fault['thread'])
    require(fault['mode'] == mode and team > 1,
            f'{mode}: missing single injection in an actual multi-thread team')
    require(int(fault['batch']) == 1,
            f'{mode}: fault did not follow a complete first kernel/scatter batch')
    require(0 <= thread < team and (thread > 0 if mode.startswith('worker') else thread == 0),
            f'{mode}: failure came from the wrong OpenMP thread')
    return fault


def owned_fields(path, ranks, elastic):
    """Use the owner copy on each domain's global support; also check its ghosts."""
    result = {}
    for solid in ((False, True) if elastic else (False,)):
        parts, support = [], set()
        for rank in range(ranks):
            suffix = ('_solid' if solid else '')+(f'_rank{rank}' if ranks > 1 else '')+'.vtu'
            tree = ET.parse(path.with_name(path.stem+suffix))
            arrays = {a.attrib['Name']: (int(a.attrib.get('NumberOfComponents', 1)),
                      list(map(float, a.text.split()))) for a in tree.findall('.//PointData/DataArray')}
            xyz = list(map(float, tree.find('.//Points/DataArray').text.split()))
            count = len(xyz)//3
            require(len(xyz) == 3*count and all(map(math.isfinite, xyz)), 'Invalid VTU coordinates')
            require(all(width > 0 and len(values) == width*count and all(map(math.isfinite, values))
                        for width, values in arrays.values()), 'Invalid VTU field values or shape')
            used = set(map(int, tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            require(all(0 <= i < count for i in used), 'Invalid VTU connectivity')
            support.update(int(arrays['mesh_node_id'][1][i]) for i in used)
            arrays['coordinates'] = (3, xyz)
            parts.append(arrays)
        require(support, 'Missing physical domain output')
        owners = set()
        for rank, arrays in enumerate(parts):
            for i, node_id in enumerate(arrays['mesh_node_id'][1]):
                node = int(node_id)
                if node not in support or int(arrays['owner'][1][i]) != rank:
                    continue
                require(node not in owners, 'Duplicate owned physical node')
                owners.add(node)
                for name, (width, values) in arrays.items():
                    if name not in ('owner', 'mesh_node_id', 'algebra_node_id'):
                        result[solid, node, name] = values[width*i:width*(i+1)]
        require(owners == support, 'Physical node has no owner copy')
        for arrays in parts:
            for i, node_id in enumerate(arrays['mesh_node_id'][1]):
                node = int(node_id)
                if node not in support:
                    continue
                for name, (width, values) in arrays.items():
                    if name not in ('owner', 'mesh_node_id', 'algebra_node_id'):
                        require(max(abs(x-y) for x, y in zip(result[solid, node, name],
                                values[width*i:width*(i+1)])) < 2e-9, 'Inconsistent ghost field')
    return result


def compare_fields(expected, actual):
    require(expected and expected.keys() == actual.keys(), 'Missing or changed owned field support')
    maximum = 0.
    for key in expected:
        require(len(expected[key]) == len(actual[key]), 'Changed field tensor shape')
        maximum = max(maximum, *(abs(x-y) for x, y in zip(expected[key], actual[key])))
    require(math.isfinite(maximum) and maximum < 2e-9, f'Owned field discrepancy: {maximum}')
    return maximum


def compare_histories(expected, actual):
    require(expected and len(expected) == len(actual), 'Missing accepted history rows')
    maximum = 0.
    for left, right in zip(expected, actual):
        require(left.keys() == right.keys(), 'Changed history columns')
        for key in left:
            delta = abs(left[key]-right[key])/(1+max(abs(left[key]), abs(right[key])))
            maximum = max(maximum, delta)
    require(math.isfinite(maximum) and maximum < 2e-9, f'Physical history discrepancy: {maximum}')
    return maximum


def solver_trajectory(text):
    reports, steps = records(text, 'solver_report'), records(text, 'fsi_step=')
    require(reports and len(reports) == len(steps), 'Incomplete accepted solver trajectory')
    return [(int(step['snes_iterations']), int(report['linear_iterations']))
            for report, step in zip(reports, steps)]


def matrix_trajectory(text):
    result = []
    for report in records(text, 'solver_report'):
        values = [float(report[key]) for key in ('dofs', 'nnz')]
        require(all(math.isfinite(value) and value > 0 and value.is_integer() for value in values),
                'Invalid matrix size report')
        result.append(tuple(map(int, values)))
    return result


def check_reuse(text, reference):
    """Retries invalidate a session; successful unchanged solves must retain it."""
    result, previous, rejected = [], 0, False
    for line in text.splitlines():
        if line.startswith('step_retry='):
            rejected = True
        if not line.startswith('solver_report '):
            continue
        report = dict(re.findall(r'(\w+)=([^\s]+)', line))
        reused, generation = int(report['solver_reused']), int(report['solver_generation'])
        require(reused in (0, 1) and generation > 0, 'Invalid nonlinear session record')
        if reference or previous == 0 or rejected:
            require(reused == 0 and generation > previous,
                    'A fresh or failed nonlinear session was unexpectedly reused')
            if not rejected:
                require(generation == previous+1, 'Unexpected nonlinear session reconstruction')
        else:
            require(reused == 1 and generation == previous,
                    'A successful unchanged nonlinear session was reconstructed')
        result.append(dict(reused=reused, generation=generation))
        previous, rejected = generation, False
    return result


class AssemblyRunner(Runner):
    """Use the existing command/log lifecycle for both rigid and elastic FSI."""
    def __init__(self, *args, threads=1, overlap=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.threads = threads
        self.overlap = overlap
        self.evidence = []

    def solve(self, label, cfg, ranks=1, coo=False, extra=(), fail=None, reference=None,
              residual_coo=None):
        # The ordinary AIJ comparison isolates all new execution mechanisms.
        # reference=False also permits a threaded AIJ matrix with default Vec COO.
        reference = not coo if reference is None else reference
        threads = 1 if reference else self.threads
        residual_coo = not reference if residual_coo is None else residual_coo
        cfg = copy.deepcopy(cfg)
        output = self.work/(label+'.vtu')
        cfg['output'] = str(output)
        case = self.work/(label+'.json')
        case.write_text(json.dumps(cfg))
        part = self.work/f'part-{ranks}'
        if not part.exists():
            self.command([self.exe, '-case', case, '-prepare', part, '-parts', ranks], label+'-prepare')
        binding = ['--bind-to', 'none'] if self.threads > 1 else []
        command = [self.mpi, *binding, '-n', ranks, self.exe, '-case', case, '-partition', part,
                   '-fsi_assembly_report', '-solver_report']
        if coo:
            command.append('-fsi_coo')
        command.extend(['-fsi_threads', threads])
        if not residual_coo:
            command.extend(['-fsi_residual_coo', 'false'])
        if reference:
            command.extend(['-nonlinear_reuse', 'false'])
        if self.overlap:
            enabled = 'false' if reference else 'true'
            command.extend(['-fsi_overlap', enabled, '-nonlinear_fused_reductions', enabled])
        command.extend(extra)
        text = self.command(command, label, fail)
        evidence = dict(label=label, ranks=ranks, coo=coo, residual_coo=residual_coo,
                        element_threads_per_rank=threads, reference=reference,
                        command=list(map(str, command)), expected_failure=fail, log=label+'.log')
        self.evidence.append(evidence)
        if self.overlap:
            communication = records(text, 'nonlinear_communication')
            if not fail:
                require(communication and all(int(row['overlap']) == int(not reference) and
                        int(row['fused_reductions']) == int(not reference) for row in communication),
                        'Requested overlap/reduction execution path was not used')
            evidence['communication'] = communication
        plans = records(text, 'fsi_assembly_plan')
        require(len(plans) == 1, 'The fixed assembly plan must be reported once on rank zero')
        plan = plans[0]
        require(int(plan['coo']) == int(coo), 'Requested assembly backend was not used')
        require(int(plan['cells']) > 0 and 0 <= int(plan['interface_cells']) <= int(plan['cells']),
                'Invalid assembly cell counts')
        entries, value_bytes = int(plan['coo_entries']), int(plan['coo_value_bytes'])
        require((entries > 0 and value_bytes >= 8*entries) if coo else entries == value_bytes == 0,
                'Invalid COO value buffer report')
        timers = [float(v) for k, v in plan.items() if k.endswith('_seconds')]
        require(timers and all(math.isfinite(v) and v >= 0 for v in timers), 'Invalid assembly setup timing')
        executions = records(text, 'fsi_execution_plan')
        require(len(executions) == 1, 'Missing or duplicated execution plan')
        execution = executions[0]
        require(int(execution['threads_requested']) == threads and
                int(execution['residual_coo']) == int(residual_coo), 'Requested execution path was not used')
        size, largest = (int(execution[key]) for key in ('residual_value_bytes', 'residual_value_bytes_max'))
        require((0 < largest <= size) if residual_coo else size == largest == 0,
                'Invalid residual COO buffer report')
        require(int(execution['batch_cells']) > 1 if threads > 1 else int(execution['batch_cells']) == 1,
                'Unexpected local kernel batch mode')
        compact, fallback = (int(execution[key]) for key in ('aij_block_cells', 'aij_dense_fallback_cells'))
        require(compact == (0 if coo else int(plan['cells'])) and fallback == 0,
                'Expected compact physical-block AIJ insertion for the supported interface aliases')
        evidence['execution_plan'] = execution
        evidence['solver_sessions'] = check_reuse(text, reference)
        if fail:
            require('status=success' not in text and not output.exists()
                    and not list(self.work.glob(label+'_rank*.vtu')), 'Failed solve published physical output')
            return {}, [], text
        require(text.count('status=success') == 1, 'Missing or duplicate success marker')
        reports = records(text, 'solver_report')
        steps = text.count('fsi_step=')
        require(steps > 0 and len(reports) >= steps, 'Missing successful nonlinear solve reports')
        require(all(int(r['snes_reason']) > 0 and int(r['ksp_reason']) > 0 for r in reports),
                'Unconverged solve reported as successful')
        evidence['iteration_trajectory'] = solver_trajectory(text)
        evidence['matrix_trajectory'] = matrix_trajectory(text)
        history = self.work/(label+'.csv')
        if '-restart' in extra:
            prefix = label+'_restart'
            found = [p for p in self.work.glob(prefix+'*.csv') if p.stem[len(prefix):].isdigit()]
            require(len(found) == 1, 'Missing or ambiguous restart history')
            history = found[0]
        with history.open() as stream:
            rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
        require(len(rows) == steps, 'History does not match accepted steps')
        for row in rows:
            require(all(map(math.isfinite, row.values())), 'Nonfinite accepted history')
            require(abs(row['evaluation_body_balance']) < 2e-9 and abs(row['evaluation_power_balance']) < 2e-9,
                    'Accepted force or power balance failed')
            require(min(v for k, v in row.items() if k.endswith('_j')) > 0, 'Accepted invalid geometry')
        elastic = cfg['fsi'].get('body', 'rigid') == 'elastic'
        return owned_fields(output, ranks, elastic), rows, text


def parity(run, cfg, label, ranks=(1, 2), jacobian=False, threaded=True):
    observations, diagnostics = {}, []
    reference = None
    for count in ranks:
        pair = []
        for coo in (False, True):
            name = f'{label}-r{count}-'+('coo' if coo else 'values')
            extra = ['-snes_test_jacobian'] if jacobian and count == 2 else []
            fields, rows, text = run.solve(name, cfg, count, coo, extra)
            iterations, matrices = solver_trajectory(text), matrix_trajectory(text)
            pair.append((fields, rows, iterations, matrices))
            observations[count, coo] = (fields, rows, name)
            if reference is None:
                reference = fields, rows, iterations
            require(iterations == reference[2],
                    f'{name}: Newton/Krylov trajectory changed: {iterations} versus {reference[2]}')
            diagnostics.append(dict(label=name, field_difference=compare_fields(reference[0], fields),
                                    history_difference=compare_histories(reference[1], rows),
                                    iteration_trajectory=iterations, matrix_trajectory=matrices,
                                    solver_sessions=check_reuse(text, not coo)))
            if extra:
                ratios = list(map(float, re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)', text)))
                require(ratios and all(math.isfinite(v) for v in ratios) and max(ratios) < 1e-6,
                        'Full reduced FSI Jacobian differs from independent global finite differences')
                diagnostics[-1]['jacobian_relative_difference'] = max(ratios)
        compare_fields(pair[0][0], pair[1][0])
        require(pair[0][3] == pair[1][3],
                f'{label} r{count}: default AIJ and COO matrix sizes differ: {pair[0][3]} versus {pair[1][3]}')
        if threaded and run.threads > 1 and count == 2:
            name = f'{label}-r{count}-threaded-values'
            fields, rows, text = run.solve(name, cfg, count, reference=False)
            iterations, matrices = solver_trajectory(text), matrix_trajectory(text)
            require(iterations == pair[0][2] and matrices == pair[0][3],
                    'Threaded AIJ changed solver iterations or matrix size')
            diagnostics.append(dict(label=name, field_difference=compare_fields(pair[0][0], fields),
                                    history_difference=compare_histories(pair[0][1], rows),
                                    iteration_trajectory=iterations, matrix_trajectory=matrices,
                                    solver_sessions=check_reuse(text, False)))
    return observations, diagnostics


def batch_failures(run, cfg):
    """Second-batch rank-local faults join workers and drain or discard prior work."""
    attempted = copy.deepcopy(cfg)
    attempted['fsi'].update(steps=1, dt=.008, output_interval=1)
    attempted['time_control'] = dict(step_sizes=[.008], max_retries=2,
                                     minimum_dt=1e-6, reduction=.5)
    replay = copy.deepcopy(attempted)
    replay['fsi']['dt'] = .004
    replay['time_control']['step_sizes'] = [.004]
    stop = ['-stop_after', 1]
    expected, accepted, expected_text = run.solve('batch-replay', replay, 2, False, stop)
    result = []
    previous_timeout = run.timeout
    run.timeout = 60  # A barrier regression must fail promptly, not hang the suite.
    try:
        # Keep four faults, but cover both partial COO buffers and ordinary
        # matrix/vector insertion stashes before a rejected or fatal batch.
        for mode, coo, residual_coo in (('worker', True, True), ('insert', False, False)):
            fields, rows, text = run.solve('batch-'+mode, attempted, 2, coo,
                [*stop, '-verify_fsi_batch_failure', mode], reference=False, residual_coo=residual_coo)
            check_batch_injection(text, mode)
            require(text.count('step_retry=') == 1 and len(rows) == 1
                    and abs(rows[0]['accepted_dt']-.004) < 1e-15,
                    f'{mode}: one injected rejection did not cut back exactly once')
            require(solver_trajectory(text) == solver_trajectory(expected_text),
                    f'{mode}: batch recovery changed accepted-grid solver iterations')
            result.append(dict(mode=mode, coo=coo, residual_coo=residual_coo, batch=1,
                               retries=1, field_difference=compare_fields(expected, fields),
                               history_difference=compare_histories(accepted, rows),
                               iteration_trajectory=solver_trajectory(text)))
        for mode, coo in (('worker_fatal', False), ('insert_fatal', True)):
            _, _, text = run.solve('batch-'+mode, attempted, 2, coo,
                [*stop, '-verify_fsi_batch_failure', mode], reference=False,
                fail='Injected fatal FSI batch failure')
            check_batch_injection(text, mode)
            require('step_retry=' not in text and 'fsi_step=' not in text,
                    f'{mode}: fatal batch failure was retried or published an accepted step')
            result.append(dict(mode=mode, coo=coo, residual_coo=True, batch=1, expected_fatal=True))
    finally:
        run.timeout = previous_timeout
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=1, help='Element threads per rank for optimized execution paths')
    parser.add_argument('--overlap', action='store_true',
                        help='Compare owned/halo overlap and fused reductions against the ordinary reference')
    args = parser.parse_args()
    if not 1 <= args.threads <= 256:
        parser.error('threads must be between 1 and 256')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    runners, report = [], {}

    for body in ('rigid', 'shared-elastic', 'dual-neo'):
        directory = work/body
        cfg = json.loads(generate(directory).read_text())
        if body == 'rigid':
            cfg['fsi'] = dict(body='rigid', mass=2., damping=.3, stiffness=5., pressure=1.)
            cfg['solver'].pop('fields', None)
        elif body == 'shared-elastic':
            cfg['fsi'].pop('domains')
        else:
            cfg['fsi'].update(material='neo_hookean', pressure=2.)
        cfg['fsi'].update(dt=.01, steps=3, output_interval=1, stabilization_tau=.05)
        cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
        cfg['time_control'] = dict(step_sizes=[.008, .012, .01])
        run = AssemblyRunner(args.executable, args.mpiexec, directory, threads=args.threads, overlap=args.overlap)
        runners.append(run)
        observations, report[body] = parity(run, cfg, body)
        if body == 'rigid':
            expected = owned_fields(directory/'rigid-r2-values_step1.vtu', 2, False)
            for coo in (False, True):
                fields, rows, _ = run.solve('rigid-fd' if coo else 'rigid-fd-values', cfg, 2, coo,
                                            ['-fsi_fd_tangent', '-stop_after', 1])
                report['finite-difference-reference' if coo else 'finite-difference-default'] = dict(
                    field_difference=compare_fields(expected, fields),
                    history_difference=compare_histories(observations[2, False][1][:1], rows))
            if run.threads > 1:
                # 162 fluid tetrahedra give both ranks more than one 64-cell
                # batch; the original n=2 rigid fixture cannot exercise reuse
                # of the team or partially assembled preceding batches.
                failure_directory = work/'batch-failures'
                generate(failure_directory, n=3)
                failure_run = AssemblyRunner(args.executable, args.mpiexec, failure_directory,
                                             threads=args.threads, overlap=args.overlap)
                runners.append(failure_run)
                report['batch-failures'] = batch_failures(failure_run, cfg)

    directory = work/'moving-port'
    cfg, geometry = circular_case(directory, (1., 0., 0.), (0., 0., 0.))
    cfg['fsi'].update(steps=3, output_interval=1)
    cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
    cfg['time_control'] = dict(step_sizes=[.015, .013, .017])
    run = AssemblyRunner(args.executable, args.mpiexec, directory, threads=args.threads, overlap=args.overlap,
                         interface_area=geometry['interface_area'])
    runners.append(run)
    observations, report['moving-port'] = parity(run, cfg, 'moving', jacobian=True)
    model = cfg['fsi']['domains']['rcr_outlet']
    for count, coo in observations:
        fields, rows, name = observations[count, coo]
        check_rcr_history(run, name, model, rows)
        area, flow, original_area, _ = cap(directory, fields, model['tag'], (1., 0., 0.))
        require(abs(area/original_area-1) > 1e-6 and abs(flow-rows[-1]['endpoint_rcr_flow']) < 2e-12,
                'Moving outlet or independently reconstructed current flux was not exercised')
        verify_volume_rates(rows[0]['endpoint_volume'], rows[1:])

    # Checkpoint state is independent of sparse assembly representation, in both directions.
    report['restart'] = []
    for source_coo in (False, True):
        label = 'restart-from-'+('coo' if source_coo else 'values')
        checkpoint = directory/(label+'-checkpoint')
        run.solve(label+'-seed', cfg, 2, source_coo, ['-checkpoint', checkpoint, '-stop_after', 1])
        fields, tail, text = run.solve(label, cfg, 2, not source_coo, ['-restart', checkpoint])
        reference, rows, reference_name = observations[2, False]
        iterations = solver_trajectory(text)
        require(iterations == solver_trajectory((directory/(reference_name+'.log')).read_text())[1:],
                'Cross-backend restart changed Newton/Krylov iterations')
        report['restart'].append(dict(source_coo=source_coo, field_difference=compare_fields(reference, fields),
                                     history_difference=compare_histories(rows[1:], tail),
                                     iteration_trajectory=iterations))
        check_rcr_history(run, label, model, tail, restart=1)

    # Keep the same geometry but restore the fixed-port constraints and coupling path.
    fixed = copy.deepcopy(cfg)
    domains = fixed['fsi']['domains']
    del domains['rcr_outlet']['moving_plane_axis']
    for key, tag in [('mesh_constraints', model['tag']), ('solid_constraints', 12)]:
        next(c for c in domains[key] if c['tag'] == tag)['components'] = [0, 1, 2]
    fixed_observations, report['fixed-port'] = parity(run, fixed, 'fixed', ranks=(2,), threaded=False)
    for fields, rows, name in fixed_observations.values():
        check_rcr_history(run, name, domains['rcr_outlet'], rows)

    # A real nonlinear cutback must reset the COO buffer and all time/circuit histories.
    retried = copy.deepcopy(cfg)
    retried['fsi'].update(dt=.10)
    retried['fsi']['inlet']['flow_rate'].update(mean=.12, amplitude=.03)
    retried['time_control'] = dict(step_sizes=[.004, .004, .10])
    checkpoint = directory/'retry-checkpoint'
    _, seed, _ = run.solve('retry-seed', retried, 2, True, ['-checkpoint', checkpoint, '-stop_after', 2])
    retried['time_control'].update(max_retries=18, minimum_dt=1e-10, reduction=.5)
    fields, rows, text = run.solve('retry-coo', retried, 2, True,
                                 ['-restart', checkpoint, '-snes_max_it', 3, '-stop_after', 3])
    require(len(rows) == 1 and 'step_retry=' in text and rows[0]['accepted_dt'] < .10,
            'Expected a real rejected nonlinear step before COO recovery')
    verify_volume_rates(seed[-1]['endpoint_volume'], rows)
    check_rcr_history(run, 'retry-coo', model, rows, restart=2)
    retried['time_control']['step_sizes'] = [.004, .004, rows[0]['accepted_dt']]
    replay, trajectory, replay_text = run.solve('retry-values-replay', retried, 2, False, ['-stop_after', 3])
    require(solver_trajectory(text) == solver_trajectory(replay_text)[-1:],
            'Recovered retry changed Newton/Krylov iterations relative to accepted-grid replay')
    report['retry'] = dict(retries=text.count('step_retry='), accepted_dt=rows[0]['accepted_dt'],
                           field_difference=compare_fields(replay, fields),
                           history_difference=compare_histories(trajectory[-1:], rows),
                           iteration_trajectory=solver_trajectory(text))

    # A failed solve cannot publish a partial field or replace its accepted checkpoint.
    digest = lambda: {str(p.relative_to(checkpoint)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in checkpoint.rglob('*') if p.is_file()}
    before = digest()
    failed = copy.deepcopy(cfg)
    failed['fsi']['dt'] = .10
    failed['fsi']['inlet']['flow_rate'].update(mean=.12, amplitude=.03)
    failed['time_control'] = dict(step_sizes=[.004, .004, .10])
    run.solve('failed-coo', failed, 2, True,
              ['-restart', checkpoint, '-checkpoint', checkpoint, '-snes_max_it', 0], fail='retries exhausted')
    require(before and digest() == before, 'Failed COO solve changed the accepted checkpoint')

    for option in (['-fsi_coo'], ['-fsi_threads', 1], ['-fsi_residual_coo', 'false']):
        run.command([run.exe, '-case', ROOT/'cases/fluid/stokes.yaml', *option],
                    'unsupported-fluid-'+option[0][1:], fail='require the monolithic FSI problem')

    report['element_threads_per_rank'] = args.threads
    report['overlap_comparison'] = args.overlap
    report['commands'] = [entry for runner in runners for entry in runner.evidence]
    report['executable_sha256'] = hashlib.sha256(Path(args.executable).read_bytes()).hexdigest()
    (work/'results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'PASS: FSI sparse assembly, {args.threads} threads, solver reuse, MPI, ports, Jacobian, restart and cutback; '
          f'{len(report["commands"])} solves')


if __name__ == '__main__':
    main()
