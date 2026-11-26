"""Bounded physical validation of monolithic MG, pressure enhancements and exact Jv.

Every mode solves the same physical equations and is compared to an independent
direct trajectory, saved fields, histories and original-operator residuals.
Optional scaling/coupling sections measure behavior without assuming a speedup
or mesh-independent convergence. Each failure and original log is retained.
"""
import argparse
from collections import Counter
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import time

import verify_fsi_advanced_pc as previous
import verify_fsi_block_efficiency as block
from verify_fsi_inlet import error, check_rcr_history
from verify_fsi_moving_port import circular_case

assembly = previous.assembly
ROOT = Path(__file__).resolve().parents[1]
FEATURES = {
    'mono_scaled': {'scaling'}, 'mono_candidates': {'candidates'},
    'mono_adaptive': {'adaptive'}, 'mono_native_fp32': {'native'},
    'mono_optimized': {'scaling', 'candidates', 'adaptive', 'native'},
    'mono_kcycle': {'scaling', 'candidates', 'adaptive', 'native', 'kcycle'},
    'mono_reduced': {'mf', 'reduced'}, 'mono_reduced_coo': {'mf', 'reduced', 'coo'},
    'mono_partial': {'mf', 'partial'},
    'mono_simd': {'mf', 'partial', 'simd'}, 'mono_overlap': {'mf', 'overlap'},
    'mono_inexact': {'mf', 'inexact'}, 'mono_recycle': {'mf', 'recycle'},
    'mono_all': {'scaling', 'candidates', 'adaptive', 'native', 'mf', 'reduced',
                 'partial', 'simd', 'overlap', 'inexact', 'recycle', 'kcycle'},
}
MODES = ('mono', 'mono_fp32', 'mono_pipe', 'mono_mf', 'mono_mf_pipe', 'mono_chebyshev',
         'mono_block_chebyshev', 'added_mass', 'pcd_mass', 'pcd_robin', *FEATURES)
SCALING_SUBDIVISIONS = (4, 6, 8)
MESH_ITERATION_RATIO_LIMIT = 1.3


def features(mode):
    return FEATURES.get(mode, {'mf'} if mode in ('mono_mf', 'mono_mf_pipe') else set())


def flags(mode, ports=False):
    if mode == 'direct':
        return [*block.flags('direct', 'rcm'), '-linear_report', '-solver_report']
    pipelined = mode in ('mono_pipe', 'mono_mf_pipe')
    result = ['-ksp_type', 'pipefgmres' if pipelined else 'fgmres',
              '-ksp_pc_side', 'right', '-ksp_norm_type', 'unpreconditioned',
              '-ksp_rtol', '1e-12', '-ksp_atol', '1e-15', '-ksp_max_it', '1500',
              '-ksp_gmres_restart', '100', '-linear_report', '-solver_report', '-pc_plan_report']
    if not pipelined:
        result += ['-ksp_gmres_modifiedgramschmidt']
    if ports:
        result += ['-pc_plan_rcr_ports', 'true', '-rcr_port_report']
    selected = features(mode)
    if mode.startswith('mono'):
        prefix = '-rcr_bulk_monolithic_mg_' if ports else '-monolithic_mg_'
        result += ['-pc_recipe', 'monolithic_mg', prefix + 'coarse_limit', '48',
                   prefix + 'coarse_processes', '1']
        if mode == 'mono_fp32':
            result += [prefix + 'single_precision', 'true']
        if 'kcycle' in selected:
            result += [prefix + 'cycle', 'k']
        elif mode == 'mono_optimized':
            result += [prefix + 'cycle', 'v']
        if 'mf' in selected:
            result += ['-fsi_matrix_free', '-nonlinear_matrix_free_pc_interval', '2']
        for feature, option in (('scaling', 'field_scaling'), ('candidates', 'fsi_candidates'),
                                ('adaptive', 'adaptive_patches'), ('native', 'native_fp32')):
            if feature in selected:
                result += [prefix + option, 'true']
        if 'adaptive' in selected:
            result += [prefix + 'patch_strength', '0.25']
        for feature, option in (('reduced', '-fsi_reduced_pc'), ('partial', '-fsi_partial_assembly'),
                                ('simd', '-fsi_matrix_free_simd'), ('overlap', '-fsi_matrix_free_overlap'),
                                ('inexact', '-nonlinear_inexact_newton')):
            if feature in selected:
                result += [option, 'true']
        if 'recycle' in selected:
            result += ['-nonlinear_krylov_recycle', '4']
        if selected & {'reduced', 'partial', 'simd', 'overlap'}:
            result += ['-fsi_assembly_report']
        if 'coo' in selected:
            result += ['-fsi_coo', 'true']
        if mode in ('mono_chebyshev', 'mono_block_chebyshev'):
            result += [prefix + 'smoother', mode.removeprefix('mono_')]
    else:
        result += ['-pc_recipe', 'hybrid', '-pc_plan_velocity_solver', 'field_amg',
                   '-pc_plan_velocity_coarse_space', 'rigid', '-pc_plan_schur_approx',
                   'added_mass' if mode == 'added_mass' else 'pcd']
        if mode.startswith('pcd'):
            result += ['-pc_plan_pcd_velocity_mass', 'true']
            if mode == 'pcd_robin':
                result += ['-pc_plan_pcd_robin', 'true']
    return result


