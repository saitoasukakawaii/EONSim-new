"""Bounded coupled FSI mesh-refinement study with unchanged physical gates.

The independent-domain generator supplies n=4/6/8 refinements. Every solver uses
the same mesh, partition, five-step trajectory and field scales. A direct solve
is checked before coupled, twolevel and aggregate responses are compared. The
existing assembly benchmark owns the saved-field, accepted-history and original
linear-residual gates; solver presets come from the arterial block study.

By default only correctness is run. With --timing-repeats >= 3 the initial runs
are unmeasured warmups and passing iterative modes receive interleaved samples.
Timing has no pass threshold. Each command has a process-group watchdog; failed
or timed-out modes remain failed evidence and receive no performance samples.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import benchmark_fsi_assembly as assembly

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import verify_fsi_block_efficiency as block

MODES = ('coupled_nodal', 'twolevel_rigid', 'aggregate_rigid',
         'aggregate_rigid_adaptive')
PC_COUNTERS = ('pc_refreshes', 'pc_reuses', 'pc_drift_refreshes',
               'pc_age_refreshes', 'pc_iteration_refreshes', 'pc_context_refreshes',
               'pc_rebuild_retries')


def hierarchy(text, mode, ranks, steps):
    """Inspect observed operators; sizes and levels are never inferred from n."""
    expected = {prefix: (ksp, pc) for prefix, ksp, pc in block.expected_solvers(mode)}
    observed, completed = None, 0
    for line in text.splitlines():
        if line.startswith('solver_report '):
            assembly.require(observed is None, 'Nested solver-report interval')
            observed = {prefix: [0] * ranks for prefix in expected}
        elif line.startswith('solver_node '):
            node = assembly.records(line, 'solver_node ')[0]
            prefix = node['prefix']
            if prefix not in expected:
                continue
            rank = assembly.number(node, 'rank', 0, True)
            assembly.require(observed is not None and rank < ranks, 'Response outside accepted-step interval')
            assembly.require((node['ksp'], node['pc']) == expected[prefix],
                             ('Requested response differs', mode, prefix, rank))
            reason = assembly.number(node, 'ksp_reason', integer=True)
            assembly.require(assembly.number(node, 'pc_reason', integer=True) == 0 and
                             (reason > 0 or (node['ksp'] != 'preonly' and reason == -3)),
                             ('Response solve failed', node))
            assembly.number(node, 'reported_norm', 0)
            observed[prefix][rank] += 1
        elif line.startswith('fsi_step='):
            assembly.require(observed is not None and all(counts == [1] * ranks for counts in observed.values()),
                             ('Requested response was not observed once on every rank/step', mode, observed))
            observed = None
            completed += 1
    assembly.require(completed == steps and observed is None, 'Incomplete response hierarchy trajectory')
    last = assembly.records(text.rsplit('solver_report ', 1)[1], 'solver_node ')
    last = [node for node in last if int(node['rank']) == 0]
    result = dict(last_rank0_operators=last)
    if mode.startswith(('twolevel_', 'aggregate_')):
        basis = assembly.records(text, 'pc_twolevel ')
        assembly.require(basis, ('Missing interpolation evidence', mode))
        dimensions = {int(row['global_modes']) for row in basis}
        assembly.require(len(dimensions) == 1, ('Interpolation dimension changed', dimensions))
        result['first_coarse_dimension'] = dimensions.pop()
        result['aggregate_nodes'] = int(basis[-1]['aggregate_nodes'])
        result['velocity_mg_levels'] = int(basis[-1]['levels'])
        if mode.startswith('aggregate_'):
            prefix = 'fieldsplit_dynamics_fieldsplit_velocity_mg_coarse_'
            coarse = [node for node in last if node['prefix'] == prefix]
            assembly.require(len(coarse) == 1, 'Missing final auxiliary GAMG operator')
            stem = coarse[0]['path'] + '/'
            levels = [node for node in last if node['path'].startswith(stem) and
                      '/' not in node['path'][len(stem):]]
            assembly.require(levels and int(coarse[0]['operator_rows']) ==
                             result['first_coarse_dimension'], 'Inconsistent auxiliary coarse hierarchy')
            result['auxiliary_gamg_levels'] = len(levels)
            result['auxiliary_level_rows'] = [int(node['operator_rows']) for node in levels]
    return result


def solver_kind(mode):
    # The assembly audit verifies the actual outer and velocity response types;
    # hierarchy() additionally checks the aggregate GAMG child on every step.
    return 'direct' if mode == 'direct' else 'hybrid' if mode.startswith('coupled_') else 'twolevel'


def save(result, path):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--build-source', required=True,
                        help='Actual source commit used to build this executable')
    parser.add_argument('--mpiexec', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--subdivisions', type=int, nargs='+', default=[4, 6, 8])
    parser.add_argument('--ranks', type=int, nargs='+', default=[1, 2])
    parser.add_argument('--modes', choices=MODES, nargs='+', default=list(MODES))
    parser.add_argument('--steps', type=int, default=5)
    parser.add_argument('--timing-repeats', type=int, default=0)
    parser.add_argument('--timeout', type=float, default=180.)
    args = parser.parse_args()
    if (args.subdivisions != sorted(set(args.subdivisions)) or
            any(n < 2 for n in args.subdivisions)):
        parser.error('Use ascending unique subdivisions >= 2')
    if args.ranks != sorted(set(args.ranks)) or any(n not in (1, 2, 4) for n in args.ranks):
        parser.error('Use ascending unique ranks from 1, 2, 4')
    if (len(set(args.modes)) != len(args.modes) or args.steps < 1 or
            not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error('Modes must be unique and steps/timeout positive')
    if not re.fullmatch('[0-9a-f]{40}', args.build_source):
        parser.error('--build-source must name the actual full 40-character build commit')
    if args.timing_repeats not in (0,) and args.timing_repeats < 3:
        parser.error('Use zero timing repeats or at least three')
    executable, mpiexec = args.executable.resolve(), args.mpiexec.resolve()
    assembly.require(executable.is_file() and mpiexec.is_file(), 'Missing executable or MPI launcher')
    environment = dict(OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', OPENBLAS_NUM_THREADS='1',
                       MKL_NUM_THREADS='1', OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    os.environ.update(environment)
    work = args.work.resolve() / str(time.time_ns())
    work.mkdir(parents=True)
    receipt = work / 'results.json'
    result = dict(status='running', output_directory=str(work), build_source=args.build_source,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                        text=True).strip(),
                  executable=str(executable), executable_sha256=assembly.digest(executable),
                  script_sha256=assembly.digest(__file__),
                  helper_sha256={str(path.relative_to(ROOT)): assembly.digest(path) for path in
                                 (ROOT / 'cases/fsi/generate_domains.py',
                                  ROOT / 'scripts/benchmark_fsi_assembly.py',
                                  ROOT / 'tests/verify_fsi_block_efficiency.py')},
                  environment=environment, cpu_affinity=sorted(os.sched_getaffinity(0)),
                  steps=args.steps, timing_repeats=args.timing_repeats,
                  per_command_timeout_seconds=args.timeout, modes=['direct', *args.modes],
                  linear_gate='1e-12 + 1e-10 * rhs_norm',
                  field_absolute_limit=assembly.FIELD_LIMIT, cases=[], failures=[])
    save(result, receipt)

    def run_command(command, log, row):
        row['command'] = list(map(str, command))
        row['log'] = str(log)
        try:
            return block.timed_command(command, log, args.timeout, row)
        finally:
            if log.is_file():
                row['log_sha256'] = assembly.digest(log)

    for n in args.subdivisions:
        case = assembly.generate(work / f'n{n}-input', n)
        config = json.loads(case.read_text())
        config['fsi'].update(steps=args.steps, output_interval=1)
        case.write_text(json.dumps(config, indent=2) + '\n')
        hashes = {path.name: assembly.digest(path) for path in case.parent.iterdir() if path.is_file()}
        for ranks in args.ranks:
            directory = work / f'n{n}-r{ranks}'
            directory.mkdir()
            partition = directory / 'partition'
            record = dict(subdivisions=n, ranks=ranks, input=str(case), config=config,
                          input_sha256=hashes, partition=str(partition), runs=[], medians={})
            result['cases'].append(record)
            preparation = {}
            record['preparation'] = preparation
            try:
                run_command([executable, '-case', case, '-prepare', partition, '-parts', ranks],
                            directory / 'prepare.log', preparation)
                preparation['evidence'] = assembly.partition_evidence(partition, ranks, work)
            except Exception as exc:
                record['status'] = 'failed'
                result['failures'].append(dict(subdivisions=n, ranks=ranks, mode='prepare', error=str(exc)))
                save(result, receipt)
                continue
            reference_fields = reference_history = None

            def run(mode, label, timing):
                nonlocal reference_fields, reference_history
                run_directory = directory / label
                run_directory.mkdir()
                output = run_directory / 'solution.vtu'
                row = dict(mode=mode, label=label, timing_sample=timing, status='running',
                           flags=block.flags(mode, 'rcm'), output=str(output))
                record['runs'].append(row)
                try:
                    assembly.require({path.name: assembly.digest(path) for path in case.parent.iterdir()
                                      if path.is_file()} == hashes, 'Case input changed before a run')
                    assembly.check_partition_unchanged(preparation['evidence'], work)
                    text = run_command([mpiexec, '--map-by', 'core', '--bind-to', 'core',
                                        '-n', ranks, executable, '-case', case, '-partition', partition,
                                        '-output', output, '-solver_report', '-linear_report',
                                        *row['flags']], run_directory / 'solver.log', row)
                    assembly.require({path.name: assembly.digest(path) for path in case.parent.iterdir()
                                      if path.is_file()} == hashes, 'Case input changed during a run')
                    assembly.check_partition_unchanged(preparation['evidence'], work)
                    checked = assembly.parse_log(text, args.steps, ranks, config['fsi']['dt'],
                                                 solver_kind(mode))
                    row.update(checked)
                    row.update(hierarchy(text, mode, ranks, args.steps))
                    fields = [assembly.physical_fields(output.with_stem(output.stem + f'_step{step}'), ranks)
                              for step in range(1, args.steps + 1)]
                    final = assembly.physical_fields(output, ranks)
                    delta = assembly.compare_fields(fields[-1], final)
                    history = assembly.history(output.with_suffix('.csv'), args.steps, config['fsi']['dt'])
                    # Different preconditioners may change Newton work. Keep
                    # every physical/history scalar at the original 2e-9 gate
                    # and record iteration counts separately as measurements.
                    history = [{key: value for key, value in step.items() if key != 'snes_iterations'}
                               for step in history]
                    if mode == 'direct':
                        reference_fields, reference_history = fields, history
                    assembly.require(reference_fields is not None, 'Direct reference has not passed')
                    row['field_max_delta'] = max(delta, *(assembly.compare_fields(x, y)
                        for x, y in zip(reference_fields, fields)))
                    row['history_max_delta'] = assembly.compare_history(reference_history, history)
                    row['dofs'] = int(checked['steps'][0]['dofs'])
                    row['nnz'] = max(step['nnz'] for step in checked['steps'])
                    row['outer_iterations'] = sum(step['linear_iterations'] for step in checked['steps'])
                    row['newton_iterations'] = sum(step['snes_iterations'] for step in checked['steps'])
                    for name in assembly.TIMERS:
                        row[name] = sum(step[name] for step in checked['steps'])
                    for name in ('peak_rss_max_bytes', 'peak_rss_sum_bytes'):
                        row[name] = max(step[name] for step in checked['steps'])
                    if mode.endswith('_adaptive'):
                        for step in checked['steps']:
                            assembly.require(int(step['pc_refreshes']) + int(step['pc_reuses']) ==
                                             step['linear_completed'], 'Unaccounted adaptive correction')
                        for name in PC_COUNTERS:
                            row[name] = sum(int(step[name]) for step in checked['steps'])
                    row['artifacts'] = [dict(path=str(path), sha256=assembly.digest(path),
                                             bytes=path.stat().st_size)
                                        for path in sorted(run_directory.iterdir()) if path.is_file()]
                    row['status'] = 'passed'
                except Exception as exc:
                    row.update(status='failed', error=str(exc))
                    result['failures'].append(dict(subdivisions=n, ranks=ranks, mode=mode,
                                                   label=label, error=str(exc)))
                save(result, receipt)
                print('fsi_block_scaling_run', json.dumps({key: row[key] for key in
                      ('mode', 'label', 'status', 'wall_seconds', 'dofs', 'outer_iterations',
                       'linear_seconds', 'first_coarse_dimension', 'auxiliary_gamg_levels',
                       'pc_refreshes', 'pc_reuses', 'field_max_delta', 'max_linear_residual_ratio',
                       'error') if key in row}, allow_nan=False), flush=True)
                return row

            if run('direct', 'reference-direct', False)['status'] != 'passed':
                record['status'] = 'failed'
                save(result, receipt)
                continue
            passed = [mode for mode in args.modes if run(mode, 'warmup-' + mode, False)['status'] == 'passed']
            failed_timing = set()
            for repeat in range(args.timing_repeats):
                sequence = passed if repeat % 2 == 0 else list(reversed(passed))
                for mode in sequence:
                    if mode not in failed_timing and run(mode, f'timing-{repeat + 1}-{mode}', True)['status'] != 'passed':
                        failed_timing.add(mode)
            for mode in passed:
                samples = [row for row in record['runs'] if row['mode'] == mode and row['timing_sample']]
                if len(samples) == args.timing_repeats and samples and all(row['status'] == 'passed' for row in samples):
                    record['medians'][mode] = dict(samples=len(samples), **{key: assembly.stats(
                        [row[key] for row in samples]) for key in
                        ('wall_seconds', 'outer_iterations', *assembly.TIMERS,
                         'peak_rss_max_bytes', 'peak_rss_sum_bytes')})
            record['status'] = 'passed' if all(row['status'] == 'passed' for row in record['runs']) else 'failed'
            save(result, receipt)
    if assembly.digest(executable) != result['executable_sha256']:
        result['failures'].append(dict(error='Executable changed during study'))
    result['status'] = 'failed' if result['failures'] else 'passed'
    save(result, receipt)
    print('fsi_block_scaling_summary', json.dumps(dict(status=result['status'], results=str(receipt),
                                                     failures=result['failures'])), flush=True)
    return 1 if result['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
