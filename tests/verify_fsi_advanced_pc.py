"""Physical FSI acceptance for field AMG, pressure Schur and interface patches.

The default campaign is a bounded 1/2-rank comparison to direct solves, with
generalized-alpha, unequal time steps, moving RCR and restart. --study adds
three mesh levels and a specified density/time-step scan. Every candidate uses
the same physical input and independent field/history/true-residual gates.
Iteration growth is measured, never converted automatically into a claim of
mesh-independent convergence. Raw failures remain in the receipt.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from verify_fsi_inlet import Runner, check_rcr_history, error
from verify_fsi_moving_port import circular_case
import verify_fsi_block_efficiency as block

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import benchmark_fsi_assembly as assembly
from generate_domains import generate

MODES = ('nodal_field', 'lsc_field', 'bfbt_field', 'pcd_field',
         'pcd_vanka_double', 'pcd_vanka_single')
STUDY_MODES = ('aggregate_nodal', 'nodal_field', 'lsc_vanka_single',
               'bfbt_vanka_single', 'pcd_vanka_single')
FIELD_LIMIT = 2e-9


def save(result, path):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def flags(mode, ports=False):
    if mode == 'direct':
        return [*block.flags('direct', 'rcm'), '-linear_report', '-solver_report']
    pressure = 'nodal' if mode == 'aggregate_nodal' else mode.split('_')[0]
    result = ['-pc_recipe', 'hybrid', '-pc_plan_schur_approx', pressure,
              '-pc_plan_velocity_solver', 'aggregate' if mode == 'aggregate_nodal' else 'field_amg',
              '-pc_plan_velocity_coarse_space', 'rigid',
              '-ksp_rtol', '1e-12', '-ksp_atol', '1e-15', '-ksp_max_it', '1500',
              '-ksp_gmres_restart', '100', '-ksp_gmres_modifiedgramschmidt',
              '-ksp_pc_side', 'right', '-ksp_norm_type', 'unpreconditioned',
              '-pc_plan_report', '-linear_report', '-solver_report']
    if 'vanka' in mode:
        result += ['-pc_plan_interface_smoother', 'vanka',
                   '-pc_plan_patch_precision', 'single' if mode.endswith('single') else 'double']
    if ports:
        result += ['-pc_plan_rcr_ports', 'true', '-rcr_port_report']
    return result


class EvidenceRunner(Runner):
    def __init__(self, *args, commands, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = commands

    def command(self, args, label, fail=None):
        block.require(fail is None, 'This campaign has no expected process failures')
        path = self.work / (label + '.log')
        row = dict(label=label, command=list(map(str, args)), log=str(path), status='running')
        self.commands.append(row)
        try:
            text = block.timed_command(args, path, self.timeout, row)
            row['status'] = 'passed'
            return text
        except BaseException as exc:
            row.update(status='failed', error=str(exc))
            raise
        finally:
            if path.is_file():
                row['log_sha256'] = assembly.digest(path)


def compare_history(expected, actual):
    block.require(len(expected) == len(actual), 'History lengths differ')
    worst = 0.
    for first, second in zip(expected, actual):
        block.require(first.keys() == second.keys(), 'History columns differ')
        block.require(first['step'] == second['step'] and
                      math.isclose(first['time'], second['time'], rel_tol=0, abs_tol=1e-13) and
                      math.isclose(first['accepted_dt'], second['accepted_dt'], rel_tol=0, abs_tol=1e-13),
                      'Accepted step/time grid changed')
        for key in first:
            if key != 'snes_iterations':
                worst = max(worst, abs(first[key] - second[key]))
    block.require(worst <= FIELD_LIMIT, ('History physical difference', worst))
    return worst


def audit(log, rows, ranks, mode):
    reports = assembly.records(log, 'solver_report ')
    residuals = assembly.records(log, 'linear_residual ')
    block.require(len(reports) == len(rows) and rows and residuals, 'Incomplete accepted solve evidence')
    block.require(log.count('status=success') == 1 and
                  not any(marker in log for marker in ('linear_residual_unavailable',
                                                       'linear_iteration_limit_residual ', 'step_retry=')),
                  'Incomplete/rejected trajectory or unavailable true residual')
    block.require(sum(int(row['linear_completed']) for row in reports) == len(residuals),
                  'True residual count differs from actual linear corrections')
    for row in reports:
        block.require(int(row['ranks']) == ranks and min(int(row['snes_reason']), int(row['ksp_reason'])) > 0 and
                      int(row['linear_started']) == int(row['linear_completed']), 'Failed or incomplete solve')
        block.require(row['ksp'] == ('preonly' if mode == 'direct' else 'fgmres'), 'Wrong outer Krylov method')
    ratios = []
    for row in residuals:
        norm, rhs = float(row['norm']), float(row['rhs_norm'])
        block.require(math.isfinite(norm) and math.isfinite(rhs) and min(norm, rhs) >= 0.,
                      'Invalid original-Jacobian residual')
        ratios.append(norm / (1e-12 + 1e-10 * rhs))
    block.require(max(ratios) <= 1., ('Original true residual gate failed', max(ratios)))
    result = dict(accepted_steps=len(rows), corrections=len(residuals),
                  dofs=int(reports[-1]['dofs']), max_true_residual_ratio=max(ratios),
                  outer_iterations=sum(int(row['linear_iterations']) for row in reports),
                  newton_iterations=sum(int(row['snes_iterations']) for row in rows),
                  linear_seconds=sum(float(row['linear_seconds']) for row in reports),
                  schur_setup_seconds=sum(float(row['schur_setup_seconds']) for row in reports),
                  peak_rss_max_bytes=max(float(row['peak_rss_max_bytes']) for row in reports))
    result['iterations_per_correction'] = result['outer_iterations'] / result['corrections']
    if mode == 'direct':
        return result
    pressure = mode.split('_')[0]
    if pressure in ('pcd', 'lsc', 'bfbt'):
        operators = assembly.records(log, 'pressure_schur ')
        block.require(operators and all(row['kind'] == pressure and int(row['rows']) > 0 and
                                        int(row['numerical_updates']) > 0 for row in operators),
                      ('Requested pressure Schur was not observed', pressure))
        result['pressure_operators'] = operators
    if mode != 'aggregate_nodal':
        hierarchy = assembly.records(log, 'pc_field_amg ')
        block.require(hierarchy and all(int(row['rigid_modes']) == 1 and int(row['levels']) >= 1 and
                                        int(row['coarse_rows']) > 0 for row in hierarchy),
                      'Requested field-aware hierarchy was not observed')
        level_rows = assembly.records(log, 'pc_field_amg_level ')
        block.require(all(float(row['reproduction_error']) <= 1e-10 and
                          int(row['fine_rows']) > int(row['coarse_rows']) for row in level_rows),
                      'Invalid field hierarchy reproduction/contraction')
        result.update(field_amg=hierarchy, field_amg_transfers=level_rows)
    if 'vanka' in mode:
        patches = assembly.records(log, 'interface_patch_pc ')
        block.require(patches and sum(int(row['patches']) for row in patches) > 0,
                      'No interface patch was actually built')
        block.require({int(row['rank']) for row in patches} == set(range(ranks)),
                      'Missing rank-local interface patch evidence')
        block.require(all(int(row['fp32']) + int(row['fp64']) == int(row['patches']) for row in patches),
                      'Patch factor counts disagree')
        if mode.endswith('double'):
            block.require(all(int(row['fp32']) == 0 for row in patches), 'Double mode constructed FP32 factors')
        result.update(patch_reports=patches, observed_fp32=any(int(row['fp32']) > 0 for row in patches))
    return result


def snapshot(run, label, rows, ranks, restart=None):
    stem = label if restart is None else label + f'_restart{restart}'
    fields = [assembly.physical_fields(run.work / f'{stem}_step{int(row["step"])}.vtu', ranks) for row in rows]
    final = assembly.physical_fields(run.work / f'{label}.vtu', ranks)
    assembly.compare_fields(fields[-1], final)
    return fields


def campaign(args, result, receipt, directory, cfg, modes, ranks, interface_area=1., ports=False,
             restart=False):
    case_record = dict(directory=str(directory), configuration=copy.deepcopy(cfg), ranks=ranks, runs=[])
    result['cases'].append(case_record)
    run = EvidenceRunner(args.executable, args.mpiexec, directory, timeout=args.timeout,
                         interface_area=interface_area, commands=result['commands'])
    input_hashes = {p.name: assembly.digest(p) for p in directory.glob('*.msh')}
    reference = None
    previous_partition = None
    saved_candidate = None
    candidates = [('direct', 'reference', ())] + [(mode, mode, ()) for mode in modes]
    for mode, label, extra in candidates:
        row = dict(mode=mode, label=label, ranks=ranks, status='running')
        case_record['runs'].append(row)
        save(result, receipt)
        try:
            output, trace, log = run.solve(label, cfg, ranks, [*flags(mode, ports), *extra])
            block.require({p.name: assembly.digest(p) for p in directory.glob('*.msh')} == input_hashes,
                          'Physical mesh changed during campaign')
            partition = assembly.partition_evidence(directory / f'part-{ranks}', ranks, directory)
            block.require(previous_partition is None or previous_partition == partition, 'Partition changed')
            previous_partition = partition
            saved = snapshot(run, label, trace, ranks)
            row.update(audit(log, trace, ranks, mode))
            if reference is None:
                block.require(mode == 'direct', 'Direct reference must be first')
                reference = (output, trace, saved)
            row['field_max_difference'] = max(error(reference[0], output),
                *(assembly.compare_fields(first, second) for first, second in zip(reference[2], saved)))
            block.require(row['field_max_difference'] <= FIELD_LIMIT, 'Final physical fields differ')
            row['history_max_difference'] = compare_history(reference[1], trace)
            if ports:
                row['circuit_defect'] = check_rcr_history(run, label, cfg['fsi']['domains']['rcr_outlet'], trace)
            row['artifacts'] = [dict(path=str(p), sha256=assembly.digest(p), bytes=p.stat().st_size)
                                for p in sorted(directory.glob(label + '*')) if p.is_file()]
            row.update(status='passed', partition=partition)
            if mode == modes[-1]:
                saved_candidate = (output, trace, saved)
        except Exception as exc:
            row.update(status='failed', error=str(exc))
            result['failures'].append(dict(directory=str(directory), mode=mode, error=str(exc)))
        save(result, receipt)
        print('advanced_fsi_run', json.dumps({key: row[key] for key in
              ('mode', 'ranks', 'status', 'dofs', 'outer_iterations', 'linear_seconds',
               'max_true_residual_ratio', 'field_max_difference', 'error') if key in row}), flush=True)
        if row['status'] != 'passed' and mode == 'direct':
            return
    if restart and saved_candidate is not None:
        mode = modes[-1]
        checkpoint = directory / 'checkpoint'
        restart_row = dict(mode=mode, label='restart', ranks=ranks, status='running')
        case_record['runs'].append(restart_row)
        try:
            _, first, first_log = run.solve('checkpoint', cfg, ranks,
                                           [*flags(mode, ports), '-checkpoint', checkpoint, '-stop_after', 1])
            restart_row['start'] = audit(first_log, first, ranks, mode)
            resumed, tail, log = run.solve('resumed', cfg, ranks,
                                          [*flags(mode, ports), '-restart', checkpoint])
            block.require(len(tail) == len(saved_candidate[1]) - 1, 'Incomplete restart tail')
            restart_row.update(audit(log, tail, ranks, mode))
            restart_row['field_max_difference'] = error(saved_candidate[0], resumed)
            block.require(restart_row['field_max_difference'] <= FIELD_LIMIT, 'Restart physical fields differ')
            restart_row['history_max_difference'] = compare_history(saved_candidate[1][1:], tail)
            restarted = snapshot(run, 'resumed', tail, ranks, restart=1)
            restart_row['saved_field_max_difference'] = max(
                assembly.compare_fields(first, second) for first, second in zip(saved_candidate[2][1:], restarted))
            if ports:
                restart_row['circuit_defect'] = check_rcr_history(run, 'resumed', cfg['fsi']['domains']['rcr_outlet'],
                                                                tail, restart=1)
            restart_row['status'] = 'passed'
        except Exception as exc:
            restart_row.update(status='failed', error=str(exc))
            result['failures'].append(dict(directory=str(directory), mode='restart', error=str(exc)))
        save(result, receipt)


def domain_case(directory, n, density_ratio=1., dt=.02, unequal=False):
    cfg = json.loads(generate(directory, n).read_text())
    cfg['fsi'].update(steps=3, dt=dt, output_interval=1, density=1., solid_density=density_ratio)
    cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
    if unequal:
        cfg['time_control'] = dict(step_sizes=[dt, .75 * dt, 1.25 * dt])
        cfg['fsi']['dt'] = math.fsum(cfg['time_control']['step_sizes']) / 3
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--build-source', help='Exact commit used to compile the binary; absence is recorded')
    parser.add_argument('--study', action='store_true')
    parser.add_argument('--sections', nargs='+', choices=('default', 'scaling', 'coupling', 'rcr'),
                        help='Run only these sections; omitted runs default+rcr, --study also adds scaling+coupling')
    parser.add_argument('--timeout', type=float, default=180.)
    args = parser.parse_args()
    if args.build_source and not re.fullmatch('[0-9a-f]{40}', args.build_source):
        parser.error('--build-source must be a full commit SHA')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')
    if args.sections and (args.study or len(set(args.sections)) != len(args.sections)):
        parser.error('--sections must be unique and cannot be combined with --study')
    sections = set(args.sections or (['default', 'rcr', 'scaling', 'coupling'] if args.study else ['default', 'rcr']))
    args.executable, args.mpiexec = args.executable.resolve(), args.mpiexec.resolve()
    work = args.work.resolve() / str(time.time_ns())
    work.mkdir(parents=True)
    receipt = work / 'results.json'
    environment = dict(OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    os.environ.update(environment)
    result = dict(status='running', build_source=args.build_source,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  executable=str(args.executable), executable_sha256=assembly.digest(args.executable),
                  driver_sha256=assembly.digest(__file__), environment=environment,
                  helper_sha256={str(p.relative_to(ROOT)): assembly.digest(p) for p in
                                 (ROOT / 'tests/verify_fsi_inlet.py', ROOT / 'tests/verify_fsi_moving_port.py',
                                  ROOT / 'tests/verify_fsi_block_efficiency.py', ROOT / 'scripts/benchmark_fsi_assembly.py',
                                  ROOT / 'cases/fsi/generate_domains.py')},
                  linear_gate='1e-12 + 1e-10 * rhs_norm', field_absolute_limit=FIELD_LIMIT,
                  study=bool(sections & {'scaling', 'coupling'}), sections=sorted(sections),
                  commands=[], cases=[], failures=[])
    save(result, receipt)
    if 'default' in sections:
        for ranks in (1, 2):
            directory = work / f'domains-r{ranks}'
            cfg = domain_case(directory, 3, unequal=True)
            campaign(args, result, receipt, directory, cfg, MODES, ranks, restart=ranks == 2)
    if 'rcr' in sections:
        directory = work / 'moving-rcr'
        cfg, geometry = circular_case(directory, (1., 0., 0.), (0., 0., 0.))
        cfg['fsi'].update(steps=3, output_interval=1, pressure_face_history=True)
        cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
        cfg['time_control'] = dict(step_sizes=[.015, .013, .017])
        cfg['fsi']['dt'] = math.fsum(cfg['time_control']['step_sizes']) / 3
        campaign(args, result, receipt, directory, cfg, ('pcd_vanka_single',), 2,
                 interface_area=geometry['interface_area'], ports=True, restart=True)
    if 'scaling' in sections:
        for ranks in (1, 2):
            for n in (4, 6, 8):
                directory = work / f'scaling-n{n}-r{ranks}'
                campaign(args, result, receipt, directory, domain_case(directory, n), STUDY_MODES, ranks)
    if 'coupling' in sections:
        for ratio in (1., .1, .01):
            for dt in (.02, .005):
                directory = work / f'coupling-rho{ratio:g}-dt{dt:g}'
                cfg = domain_case(directory, 4, ratio, dt)
                campaign(args, result, receipt, directory, cfg,
                         ('bfbt_field', 'bfbt_vanka_single', 'pcd_vanka_single'), 2)
    if 'scaling' in sections:
        scaling = []
        for ranks in (1, 2):
            for mode in STUDY_MODES:
                rows = [next((r for r in case['runs'] if r['mode'] == mode and r['status'] == 'passed'), None)
                        for case in result['cases'] if re.search(fr'scaling-n[468]-r{ranks}$', case['directory'])]
                if len(rows) == 3 and all(row is not None for row in rows):
                    first, last = rows[0], rows[-1]
                    growth = last['iterations_per_correction'] / first['iterations_per_correction']
                    scaling.append(dict(ranks=ranks, mode=mode, dofs=[r['dofs'] for r in rows],
                                        mean_iterations=[r['iterations_per_correction'] for r in rows],
                                        finest_coarsest_iteration_ratio=growth,
                                        observation='bounded_three_mesh_evidence_only'))
        result['mesh_scaling'] = scaling
    result['status'] = 'failed' if result['failures'] else 'passed'
    save(result, receipt)
    print('advanced_fsi_receipt', receipt, result['status'], flush=True)
    if result['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