def kcycle_evidence(log, hierarchy, ranks):
    """Keep cumulative PC work snapshots, with no sum across accepted solves."""
    block.require(hierarchy and all(row.get('cycle') == 'k' for row in hierarchy),
                  'Requested K-cycle is absent from the hierarchy')
    counts = ('applications', 'level_matvecs', 'zero_start_skips', 'coarse_revisits',
              'coarse_solves', 'coarse_iterations', 'smoother_applications',
              'coarse_krylov_directions', 'coarse_krylov_rank_drops',
              'coarse_krylov_rejections', 'coarse_krylov_reductions')
    snapshots, groups, last = [], [], {}
    generation, solve_index = None, 0
    for line in log.splitlines():
        if line.startswith('solver_report '):
            report = assembly.records(line, 'solver_report ')[0]
            block.require('solver_generation' in report, 'Missing solver generation for cumulative K-cycle work')
            generation = int(report['solver_generation'])
            solve_index += 1
            groups.append([])
        elif line.startswith('monolithic_mg_stats '):
            row = assembly.records(line, 'monolithic_mg_stats ')[0]
            block.require(generation is not None and all(key in row for key in
                          ('rank', 'path', 'cycle', 'coarse_krylov_max_residual_ratio', *counts)),
                          'Missing cumulative K-cycle work evidence')
            block.require(row['cycle'] == 'k' and row['path'] and 0 <= int(row['rank']) < ranks and
                          all(int(row[key]) >= 0 for key in counts), 'Invalid cumulative K-cycle work counters')
            residual_ratio = float(row['coarse_krylov_max_residual_ratio'])
            block.require(math.isfinite(residual_ratio) and 0 <= residual_ratio <= 1,
                          'Invalid coarse Krylov residual ratio')
            snapshot = dict(row, solver_generation=generation, accepted_solve=solve_index)
            key = int(row['rank']), row['path'], generation
            if key in last:
                block.require(all(int(row[name]) >= int(last[key][name]) for name in counts),
                              'Cumulative K-cycle work decreased within one solver generation')
            snapshots.append(snapshot)
            groups[-1].append(snapshot)
            last[key] = snapshot
    block.require(groups and all(group for group in groups), 'Missing accepted-solve K-cycle work snapshots')
    for group in groups:
        paths = {row['path'] for row in group}
        block.require(Counter((int(row['rank']), row['path']) for row in group) ==
                      Counter((rank, path) for rank in range(ranks) for path in paths),
                      'Missing or duplicate rank/path K-cycle work snapshots')
    for key in ('applications', 'level_matvecs', 'coarse_solves', 'smoother_applications',
                'coarse_krylov_directions', 'coarse_krylov_reductions'):
        block.require(any(int(row[key]) > 0 for row in snapshots),
                      ('Requested K-cycle did not execute coarse directions/work', key))
    return dict(snapshots=snapshots, last_by_rank_path_generation=list(last.values()),
                counter_semantics='Cumulative per hierarchy lifetime, preserved across numeric refreshes; '
                                  'snapshots are not summed; RCR response applies are included')


