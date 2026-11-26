"""Independent field/circuit checks for the RCR port Schur wrapper and base AMG choices."""
import argparse
import json
import math
import re
from pathlib import Path

from verify_fsi_inlet import Runner, check_rcr_history, error
from verify_fsi_moving_port import cap, circular_case, release_plane
from verify_fsi_tube import audit_block_linear_log
from generate_branched import generate as generate_junction


def options(velocity='split', adaptive=False, ports=True):
    flags = ['-pc_recipe', 'hybrid', '-pc_plan_rcr_ports', str(ports).lower(),
             '-pc_plan_schur_approx', 'nodal', '-pc_plan_velocity_solver', velocity,
             '-ksp_rtol', '1e-11', '-ksp_atol', '1e-13', '-ksp_max_it', '1500',
             '-ksp_pc_side', 'right', '-ksp_norm_type', 'unpreconditioned',
             '-pc_plan_report', '-rcr_port_report', '-linear_report', '-solver_report']
    if adaptive:
        flags += ['-nonlinear_adaptive_pc', 'true', '-nonlinear_pc_max_reuse', '2',
                  '-nonlinear_pc_change_tolerance', '0.05',
                  '-nonlinear_pc_iteration_growth', '1.5']
    return flags


def audit(log, rows, adaptive=False, port_count=0, velocity=None):
    corrections = audit_block_linear_log(log, len(rows))
    reports = [dict(re.findall(r'(\w+)=([^\s]+)', line))
               for line in log.splitlines() if line.startswith('solver_report ')]
    residuals = [dict(re.findall(r'(\w+)=([^\s]+)', line))
                 for line in log.splitlines() if line.startswith('linear_residual ')]
    ratios = [float(r['norm']) / max(1e-12, 1e-9*float(r['rhs_norm'])) for r in residuals]
    assert ratios and all(math.isfinite(v) and v <= 1 for v in ratios), ratios
    if adaptive:
        assert all(int(r['pc_refreshes']) + int(r['pc_reuses']) == int(r['linear_completed'])
                   for r in reports), reports
    port_stats = [dict(re.findall(r'(\w+)=([^\s]+)', line))
                  for line in log.splitlines() if line.startswith('rcr_port_stats ')]
    if port_count:
        assert port_stats and all(int(r['ports']) == port_count and
                                  int(r['responses']) == port_count*int(r['rebuilds']) and
                                  int(r['setup_reductions']) == int(r['rebuilds']) and
                                  int(r['apply_reductions']) == int(r['applications'])
                                  for r in port_stats), port_stats
        assert any(int(r['applications']) > 0 for r in port_stats)
    else:
        assert not port_stats, 'Unwrapped baseline unexpectedly used the port shell'
    if velocity in ('gamg', 'boomeramg'):
        nodes = [dict(re.findall(r'(\w+)=([^\s]+)', line))
                 for line in log.splitlines() if line.startswith('solver_node ')]
        prefix = ('rcr_bulk_' if port_count else '')+'fieldsplit_dynamics_fieldsplit_velocity_'
        leaves = [r for r in nodes if r['prefix'] == prefix]
        expected = 'gamg' if velocity == 'gamg' else 'hypre'
        assert leaves and all(r['ksp'] == 'preonly' and r['pc'] == expected for r in leaves), leaves
    return dict(corrections=corrections, worst_true_residual_ratio=max(ratios),
                outer_iterations=sum(int(r['linear_iterations']) for r in reports),
                linear_seconds=sum(float(r['linear_seconds']) for r in reports),
                schur_setup_seconds=sum(float(r['schur_setup_seconds']) for r in reports),
                solve_seconds=sum(float(r['solve_seconds']) for r in reports),
                pc_refreshes=sum(int(r['pc_refreshes']) for r in reports),
                pc_reuses=sum(int(r['pc_reuses']) for r in reports),
                pc_context_refreshes=sum(int(r['pc_context_refreshes']) for r in reports))


def compare_history(reference, actual):
    assert len(reference) == len(actual)
    maximum = 0.
    for before, after in zip(reference, actual):
        assert before.keys() == after.keys() and before['step'] == after['step']
        for key in before:
            if 'rcr' in key or 'capacitor' in key:
                maximum = max(maximum, abs(before[key]-after[key]))
    assert maximum < 2e-9, maximum
    return maximum


