"""FSI COO parity: owned fields, changing trace weights, ports, restart and cutback."""
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
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(marker + ' ')]


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


class AssemblyRunner(Runner):
    """Use the existing command/log lifecycle for both rigid and elastic FSI."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evidence = []

    def solve(self, label, cfg, ranks=1, coo=False, extra=(), fail=None):
        cfg = copy.deepcopy(cfg)
        output = self.work/(label+'.vtu')
        cfg['output'] = str(output)
        case = self.work/(label+'.json')
        case.write_text(json.dumps(cfg))
        part = self.work/f'part-{ranks}'
        if not part.exists():
            self.command([self.exe, '-case', case, '-prepare', part, '-parts', ranks], label+'-prepare')
        command = [self.mpi, '-n', ranks, self.exe, '-case', case, '-partition', part,
                   '-fsi_assembly_report', '-solver_report']
        if coo:
            command.append('-fsi_coo')
        command.extend(extra)
        text = self.command(command, label, fail)
        self.evidence.append(dict(label=label, ranks=ranks, coo=coo, command=list(map(str, command)),
                                  expected_failure=fail, log=label+'.log'))
        if fail:
            require('status=success' not in text and not output.exists()
                    and not list(self.work.glob(label+'_rank*.vtu')), 'Failed solve published physical output')
            return {}, [], text
        require(text.count('status=success') == 1, 'Missing or duplicate success marker')
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
        reports = records(text, 'solver_report')
        steps = text.count('fsi_step=')
        require(steps > 0 and len(reports) >= steps, 'Missing successful nonlinear solve reports')
        require(all(int(r['snes_reason']) > 0 and int(r['ksp_reason']) > 0 for r in reports),
                'Unconverged solve reported as successful')
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


def parity(run, cfg, label, ranks=(1, 2), jacobian=False):
    observations, diagnostics = {}, []
    reference = None
    for count in ranks:
        pair = []
        for coo in (False, True):
            name = f'{label}-r{count}-'+('coo' if coo else 'values')
            extra = ['-snes_test_jacobian'] if jacobian and coo and count == 2 else []
            fields, rows, text = run.solve(name, cfg, count, coo, extra)
            pair.append((fields, rows))
            observations[count, coo] = (fields, rows, name)
            if reference is None:
                reference = fields, rows
            diagnostics.append(dict(label=name, field_difference=compare_fields(reference[0], fields),
                                    history_difference=compare_histories(reference[1], rows),
                                    linear_iterations=[int(r['linear_iterations']) for r in records(text, 'solver_report')]))
            if extra:
                ratios = list(map(float, re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)', text)))
                require(ratios and all(math.isfinite(v) for v in ratios) and max(ratios) < 1e-6,
                        'Full reduced FSI Jacobian differs from independent global finite differences')
                diagnostics[-1]['jacobian_relative_difference'] = max(ratios)
        compare_fields(pair[0][0], pair[1][0])
    return observations, diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
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
        run = AssemblyRunner(args.executable, args.mpiexec, directory)
        runners.append(run)
        observations, report[body] = parity(run, cfg, body)
        if body == 'rigid':
            fields, rows, _ = run.solve('rigid-fd', cfg, 2, True, ['-fsi_fd_tangent', '-stop_after', 1])
            expected = owned_fields(directory/'rigid-r2-values_step1.vtu', 2, False)
            report['finite-difference-reference'] = dict(field_difference=compare_fields(expected, fields),
                history_difference=compare_histories(observations[2, False][1][:1], rows))

    directory = work/'moving-port'
    cfg, geometry = circular_case(directory, (1., 0., 0.), (0., 0., 0.))
    cfg['fsi'].update(steps=3, output_interval=1)
    cfg['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
    cfg['time_control'] = dict(step_sizes=[.015, .013, .017])
    run = AssemblyRunner(args.executable, args.mpiexec, directory, interface_area=geometry['interface_area'])
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
        fields, tail, _ = run.solve(label, cfg, 2, not source_coo, ['-restart', checkpoint])
        reference, rows, _ = observations[2, False]
        report['restart'].append(dict(source_coo=source_coo, field_difference=compare_fields(reference, fields),
                                     history_difference=compare_histories(rows[1:], tail)))
        check_rcr_history(run, label, model, tail, restart=1)

    # Keep the same geometry but restore the fixed-port constraints and coupling path.
    fixed = copy.deepcopy(cfg)
    domains = fixed['fsi']['domains']
    del domains['rcr_outlet']['moving_plane_axis']
    for key, tag in [('mesh_constraints', model['tag']), ('solid_constraints', 12)]:
        next(c for c in domains[key] if c['tag'] == tag)['components'] = [0, 1, 2]
    fixed_observations, report['fixed-port'] = parity(run, fixed, 'fixed', ranks=(2,))
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
    replay, trajectory, _ = run.solve('retry-values-replay', retried, 2, False, ['-stop_after', 3])
    report['retry'] = dict(retries=text.count('step_retry='), accepted_dt=rows[0]['accepted_dt'],
                           field_difference=compare_fields(replay, fields),
                           history_difference=compare_histories(trajectory[-1:], rows))

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

    run.command([run.exe, '-case', ROOT/'cases/fluid/stokes.yaml', '-fsi_coo'],
                'unsupported-fluid', fail='require the monolithic FSI problem')

    report['commands'] = [entry for runner in runners for entry in runner.evidence]
    report['executable_sha256'] = hashlib.sha256(Path(args.executable).read_bytes()).hexdigest()
    (work/'results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'PASS: FSI COO owned fields, MPI, ports, Jacobian, restart and cutback; {len(report["commands"])} solves')


if __name__ == '__main__':
    main()