def mesh_convergence_goal(cases, modes):
    """Assess the declared finite window without changing physical acceptance."""
    result = dict(subdivisions=list(SCALING_SUBDIVISIONS), ranks=2,
                  metric='maximum/minimum average outer iterations per Newton correction',
                  maximum_ratio=MESH_ITERATION_RATIO_LIMIT,
                  scope='Finite n=4/6/8 window with unchanged strict linear and physical gates',
                  physical_acceptance_independent=True, modes={})
    for mode in modes:
        assessment = dict(status='incomplete', observations=[])
        result['modes'][mode] = assessment
        for n in SCALING_SUBDIVISIONS:
            matches = [row for case in cases if case['name'] == f'scaling-n{n}-r2' and case['ranks'] == 2
                       for row in case['runs'] if row['mode'] == mode]
            if len(matches) != 1 or matches[0]['status'] != 'passed':
                continue
            row = matches[0]
            average = float(row['iterations_per_correction'])
            if not math.isfinite(average) or average <= 0:
                continue
            assessment['observations'].append(dict(subdivisions=n, dofs=row['dofs'],
                                                   iterations_per_correction=average))
        if 'inexact' in features(mode):
            assessment.update(status='not_applicable_inexact',
                              reason='Varying forcing tolerances cannot establish the strict linear convergence goal')
        elif len(assessment['observations']) == len(SCALING_SUBDIVISIONS):
            values = [row['iterations_per_correction'] for row in assessment['observations']]
            ratio = max(values) / min(values)
            assessment.update(observed_ratio=ratio, status='met' if ratio <= MESH_ITERATION_RATIO_LIMIT else 'open')
    return result