def single(executable, mpi, work):
    cfg, geometry = circular_case(work, (1., 0., 0.), (0., 0., 0.))
    cfg['fsi'].update(steps=4, output_interval=4)
    cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
    cfg['time_control'] = dict(step_sizes=[.015, .015, .013, .013])
    model = cfg['fsi']['domains']['rcr_outlet']
    run = Runner(executable, mpi, work, interface_area=geometry['interface_area'])
    reference, rows, _ = run.solve('direct', cfg)
    circuit = check_rcr_history(run, 'direct', model, rows)
    area, flux, area0, _ = cap(work, reference, model['tag'], (1., 0., 0.))
    assert abs(area/area0-1) > 1e-6 and abs(flux-rows[-1]['endpoint_rcr_flow']) < 2e-12
    report = dict(direct_circuit_defect=circuit, moving_area_change=area/area0-1)
    candidates = {}
    for label, velocity, ranks, adaptive, ports in (
            ('gamg-baseline-two', 'gamg', 2, False, False),
            ('split-one', 'split', 1, False, True), ('gamg-two', 'gamg', 2, False, True),
            ('boomeramg-two', 'boomeramg', 2, False, True), ('adaptive-two', 'gamg', 2, True, True)):
        fields, trace, log = run.solve(label, cfg, ranks, options(velocity, adaptive, ports))
        gap = error(reference, fields)
        assert gap < 2e-8, (label, gap)
        report[label] = dict(field_error=gap, history_error=compare_history(rows, trace),
                             circuit_defect=check_rcr_history(run, label, model, trace),
                             **audit(log, trace, adaptive, 1 if ports else 0, velocity))
        candidates[label] = (fields, trace)
    assert report['adaptive-two']['pc_context_refreshes'] > 0

    # Restart across base preconditioners; only accepted physical/circuit state
    # is persistent. A cached numerical inverse must be reconstructed.
    checkpoint = work/'checkpoint'
    _, start, log = run.solve('checkpoint', cfg, 2,
                             [*options('gamg'), '-checkpoint', checkpoint, '-stop_after', 2])
    report['checkpoint'] = audit(log, start, port_count=1, velocity='gamg')
    resumed, tail, log = run.solve('resume', cfg, 2,
                                  [*options('boomeramg'), '-restart', checkpoint])
    assert len(tail) == 2
    restart_error = error(candidates['boomeramg-two'][0], resumed)
    assert restart_error < 2e-8, restart_error
    report['restart'] = dict(field_error=restart_error, history_error=compare_history(rows[2:], tail),
                              circuit_defect=check_rcr_history(run, 'resume', model, tail, restart=2),
                              **audit(log, tail, port_count=1, velocity='boomeramg'))
    return report


def multiple(executable, mpi, work):
    cfg = json.loads(generate_junction(work).read_text())
    geometry = json.loads((work/'geometry.json').read_text())
    f = cfg['fsi']
    f.update(steps=3, output_interval=3, dt=.016, pressure_face_history=True)
    cfg['time_control'] = dict(step_sizes=[.016, .014, .017])
    dom = f['domains']
    left, right = dom['rcr_outlets']
    left.update(initial_capacitor_pressure=.18, proximal_resistance=12.,
                distal_resistance=32., compliance=.00625)
    right['initial_capacitor_pressure'] = .09
    release_plane(dom, left, 1, 12)
    release_plane(dom, right, 1, 13)
    run = Runner(executable, mpi, work, interface_area=geometry['interface_area'])
    reference, rows, _ = run.solve('direct-two', cfg, 2)
    report = {}
    changes = []
    for model, normal in ((left, (0., 1., 0.)), (right, (0., -1., 0.))):
        area, flux, area0, _ = cap(work, reference, model['tag'], normal)
        changes.append(area/area0-1)
        assert abs(flux-rows[-1]['endpoint_rcr_flow_'+str(model['tag'])]) < 2e-12
        assert abs(changes[-1]) > 1e-6
    assert abs(rows[-1]['endpoint_rcr_pressure_2']-rows[-1]['endpoint_rcr_pressure_3']) > 1e-6
    report['moving_area_changes'] = changes
    for label, velocity, ranks, ports in (('gamg-baseline-two', 'gamg', 2, False),
                                          ('split-one', 'split', 1, True), ('gamg-two', 'gamg', 2, True),
                                          ('boomeramg-two', 'boomeramg', 2, True)):
        fields, trace, log = run.solve(label, cfg, ranks, options(velocity, ports=ports))
        gap = error(reference, fields)
        assert gap < 2e-8, (label, gap)
        circuit = max(check_rcr_history(run, label, m, trace, sole_pressure=False) for m in (left, right))
        report[label] = dict(field_error=gap, history_error=compare_history(rows, trace),
                             circuit_defect=circuit, **audit(log, trace, port_count=2 if ports else 0,
                                                              velocity=velocity))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    result = dict(single=single(args.executable, args.mpiexec, args.work/'single'),
                  multiple=multiple(args.executable, args.mpiexec, args.work/'multiple'))
    (args.work/'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
