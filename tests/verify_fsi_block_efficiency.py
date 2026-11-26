"""Staged FSI block comparison on the pinned arterial meshes.

Quick mode runs four steps and the unchanged true-residual/five-field gates.
Full mode requires a matching successful quick receipt for each selected mode,
then runs 32 steps, one warmup, and three interleaved four-step samples. Selecting
promising modes is explicit; timing is evidence, never a numerical pass gate.
The twolevel PREONLY candidate applies one cycle, not a fixed linear inverse.
Robustness mode is opt-in: it compares fixed density ratios and time steps to
a fresh direct reference on each identical mesh/partition. It does not require
a speedup, promote a failed candidate, or replace the pinned baseline studies.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import tarfile
import threading
import time
import xml.etree.ElementTree as ET

from verify_fsi_inlet import Runner, error
from verify_fsi_tube import audit_block_linear_log


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'docs/research/data/fsi-linear-transient-2026-11-24/arterial-inputs.tar.xz'
FIXTURE_SHA256 = '662518aa06f1d9f3072c92910fcfd08c3788f0be8bf0875ec035ff6e0984fae6'
GRIDS = {'coarse': ('s24-r3-w2-a6', 1, 1027, 'natural'),
         'fine': ('s48-r4-w4-a6', 2, 3024, 'rcm')}
MODES = ('coupled_nodal', 'added_mass', 'added_mass_a11_onecycle',
         'added_mass_nodal', 'added_mass_fluid_onecycle',
         'twolevel_iterative', 'twolevel_onecycle')
GEOMETRIC_MODES = ('twolevel_rigid', 'gamg_constants')
HPC_MODES = ('aggregate_constants', 'aggregate_rigid', 'aggregate_rigid_adaptive',
             'twolevel_rigid_adaptive', 'coupled_nodal_adaptive')
ROBUST_MODES = ('twolevel_onecycle', 'twolevel_rigid', 'gamg_constants',
                'added_mass_fluid_onecycle')
TARGET = 'max(1e-23, 1e-10*rhs_norm)'
MARGIN = 1.00001
FIELD_LIMIT = 2e-6
TIMERS = ('linear_seconds', 'setup_seconds', 'schur_setup_seconds',
          'assembly_seconds', 'solve_seconds', 'linear_diagnostic_seconds')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def timed_command(command, log, timeout, receipt):
    """Blocking timed wait; the independent watchdog owns only this process group.

    Successful wall time includes launch and process exit, without POSIX timeout
    polling or subsequent log parsing. Failure cleanup is included in failed
    timings and never used as a successful performance sample. The receipt gets
    the observed launcher exit status even when timeout cleanup terminates it.
    """
    command = list(map(str, command))
    log = Path(log)
    start = time.perf_counter()
    process = None
    watchdog = None
    watchdog_started = False
    expired = threading.Event()

    def stop_group():
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        # Retire surviving ranks/descendants even if the launcher has already
        # exited in response to TERM. Never target other jobs.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def deadline():
        if process.poll() is None:
            expired.set()
            stop_group()

    def terminated(signum, _frame):
        # The driver calls this helper on the main thread. A default SIGTERM
        # would bypass Python cleanup and leave the detached MPI job alive.
        # Ignore a repeated TERM while the first cancellation drains the group.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise SystemExit(128 + signum)

    original_term_handler = signal.signal(signal.SIGTERM, terminated)
    try:
        with log.open('w') as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            watchdog = threading.Timer(max(0., timeout-(time.perf_counter()-start)), deadline)
            watchdog.daemon = True
            watchdog.start()
            watchdog_started = True
            returncode = process.wait()
            if returncode and not expired.is_set():
                stop_group()
    except BaseException:
        stop_group()
        raise
    finally:
        if watchdog is not None:
            watchdog.cancel()
            if watchdog_started:
                watchdog.join()
        signal.signal(signal.SIGTERM, original_term_handler)
        receipt.update(wall_seconds=time.perf_counter()-start,
                       exit_code=None if process is None else process.returncode,
                       timeout=expired.is_set())
    if expired.is_set():
        raise subprocess.TimeoutExpired(command, timeout, output=log.read_bytes())
    output = log.read_text()
    if returncode:
        raise subprocess.CalledProcessError(returncode, command, output=output)
    return output


def flags(mode, ordering, outer_rtol='5e-11'):
    if mode.endswith('_adaptive'):
        return flags(mode.removesuffix('_adaptive'), ordering, outer_rtol) + [
            '-nonlinear_adaptive_pc', 'true', '-nonlinear_pc_max_reuse', '4',
            '-nonlinear_pc_change_tolerance', '0.1', '-nonlinear_pc_iteration_growth', '1.5']
    if mode == 'direct':
        return ['-ksp_type', 'preonly', '-pc_type', 'lu',
                '-pc_factor_mat_solver_type', 'mumps']
    result = ['-ksp_pc_side', 'right', '-ksp_norm_type', 'unpreconditioned',
              '-ksp_rtol', outer_rtol, '-ksp_atol', '5e-24', '-ksp_max_it', '3000',
              '-ksp_gmres_restart', '100', '-ksp_gmres_modifiedgramschmidt',
              '-pc_plan_schur_approx', 'nodal',
              '-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type', 'lower']
    if mode.startswith('added_mass'):
        fluid = '-fieldsplit_dynamics_fieldsplit_fluid_'
        structure = '-fieldsplit_dynamics_fieldsplit_structure_'
        structural_cycle = mode in ('added_mass_nodal', 'added_mass_a11_onecycle')
        # Freeze both response budgets explicitly so later production-default
        # changes cannot silently change the controls or the feedback ablation.
        result += ['-pc_recipe', 'added_mass',
                   '-pc_plan_structure_approx', 'nodal' if mode == 'added_mass_nodal' else 'a11',
                   fluid + 'ksp_type', 'preonly' if mode == 'added_mass_fluid_onecycle' else 'fgmres',
                   fluid + 'ksp_rtol', '1e-4', fluid + 'ksp_max_it', '20',
                   structure + 'ksp_type', 'preonly' if structural_cycle else 'fgmres',
                   structure + 'ksp_rtol', '1e-2', structure + 'ksp_max_it', '20']
        return result
    twolevel = mode.startswith('twolevel_')
    gamg = mode.startswith('gamg_')
    aggregate = mode.startswith('aggregate_')
    onecycle = mode in ('twolevel_onecycle', 'twolevel_rigid') or gamg or aggregate
    prefix = '-fieldsplit_dynamics_fieldsplit_velocity_'
    result += ['-pc_recipe', 'hybrid', '-pc_plan_velocity_solver',
               'twolevel' if twolevel else 'gamg' if gamg else 'aggregate' if aggregate else 'coupled',
               prefix + ('mg_levels_' if twolevel or gamg or aggregate else '') +
               'sub_pc_factor_mat_ordering_type', ordering]
    if aggregate:
        result += ['-pc_plan_velocity_aggregate_nodes', '16']
    if twolevel or gamg or aggregate:
        result += ['-pc_plan_velocity_coarse_space',
                   'rigid' if mode.endswith('_rigid') else 'constants']
        result += [prefix + 'ksp_type', 'preonly' if onecycle else 'fgmres',
                   prefix + 'ksp_rtol', '1e-4', prefix + 'ksp_max_it', '20',
                   prefix + 'pc_mg_multiplicative_cycles', '1',
                   prefix + 'pc_mg_cycle_type', 'v']
    return result


def expected_solvers(mode):
    """Prefixes and actual KSP/PC types for each deliberately fixed response."""
    if mode.endswith('_adaptive'):
        return expected_solvers(mode.removesuffix('_adaptive'))
    if mode == 'direct':
        return [('-', 'preonly', 'lu')]
    if mode.startswith('added_mass'):
        fluid = 'preonly' if mode == 'added_mass_fluid_onecycle' else 'fgmres'
        structure = 'preonly' if mode in ('added_mass_nodal', 'added_mass_a11_onecycle') else 'fgmres'
        return [('fieldsplit_dynamics_fieldsplit_fluid_', fluid, 'fieldsplit'),
                ('fieldsplit_dynamics_fieldsplit_structure_', structure, 'gamg')]
    if mode.startswith('twolevel_'):
        return [('fieldsplit_dynamics_fieldsplit_velocity_',
                 'preonly' if mode in ('twolevel_onecycle', 'twolevel_rigid') else 'fgmres', 'mg')]
    if mode.startswith('gamg_'):
        return [('fieldsplit_dynamics_fieldsplit_velocity_', 'preonly', 'gamg')]
    if mode.startswith('aggregate_'):
        return [('fieldsplit_dynamics_fieldsplit_velocity_', 'preonly', 'mg'),
                ('fieldsplit_dynamics_fieldsplit_velocity_mg_coarse_', 'preonly', 'gamg')]
    if mode == 'coupled_nodal':
        return [('fieldsplit_dynamics_fieldsplit_velocity_', 'gmres', 'asm')]
    raise ValueError(('unknown solver mode', mode))


def copy_fixture(destination, grid):
    destination.mkdir(parents=True)
    with tarfile.open(FIXTURE, 'r:xz') as bundle:
        for name in ('case.json', 'fluid.msh', 'solid.msh'):
            matches = [m for m in bundle.getmembers() if m.isfile() and
                       Path(m.name).name == name and any(
                           part == grid or part.startswith(grid + '-')
                           for part in Path(m.name).parts[:-1])]
            require(len(matches) == 1, ('pinned input member', grid, name))
            with bundle.extractfile(matches[0]) as source:
                (destination / name).write_bytes(source.read())
    config = json.loads((destination / 'case.json').read_text())
    expected = dict(pressure=80., dt=1/32, steps=32, young=400000., poisson=.45,
                    density=1060., solid_density=1100., viscosity=.004,
                    output_interval=4, stabilization_model='volume')
    require(all(config['fsi'].get(k) == v for k, v in expected.items()), config['fsi'])
    require(config['time'] == dict(scheme='generalized_alpha', rho_infinity=.5),
            config['time'])
    require(config['fsi'].get('pressure_time') ==
            dict(amplitude=0., period=1., ramp_time=1.), 'unexpected pressure ramp')
    return {name: digest(destination / name) for name in ('case.json', 'fluid.msh', 'solid.msh')}


def owned_fields(directory, stem, ranks, names):
    fields = {name: {} for name in names}
    for rank in range(ranks):
        path = directory / (stem + (f'_rank{rank}' if ranks > 1 else '') + '.vtu')
        arrays = {}
        for node in ET.parse(path).findall('.//PointData/DataArray'):
            name = node.attrib['Name']
            require(name not in arrays, ('duplicate VTU array', path, name))
            arrays[name] = (node.attrib, (node.text or '').split())
        ids = list(map(int, arrays['mesh_node_id'][1]))
        owners = list(map(int, arrays['owner'][1]))
        require(ids and len(ids) == len(owners), ('invalid VTU identities', path))
        require(all(0 <= owner < ranks for owner in owners), ('invalid owner', path))
        for name in names:
            attributes, tokens = arrays[name]
            width = 1 if name == 'pressure' else 3
            require(int(attributes.get('NumberOfComponents', '1')) == width and
                    len(tokens) == width * len(ids), ('VTU field length', path, name))
            values = list(map(float, tokens))
            require(all(map(math.isfinite, values)), ('nonfinite VTU field', path, name))
            for i, (node, owner) in enumerate(zip(ids, owners)):
                if owner == rank:
                    require(node not in fields[name], ('duplicate owned node', path, name, node))
                    fields[name][node] = values[width*i:width*(i+1)]
    require(all(fields.values()), ('empty fields', directory, stem))
    return fields


def compare_fields(reference, actual, ranks, steps):
    peaks = {}
    for step in range(4, steps + 1, 4):
        for suffix, names in [('', ('velocity', 'pressure', 'mesh_displacement')),
                              ('_solid', ('velocity', 'displacement'))]:
            stem = f'tube_step{step}{suffix}'
            first = owned_fields(reference, stem, ranks, names)
            second = owned_fields(actual, stem, ranks, names)
            for name in names:
                require(first[name].keys() == second[name].keys(), ('field node set', stem, name))
                key = ('wall_' if suffix else 'fluid_') + name
                peak, difference = peaks.get(key, (0., 0.))
                peak = max(peak, *(abs(x) for row in first[name].values() for x in row))
                difference = max(difference, error(first[name], second[name]))
                peaks[key] = peak, difference
    ratios = {}
    for name, (peak, difference) in peaks.items():
        require(peak > 0. or difference == 0., ('nonzero error against zero field', name))
        ratios[name] = difference / peak if peak else 0.
        require(math.isfinite(ratios[name]), ('nonfinite field ratio', name))
    require(len(ratios) == 5, ('missing field comparisons', ratios))
    return ratios


def node_snapshots(text):
    """Bounded per-path last-call observations; never cumulative inner work."""
    nodes, omitted = {}, 0
    for line in text.splitlines():
        if not line.startswith('solver_node '):
            continue
        row = dict(re.findall(r'(\w+)=([^\s]+)', line))
        key = (row['rank'], row['path'], row['prefix'])
        if key not in nodes and len(nodes) == 256:
            omitted += 1
            continue
        rec = nodes.setdefault(key, dict(rank=int(row['rank']), path=row['path'],
                                       prefix=row['prefix'], observations=0,
                                       max_last_iterations=0, reason_counts={}))
        rec['observations'] += 1
        rec['max_last_iterations'] = max(rec['max_last_iterations'], int(row['last_iterations']))
        reason = row['ksp_reason']
        rec['reason_counts'][reason] = rec['reason_counts'].get(reason, 0) + 1
        rec['last'] = row
    return dict(solver_nodes=list(nodes.values()), omitted_node_observations=omitted,
                inner_iteration_semantics='last-call snapshots, not accumulated inner iterations')


def audit(text, steps, dofs, ranks, mode, dt=1/32):
    # Reuse the public report-count/finiteness checks, then enforce the tighter
    # arterial target and row-wise reconstruction used by verify_arterial_block.
    count = audit_block_linear_log(text, steps)
    require(text.splitlines().count('status=success') == 1, 'missing unique solver success')
    residuals, reports, accepted, field_counts = [], [], [], {}
    for line in text.splitlines():
        row = dict(re.findall(r'(\w+)=([^\s]+)', line))
        if line.startswith('linear_residual '):
            norm, rhs = float(row['norm']), float(row['rhs_norm'])
            require(math.isfinite(norm) and math.isfinite(rhs) and min(norm, rhs) >= 0., row)
            step = len(accepted) + 1
            require(int(row['solve']) == 1 + sum(r['step'] == step for r in residuals), row)
            ratio = norm / max(1e-23, 1e-10 * rhs)
            require(math.isfinite(ratio), ('nonfinite true residual ratio', row))
            residuals.append(dict(step=step, norm=norm, rhs=rhs, ratio=ratio, fields={}))
        elif line.startswith('linear_field_residual '):
            require(residuals and row['name'] not in residuals[-1]['fields'], row)
            value = float(row['rms'])
            require(math.isfinite(value) and value >= 0. and
                    float(row['constraint_max']) == 0. and float(row['residual_scale']) == 1., row)
            residuals[-1]['fields'][row['name']] = value
        elif line.startswith('field_residual '):
            rows = int(row['equation_rows'])
            require(rows > 0 and int(row['constraint_rows']) == 0 and
                    field_counts.setdefault(row['name'], rows) == rows, row)
        elif line.startswith('solver_report '):
            require(int(row['dofs']) == dofs and int(row['ranks']) == ranks and
                    min(int(row['snes_reason']), int(row['ksp_reason'])) > 0 and
                    int(row['domain_rejections']) == 0, row)
            reports.append(row)
        elif line.startswith('fsi_step='):
            step = len(accepted) + 1
            stage = (step - 1 + (1. if step == 1 else 2/3)) * dt
            ramp = min(max(stage, 0.), 1.)
            pressure = 80 * ramp**3 * (10 + ramp * (-15 + 6*ramp))
            require(int(row['fsi_step']) == step and abs(float(row['time']) - step*dt) < 1e-14 and
                    abs(float(row['evaluation_time']) - stage) < 1e-14 and
                    abs(float(row['applied_pressure']) - pressure) < 1e-11, row)
            accepted.append(row)
        elif line.startswith(('linear_residual_unavailable', 'linear_iteration_limit_residual ',
                              'step_retry=', 'error=', 'EONSim rank ')):
            raise ValueError(line)
    require(len(accepted) == len(reports) == steps and len(residuals) == count, 'missing solve evidence')
    require(set(field_counts) == {'velocity', 'pressure', 'structure', 'mesh'} and
            sum(field_counts.values()) == dofs, field_counts)
    for step, report in enumerate(reports, 1):
        require(sum(r['step'] == step for r in residuals) == int(report['linear_completed']) and
                int(report['linear_started']) == int(report['linear_completed']), report)
        if mode.endswith('_adaptive'):
            require(int(report['pc_refreshes']) >= 0 and int(report['pc_reuses']) >= 0 and
                    int(report['pc_refreshes']) + int(report['pc_reuses']) == int(report['linear_completed']),
                    ('adaptive policy did not account for every true linear correction', report))
    for row in residuals:
        require(row['fields'].keys() == field_counts.keys(), row)
        reconstructed = math.sqrt(sum(field_counts[k] * v*v for k, v in row['fields'].items()))
        require(math.isclose(reconstructed, row['norm'], rel_tol=2e-12, abs_tol=1e-300), row)
    result = dict(steps=steps, corrections=len(residuals),
                  within_target=sum(r['ratio'] <= MARGIN for r in residuals),
                  worst_ratio=max(r['ratio'] for r in residuals),
                  outer_iterations=sum(int(r['linear_iterations']) for r in reports),
                  correction_history=residuals, step_reports=reports, **node_snapshots(text))
    if mode.endswith('_adaptive'):
        for name in ('pc_refreshes', 'pc_reuses', 'pc_drift_refreshes', 'pc_age_refreshes',
                     'pc_iteration_refreshes', 'pc_context_refreshes'):
            result[name] = sum(int(report[name]) for report in reports)
    for name in TIMERS:
        values = [float(r[name]) for r in reports]
        require(all(math.isfinite(x) and x >= 0. for x in values), ('invalid timer', name))
        result[name] = sum(values)
    require(result['solver_nodes'], 'missing solver-node observations')
    expected = {prefix: (ksp, pc) for prefix, ksp, pc in expected_solvers(mode)}
    observations = {prefix: [0] * ranks for prefix in expected}
    # Last-call summaries intentionally discard earlier observations. Validate
    # the complete log separately so an early wrong type or a missing/duplicate
    # rank observation cannot be hidden by a later correct snapshot.
    for line in text.splitlines():
        if not line.startswith('solver_node '):
            continue
        row = dict(re.findall(r'(\w+)=([^\s]+)', line))
        prefix = row['prefix']
        if prefix not in expected:
            continue
        rank = int(row['rank'])
        require(0 <= rank < ranks, ('invalid requested-solver rank', mode, row))
        require((row['ksp'], row['pc']) == expected[prefix],
                ('requested solver type differs', mode, row))
        observations[prefix][rank] += 1
    for prefix, counts in observations.items():
        require(counts == [steps] * ranks,
                ('requested solver observation counts', mode, prefix, counts, steps))
    return result


def save(summary, path):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def provenance(executable):
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
                         capture_output=True, timeout=10, check=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT,
                           text=True, capture_output=True, timeout=10, check=True).stdout
    return dict(source_commit=git, source_dirty=bool(dirty), executable_sha256=digest(executable),
                input_sha256=digest(FIXTURE),
                script_hashes={name: digest(ROOT / 'tests' / name) for name in
                               ('verify_fsi_block_efficiency.py', 'verify_fsi_tube.py',
                                'verify_fsi_inlet.py')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--stage', choices=('quick', 'full', 'robustness'), default='quick')
    parser.add_argument('--grids', nargs='+', choices=tuple(GRIDS))
    parser.add_argument('--modes', nargs='+', choices=MODES + GEOMETRIC_MODES + HPC_MODES)
    parser.add_argument('--outer-rtol', choices=('5e-11', '1e-11'), default='5e-11',
                        help='common iterative KSP request; the independent true-residual gate stays fixed')
    parser.add_argument('--quick-results', type=Path)
    parser.add_argument('--quick-timeout', type=float, default=130.)
    parser.add_argument('--full-timeout', type=float, default=600.)
    parser.add_argument('--density-ratios', type=float, nargs='+', default=[1., .1, .01],
                        help='rho_s/rho_f for the opt-in robustness stage')
    parser.add_argument('--time-steps', type=float, nargs='+', default=[1/32, 1/128],
                        help='seconds per step for the opt-in robustness stage')
    parser.add_argument('--robust-steps', type=int, default=8,
                        help='accepted steps per robustness case; a positive multiple of four')
    parser.add_argument('--timing-samples', type=int, default=0,
                        help='optional robustness timing samples after one warmup; zero or at least three')
    args = parser.parse_args()
    if args.grids is None:
        args.grids = ['fine'] if args.stage == 'robustness' else list(GRIDS)
    if args.modes is None:
        # Preserve the historical screening variants and add two short checks
        # for the newly implemented production paths. The larger parameter
        # sweep remains an explicit manual stage.
        args.modes = list(ROBUST_MODES if args.stage == 'robustness' else
                          (*MODES, 'twolevel_rigid', 'gamg_constants'))
    require(len(set(args.modes)) == len(args.modes) and len(set(args.grids)) == len(args.grids),
            'duplicate modes or grids')
    require(all(math.isfinite(x) and x > 0. for x in (args.quick_timeout, args.full_timeout)),
            'execution budgets must be finite and positive')
    require(all(math.isfinite(x) and x > 0. for x in (*args.density_ratios, *args.time_steps)) and
            len(set(args.density_ratios)) == len(args.density_ratios) and
            len(set(args.time_steps)) == len(args.time_steps), 'invalid or duplicate robustness parameters')
    require(args.robust_steps > 0 and args.robust_steps % 4 == 0 and
            (args.timing_samples == 0 or args.timing_samples >= 3), 'invalid robustness step/sample count')
    # Imports define helpers only. Process environment changes and all external
    # commands are confined to main, after the caller has pushed this source.
    environment = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                       OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    os.environ.update(environment)
    exe, mpi, work = Path(args.executable).resolve(), Path(args.mpiexec).resolve(), args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    stamp = str(time.time_ns())
    output = work / args.stage / stamp
    output.mkdir(parents=True)
    result_path = work / ('results-' + args.stage + '.json')
    summary = dict(stage=args.stage, output_directory=str(output), modes=['direct', *args.modes],
                   grids=args.grids, target=TARGET, tolerance_margin=MARGIN,
                   outer_ksp_rtol=args.outer_rtol,
                   field_relative_peak_limit=FIELD_LIMIT, environment=environment,
                   timing_semantics=dict(
                       linear_seconds='rank-max KSP intervals, including PC setup and inner solves',
                       setup_seconds='nonlinear solve initialization, not total PC setup',
                       schur_setup_seconds='explicit tree configuration outside KSP intervals',
                       wall_seconds='blocking child wait plus launch; independent timeout watchdog; excludes log parsing'),
                   cases=[], failures=[], status='running', **provenance(exe))
    if args.stage == 'robustness':
        summary['robustness'] = dict(density_ratio_definition='solid_density / fluid_density',
                                    density_ratios=args.density_ratios, time_steps=args.time_steps,
                                    accepted_steps=args.robust_steps, timing_samples=args.timing_samples,
                                    scope='single-host parameter screening; density ratio alone is not an added-mass number')
    save(summary, result_path)
    try:
        require(summary['input_sha256'] == FIXTURE_SHA256, 'pinned arterial fixture changed')
        if args.stage == 'full':
            quick_path = (args.quick_results or work / 'results-quick.json').resolve()
            quick = json.loads(quick_path.read_text())
            require(quick['stage'] == 'quick', 'full stage requires quick evidence')
            for key in ('executable_sha256', 'input_sha256', 'script_hashes', 'target',
                        'tolerance_margin', 'field_relative_peak_limit', 'outer_ksp_rtol'):
                require(quick[key] == summary[key], ('quick evidence differs', key))
            for grid in args.grids:
                grid_name, _, _, ordering = GRIDS[grid]
                matches = [c for c in quick['cases'] if c['grid'] == grid_name]
                require(len(matches) == 1, ('missing quick grid', grid))
                for mode in summary['modes']:
                    runs = [r for r in matches[0]['runs'] if r['mode'] == mode]
                    require(len(runs) == 1 and runs[0]['status'] == 'passed' and
                            runs[0]['steps'] == 4 and runs[0]['flags'] == flags(mode, ordering, args.outer_rtol),
                            ('selected mode needs passing quick evidence', grid, mode))
            summary['quick_evidence'] = dict(path=str(quick_path), sha256=digest(quick_path))
    except (ValueError, KeyError, OSError) as exc:
        summary['status'] = 'failed'
        summary['failures'].append(dict(phase='input_and_quick_provenance', error=str(exc)))
        save(summary, result_path)
        raise

    scenarios = [(grid, None, 1/32) for grid in args.grids]
    if args.stage == 'robustness':
        scenarios = [(grid, ratio, dt) for grid in args.grids
                     for ratio in args.density_ratios for dt in args.time_steps]
    for scenario_number, (grid_alias, density_ratio, dt) in enumerate(scenarios, 1):
        grid, ranks, dofs, ordering = GRIDS[grid_alias]
        scenario = f'scenario-{scenario_number:02d}' if density_ratio is not None else 'baseline'
        directory = output / grid if density_ratio is None else output / grid / scenario
        case = directory / 'input'
        rec = dict(grid=grid, ranks=ranks, dofs=dofs, ordering=ordering, runs=[])
        if density_ratio is not None:
            rec.update(scenario=scenario, density_ratio=density_ratio, dt=dt,
                       physical_end_time=args.robust_steps*dt)
        summary['cases'].append(rec)
        part = directory / 'partition'
        prepare = [str(exe), '-case', str(case / 'case.json'), '-prepare', str(part), '-parts', str(ranks)]
        rec['prepare_command'] = prepare
        save(summary, result_path)
        try:
            rec['input_hashes'] = copy_fixture(case, grid)
            if density_ratio is not None:
                rec['source_input_hashes'] = dict(rec['input_hashes'])
                config = json.loads((case / 'case.json').read_text())
                config['fsi'].update(solid_density=config['fsi']['density']*density_ratio,
                                     dt=dt, steps=args.robust_steps)
                (case / 'case.json').write_text(json.dumps(config, indent=2, allow_nan=False) + '\n')
                rec['input_hashes']['case.json'] = digest(case / 'case.json')
                rec['physics'] = dict(fluid_density=config['fsi']['density'],
                                      solid_density=config['fsi']['solid_density'],
                                      dt=dt, steps=args.robust_steps,
                                      pressure=config['fsi']['pressure'],
                                      pressure_time=config['fsi']['pressure_time'], time=config['time'])
            Runner(exe, str(mpi), directory, timeout=args.quick_timeout).command(prepare, 'prepare')
            rec['partition_hashes'] = {str(path.relative_to(part)): digest(path)
                                       for path in sorted(part.rglob('*')) if path.is_file()}
            require(rec['partition_hashes'], 'partition prepared without files')
            rec['prepare_status'] = 'passed'
        except (AssertionError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
            rec.update(prepare_status='failed', prepare_error=str(exc))
            summary['failures'].append(dict(grid=grid, scenario=scenario, phase='prepare', error=str(exc)))
            save(summary, result_path)
            continue
        reference = None

        def run(mode, steps, label):
            out = directory / label
            out.mkdir()
            log = out / 'solve.log'
            command = [str(mpi), '--map-by', 'core', '--bind-to', 'core', '-n', str(ranks),
                       str(exe), '-case', str(case / 'case.json'), '-partition', str(part),
                       '-output', str(out / 'tube.vtu'), '-solver_report', '-linear_report',
                       '-stop_after', str(steps), *flags(mode, ordering, args.outer_rtol)]
            budget = args.full_timeout if steps > 4 else args.quick_timeout
            row = dict(mode=mode, label=label, steps_requested=steps, flags=flags(mode, ordering, args.outer_rtol),
                       command=command, output_directory=str(out), execution_budget_seconds=budget,
                       status='running', exit_code=None, timeout=False)
            rec['runs'].append(row)
            save(summary, result_path)
            start = time.monotonic()
            try:
                text = timed_command(command, log, budget, row)
                row.update(audit(text, steps, dofs, ranks, mode, dt=dt))
                require(row['within_target'] == row['corrections'], ('true residual gate', row['worst_ratio']))
                ratios = compare_fields(reference or out, out, ranks, steps)
                row['field_relative_peaks'] = ratios
                require(all(v <= FIELD_LIMIT for v in ratios.values()), ('field gate', ratios))
                row['status'] = 'passed'
            except (AssertionError, ValueError, KeyError, IndexError, OSError,
                    ET.ParseError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                row.update(status='failed', error=str(exc), timeout=isinstance(exc, subprocess.TimeoutExpired))
                if isinstance(exc, subprocess.TimeoutExpired):
                    # The helper retained the actual terminated launcher's
                    # status, separately from this timeout classification.
                    row['failure_kind'] = 'timeout'
                elif isinstance(exc, subprocess.CalledProcessError):
                    row.update(failure_kind='process_exit', exit_code=exc.returncode)
                else:
                    match = re.search(r'solve exited with (-?\d+):', str(exc))
                    if match:
                        row['exit_code'] = int(match[1])
                if log.exists():
                    row.update(node_snapshots(log.read_text(errors='replace')))
                summary['failures'].append(dict(grid=grid, scenario=scenario,
                                               mode=mode, label=label, error=str(exc)))
            row.setdefault('wall_seconds', time.monotonic()-start)
            if log.exists():
                row['log_sha256'] = digest(log)
            save(summary, result_path)
            print('fsi_block_efficiency_run ' + json.dumps(dict(grid=grid, scenario=scenario, **{
                k: v for k, v in row.items() if k not in
                ('command', 'flags', 'correction_history', 'step_reports', 'solver_nodes')}),
                allow_nan=False), flush=True)
            return row

        steps = args.robust_steps if args.stage == 'robustness' else 4 if args.stage == 'quick' else 32
        direct = run('direct', steps, args.stage + '-direct')
        if direct['status'] != 'passed':
            continue
        reference = Path(direct['output_directory'])
        passed = ['direct']
        for mode in args.modes:
            if run(mode, steps, args.stage + '-' + mode)['status'] == 'passed':
                passed.append(mode)
        samples = 3 if args.stage == 'full' else args.timing_samples if args.stage == 'robustness' else 0
        if samples:
            for mode in passed:
                run(mode, 4, 'warmup-' + mode)
            for repeat in range(samples):
                sequence = passed[repeat % len(passed):] + passed[:repeat % len(passed)]
                for mode in sequence:
                    run(mode, 4, f'timing-{repeat+1}-{mode}')
            rec['medians'] = {}
            for mode in passed:
                rows = [r for r in rec['runs'] if r['mode'] == mode and
                        r['label'].startswith('timing-') and r['status'] == 'passed']
                if len(rows) == samples:
                    rec['medians'][mode] = dict(samples=samples, **{
                        key: statistics.median(r[key] for r in rows)
                        for key in ('wall_seconds', 'outer_iterations', *TIMERS)})
            save(summary, result_path)
    summary['status'] = 'failed' if summary['failures'] else 'passed'
    save(summary, result_path)
    print('fsi_block_efficiency_summary ' + json.dumps(
        dict(status=summary['status'], results=str(result_path),
             cases=[dict(grid=c['grid'], medians=c.get('medians', {})) for c in summary['cases']],
             failures=summary['failures']), allow_nan=False), flush=True)
    return 1 if summary['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