def audit(log, trace, ranks, mode):
    selected = features(mode)
    reports = assembly.records(log, 'solver_report ')
    residuals = assembly.records(log, 'linear_residual ')
    block.require(reports and len(reports) == len(trace) and residuals, 'Incomplete physical solve evidence')
    block.require(log.count('status=success') == 1 and not any(token in log for token in
                  ('linear_residual_unavailable', 'linear_iteration_limit_residual ', 'step_retry=')),
                  'Failed or partially observed physical trajectory')
    block.require(sum(int(row['linear_completed']) for row in reports) == len(residuals),
                  'Unobserved linear correction')
    expected = 'preonly' if mode == 'direct' else 'pipefgmres' if mode in ('mono_pipe', 'mono_mf_pipe') else 'fgmres'
    for row in reports:
        block.require(int(row['ranks']) == ranks and row['ksp'] == expected and
                      min(int(row['snes_reason']), int(row['ksp_reason'])) > 0 and
                      int(row['linear_started']) == int(row['linear_completed']), 'Invalid solver result')
    # Final physical acceptance is independent of the forcing tolerance used
    # for intermediate inexact Newton corrections.
    fields = assembly.records(log, 'field_residual ')
    names = {row['name'] for row in fields}
    block.require({'velocity', 'pressure', 'mesh', 'structure'} <= names and
                  len(fields) == len(names) * len(trace) and
                  Counter(row['name'] for row in fields) == Counter({name: len(trace) for name in names}),
                  'Missing or duplicate final physical field acceptance')
    for row in fields:
        block.require(int(row['accepted']) == 1 and 0 <= float(row['rms']) <= float(row['limit']) and
                      0 <= float(row['constraint_max']) <= float(row['constraint_limit']),
                      'Final physical field or constraint rejected')
    ratios = []
    for row in residuals:
        norm, rhs = float(row['norm']), float(row['rhs_norm'])
        block.require(math.isfinite(norm) and math.isfinite(rhs) and min(norm, rhs) >= 0, 'Nonfinite true residual')
        target = 1e-12 + 1e-10 * rhs
        if 'inexact' in selected:
            relative, absolute = float(row['requested_rtol']), float(row['requested_atol'])
            block.require(int(row['forcing']) == 1 and math.isfinite(relative + absolute) and
                          0 < relative <= .5 and 0 <= absolute <= 1e-12,
                          'Invalid or missing requested inexact forcing tolerance')
            target = (absolute + relative * rhs) * (1 + 64 * math.ulp(1.))
        ratios.append(norm / target)
    block.require(max(ratios) <= 1, ('Original-operator true-residual gate failed', max(ratios)))
    result = dict(dofs=int(reports[-1]['dofs']), accepted_steps=len(trace), corrections=len(residuals),
                  max_true_residual_ratio=max(ratios),
                  outer_iterations=sum(int(row['linear_iterations']) for row in reports),
                  jacobian_assemblies=sum(int(row['jacobian_assemblies']) for row in reports),
                  jacobian_callbacks=sum(int(row['jacobian_callbacks']) for row in reports),
                  linear_seconds=sum(float(row['linear_seconds']) for row in reports),
                  solve_seconds=sum(float(row['solve_seconds']) for row in reports),
                  assembly_seconds=sum(float(row['assembly_seconds']) for row in reports),
                  peak_rss_max_bytes=max(float(row['peak_rss_max_bytes']) for row in reports))
    result.update(nnz=max(float(row['nnz']) for row in reports), final_fields=fields,
                  linear_gate='requested inexact forcing' if 'inexact' in selected else '1e-12 + 1e-10*rhs_norm')
    result['iterations_per_correction'] = result['outer_iterations'] / result['corrections']
    if mode.startswith('mono'):
        hierarchy = assembly.records(log, 'pc_monolithic_mg ')
        transfers = assembly.records(log, 'pc_monolithic_mg_level ')
        block.require(hierarchy and transfers and all(int(row['levels']) >= 2 for row in hierarchy),
                      'Full-system multilevel path was not exercised')
        for row in transfers:
            block.require(int(row['rows']) > int(row['coarse_rows']) and float(row['reproduction_error']) <= 1e-9,
                          'Coarsening lost physical candidates')
            before, after = float(row['energy_before']), float(row['energy_after'])
            block.require(math.isfinite(before + after) and after <= before * (1 + 1e-10) + 1e-12,
                          'Prolongation increased the defined positive energy')
        block.require(all(int(row['coarse_processes']) == 1 for row in hierarchy), 'Coarse process aggregation absent')
        smoother_kind = mode.removeprefix('mono_') if mode in ('mono_chebyshev', 'mono_block_chebyshev') else 'vanka'
        block.require(all(row['smoother'] == smoother_kind for row in hierarchy), 'Requested level smoother absent')
        smoothers = assembly.records(log, 'pc_monolithic_mg_smoother ')
        levels = max(int(row['levels']) for row in hierarchy)
        block.require(Counter((int(row['rank']), int(row['level'])) for row in smoothers) ==
                      Counter((rank, level) for report in hierarchy for rank in range(ranks)
                              for level in range(int(report['levels']) - 1)),
                      'Missing rank or level smoother evidence')
        for level in range(levels - 1):
            rows = [row for row in smoothers if int(row['level']) == level]
            if smoother_kind == 'vanka':
                block.require(sum(int(row['interface_patches']) for row in rows) > 0,
                              'A multigrid level did not smooth the coupled interface')
            else:
                block.require(all(int(row['polynomial_degree']) > 0 and
                                  math.isfinite(float(row['eigenvalue_upper'])) and
                                  float(row['eigenvalue_upper']) > 0 for row in rows),
                              'Polynomial level smoother absent')
        if mode == 'mono_fp32':
            block.require(all(int(row['single_precision']) == 1 for row in hierarchy), 'FP32 cycle absent')
        for feature, counter in (('scaling', 'field_scaling'), ('candidates', 'fsi_candidates'),
                                 ('native', 'native_fp32')):
            if feature in selected:
                block.require(all(int(row[counter]) == 1 for row in hierarchy),
                              ('Requested MG mechanism absent', feature))
        if 'adaptive' in selected:
            block.require(all(int(row['expanded_patches']) + int(row['core_patches']) == int(row['patches'])
                              for row in smoothers), 'Adaptive patch classification is incomplete')
        if 'native' in selected:
            storage = assembly.records(log, 'pc_monolithic_mg_storage ')
            block.require(storage and {int(row['rank']) for row in storage} == set(range(ranks)) and
                          sum(int(row['released_fp64_operator_bytes']) for row in storage) > 0,
                          'Native FP32 did not release double operator storage')
            result['storage'] = storage
        if 'kcycle' in selected:
            result['kcycle_work'] = kcycle_evidence(log, hierarchy, ranks)
        elif mode == 'mono_optimized':
            block.require(all(row.get('cycle') == 'v' for row in hierarchy), 'V-cycle comparison mode changed')
        result.update(hierarchies=hierarchy, transfers=transfers,
                      smoothers=smoothers)
    if 'mf' in selected:
        block.require(all(int(row['matrix_free']) == 1 and int(row['matrix_free_actions']) > 0 for row in reports),
                      'Exact matrix-free path absent')
        result.update(matrix_free_actions=sum(int(row['matrix_free_actions']) for row in reports),
                      assembled_pc_reuses=sum(int(row['assembled_pc_reuses']) for row in reports))
        block.require(result['assembled_pc_reuses'] > 0, 'Matrix-free trajectory did not reuse assembled P')
    if 'inexact' in selected:
        block.require(sum(int(row['inexact_linear_solves']) for row in reports) == len(residuals),
                      'Inexact correction accounting disagrees with true residuals')
        result['requested_forcing'] = [float(row['requested_rtol']) for row in residuals]
    if 'recycle' in selected:
        block.require(sum(int(row['recycle_projections']) for row in reports) > 0 and
                      max(int(row['recycle_vectors']) for row in reports) > 0,
                      'No correction-subspace projection was used')
        result['recycle_projections'] = sum(int(row['recycle_projections']) for row in reports)
        result['recycle_vectors'] = max(int(row['recycle_vectors']) for row in reports)
    if 'reduced' in selected:
        preconditioners = assembly.records(log, 'fsi_preconditioner ')
        block.require(preconditioners and all(int(row['reduced']) == 1 and
                      int(row['stores_full_jacobian']) == 0 for row in preconditioners),
                      'Reduced preconditioner storage was not selected')
    if selected & {'partial', 'simd', 'overlap'}:
        actions = assembly.records(log, 'fsi_action_report ')
        block.require(actions, 'Missing frozen-action kernel accounting')
        for feature, counter in (('partial', 'partial_assembly'), ('simd', 'simd'), ('overlap', 'overlap')):
            if feature in selected:
                block.require(all(int(row[counter]) == 1 for row in actions),
                              ('Requested action mechanism absent', feature))
        if 'partial' in selected:
            block.require(sum(int(row['prepared_cells']) for row in actions) > 0 and
                          sum(int(row['cached_actions']) for row in actions) > 0 and
                          max(int(row['cache_bytes']) for row in actions) > 0,
                          'Partial assembly did not prepare and reuse qdata')
        if 'simd' in selected:
            block.require(sum(int(row['simd_batches']) for row in actions) > 0, 'No SIMD batches executed')
        if 'overlap' in selected:
            block.require(sum(int(row['owned_cells']) for row in actions) > 0,
                          'No owned-cell Jv work overlapped communication')
        result['action_reports'] = actions
    if mode == 'added_mass' or mode.startswith('pcd'):
        operators = assembly.records(log, 'pressure_schur ')
        kind = 'added_mass' if mode == 'added_mass' else 'pcd'
        block.require(operators and all(row['kind'] == kind for row in operators), 'Requested pressure operator absent')
        if mode.startswith('pcd'):
            block.require(all(int(row['velocity_mass']) == 1 for row in operators), 'PCD velocity mass enhancement absent')
        result['pressure_operators'] = operators
    return result


def campaign(args, receipt, result, name, cfg, ranks, modes, ports=False, area=1.):
    directory = args.work / name
    record = dict(name=name, ranks=ranks, configuration=copy.deepcopy(cfg), runs=[])
    result['cases'].append(record)
    runner = previous.EvidenceRunner(args.executable, args.mpiexec, directory, timeout=args.timeout,
                                     interface_area=area, commands=result['commands'])
    reference = None
    mesh_hashes = {p.name: assembly.digest(p) for p in directory.glob('*.msh')}
    for mode in ('direct', *modes):
        row = dict(mode=mode, status='running')
        record['runs'].append(row); previous.save(result, receipt)
        try:
            fields, trace, log = runner.solve(mode, cfg, ranks, flags(mode, ports))
            block.require(mesh_hashes == {p.name: assembly.digest(p) for p in directory.glob('*.msh')},
                          'Input geometry changed between solvers')
            snapshots = previous.snapshot(runner, mode, trace, ranks)
            row.update(audit(log, trace, ranks, mode))
            if reference is None:
                block.require(mode == 'direct', 'No direct reference available')
                reference = fields, trace, snapshots, row['nnz']
            block.require(len(snapshots) == len(reference[2]), 'Saved trajectory length changed')
            row['field_max_difference'] = max(error(fields, reference[0]), *(
                assembly.compare_fields(first, second) for first, second in zip(snapshots, reference[2])))
            block.require(row['field_max_difference'] <= previous.FIELD_LIMIT, 'Physical field mismatch')
            if 'reduced' in features(mode):
                block.require(0 < row['nnz'] < reference[3], 'Reduced P retained the full Jacobian graph')
                row['preconditioner_nnz_ratio'] = row['nnz'] / reference[3]
            row['history_max_difference'] = previous.compare_history(reference[1], trace)
            if ports:
                row['circuit_defect'] = check_rcr_history(runner, mode, cfg['fsi']['domains']['rcr_outlet'], trace)
            row['artifacts'] = [dict(path=str(p), sha256=assembly.digest(p), bytes=p.stat().st_size)
                                for p in sorted(directory.glob(mode + '*')) if p.is_file()]
            row['status'] = 'passed'
        except Exception as exc:
            row.update(status='failed', error=str(exc))
            result['failures'].append(dict(case=name, mode=mode, error=str(exc)))
            if mode == 'direct':
                previous.save(result, receipt)
                break
        previous.save(result, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--build-source', help='Exact source used to build the executable; unspecified is recorded as null')
    parser.add_argument('--sections', nargs='+', choices=('default', 'moving', 'scaling', 'coupling'), default=['default', 'moving'])
    parser.add_argument('--modes', nargs='+', choices=MODES)
    args = parser.parse_args()
    args.executable, args.mpiexec = args.executable.resolve(), args.mpiexec.resolve()
    args.work = args.work.resolve() / str(time.time_ns()); args.work.mkdir(parents=True)
    os.environ.update(OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    receipt = args.work / 'results.json'
    result = dict(status='running', build_source=args.build_source,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  executable=str(args.executable), executable_sha256=assembly.digest(args.executable),
                  driver_sha256=assembly.digest(__file__), linear_gate='1e-12 + 1e-10*rhs_norm',
                  field_absolute_limit=previous.FIELD_LIMIT, cases=[], commands=[], failures=[])
    if 'scaling' in args.sections:
        # This target is saved before any solver run and is assessed separately
        # from physical acceptance; failure to meet it leaves the goal open.
        result['mesh_convergence_goal'] = mesh_convergence_goal([], ())
    previous.save(result, receipt)
    def select(default):
        chosen = tuple(mode for mode in (*default, *FEATURES) if mode in args.modes) if args.modes else default
        block.require(chosen, 'No candidate modes selected for a requested section')
        return chosen
    if 'default' in args.sections:
        for ranks in (1, 2):
            name = f'domains-r{ranks}'
            cfg = previous.domain_case(args.work / name, 3, unequal=True)
            campaign(args, receipt, result, name, cfg, ranks,
                     select(('mono', 'mono_fp32', 'mono_pipe', 'mono_mf', 'mono_mf_pipe', 'mono_chebyshev',
                             'mono_block_chebyshev', 'added_mass', 'pcd_mass')))
    if 'moving' in args.sections:
        name = 'moving-rcr'
        cfg, geometry = circular_case(args.work / name, (1., 0., 0.), (0., 0., 0.))
        cfg['fsi'].update(steps=3, output_interval=1, pressure_face_history=True)
        cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
        cfg['time_control'] = dict(step_sizes=[.015, .013, .017])
        cfg['fsi']['dt'] = math.fsum(cfg['time_control']['step_sizes']) / 3
        campaign(args, receipt, result, name, cfg, 2, select(('mono_mf', 'mono_mf_pipe', 'pcd_robin')),
                 ports=True, area=geometry['interface_area'])
    if 'scaling' in args.sections:
        scaling_modes = select(('mono', 'mono_fp32'))
        for n in SCALING_SUBDIVISIONS:
            name = f'scaling-n{n}-r2'
            cfg = previous.domain_case(args.work / name, n)
            campaign(args, receipt, result, name, cfg, 2, scaling_modes)
        result['mesh_convergence_goal'] = mesh_convergence_goal(result['cases'], scaling_modes)
    if 'coupling' in args.sections:
        for ratio, dt in ((.1, .02), (.01, .005)):
            name = f'coupling-rho{ratio:g}-dt{dt:g}'
            cfg = previous.domain_case(args.work / name, 4, ratio, dt)
            campaign(args, receipt, result, name, cfg, 2, select(('mono', 'added_mass')))
    result['status'] = 'failed' if result['failures'] else 'passed'
    previous.save(result, receipt)
    print('monolithic_fsi_receipt', receipt, result['status'], flush=True)
    if result['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
