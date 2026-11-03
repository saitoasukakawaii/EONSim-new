"""Time-dependent traction, accepted histories, and MPI publication on real FSI solves."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cases/fsi'))
from generate_domains import generate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--executable', required=True)
    p.add_argument('--mpiexec', required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--checks', choices=['state', 'convergence'], default='state')
    a = p.parse_args()
    a.work = a.work.resolve()
    a.work.mkdir(parents=True, exist_ok=True)
    base = json.loads(generate(a.work).read_text())
    base['fsi'].update(dt=.004, steps=10, stabilization_tau=.05,
                       pressure_time=dict(amplitude=.25, period=.02, ramp_time=.01), output_interval=3)
    base['solver'].update(relative_tolerance=1e-11, absolute_tolerance=1e-13)

    def command(args, label, fail=None):
        r = subprocess.run(list(map(str, args)), text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=240)
        (a.work / (label + '.log')).write_text(r.stdout)
        if fail is None:
            assert r.returncode == 0, r.stdout[-6000:]
        else:
            assert r.returncode != 0 and fail in r.stdout, r.stdout[-6000:]
            assert 'status=success' not in r.stdout
        return r.stdout

    def solve(label, cfg=None, ranks=1, extra=(), fail=None, restart_step=None):
        cfg = copy.deepcopy(base if cfg is None else cfg)
        cfg['output'] = str(a.work / (label + '.vtu'))
        case = a.work / (label + '.json')
        case.write_text(json.dumps(cfg))
        body = cfg['fsi'].get('body', 'rigid')
        part = a.work / f'part-{body}-{ranks}'
        if not part.exists():
            command([a.executable, '-case', case, '-prepare', part, '-parts', ranks], 'prepare-' + label)
        log = command([a.mpiexec, '-n', ranks, a.executable, '-case', case, '-partition', part, *extra], label, fail)
        if fail:
            return {}, [], log
        history = a.work / (label + ('' if restart_step is None else f'_restart{restart_step}') + '.csv')
        rows = []
        if cfg['fsi'].get('output_interval', 0):
            with history.open() as f:
                rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]
            steps = re.findall(r'fsi_step=(\d+)', log)
            assert [int(row['step']) for row in rows] == list(map(int, steps))
            assert all(x['time'] < y['time'] for x, y in zip(rows, rows[1:]))
            for row in rows:
                t = row['evaluation_time']
                profile = cfg['fsi'].get('pressure_time')
                pressure = cfg['fsi']['pressure']
                if profile:
                    ramp = profile.get('ramp_time', 0)
                    x = min(t / ramp, 1) if ramp else 1
                    pressure = x**3 * (10 - 15*x + 6*x*x) * (pressure + profile['amplitude'] * math.sin(2*math.pi*t/profile['period']))
                assert abs(pressure-row['applied_pressure']) < 1e-12, row
                af = 1
                if cfg.get('time', {}).get('scheme') == 'generalized_alpha' and row['time_order'] == 2:
                    af = 1/(1+cfg['time'].get('rho_infinity', .5))
                assert abs(t-(row['time']-(1-af)*row['accepted_dt'])) < 1e-14, row
                assert abs(row['evaluation_body_balance']) < 2e-9, row
                assert abs(row['evaluation_power_balance']) < 2e-9, row
            expected = [r for r in rows if int(r['step']) % cfg['fsi']['output_interval'] == 0 or r is rows[-1]]
            for solid in ([False, True] if body == 'elastic' else [False]):
                series = history.with_name(history.stem + ('_solid' if solid else '') + '.pvd')
                entries = ET.parse(series).findall('.//DataSet')
                assert [float(e.attrib['timestep']) for e in entries] == [r['time'] for r in expected]
                reference_points = {}
                last_pieces = []
                for e in entries:
                    path = series.parent/e.attrib['file']
                    tree = ET.parse(path)
                    pieces = [path] if ranks == 1 else [path.parent/p.attrib['Source'] for p in tree.findall('.//Piece')]
                    last_pieces = pieces
                    for piece in pieces:
                        data = ET.parse(piece)
                        points = list(map(float, data.find('.//Points/DataArray').text.split()))
                        ids = list(map(int, data.find('.//PointData/DataArray[@Name="mesh_node_id"]').text.split()))
                        displacement = list(map(float, data.find('.//PointData/DataArray[@Name="'+('displacement' if solid else 'mesh_displacement')+'"]').text.split()))
                        for i, node in enumerate(ids):
                            reference = [points[3*i+c]-displacement[3*i+c] for c in range(3)]
                            if node in reference_points:
                                assert max(abs(v-w) for v, w in zip(reference, reference_points[node])) < 1e-12
                            reference_points[node] = reference
                for rank, piece in enumerate(last_pieces):
                    suffix = ('_solid' if solid else '') + (f'_rank{rank}' if ranks > 1 else '') + '.vtu'
                    assert piece.read_bytes() == (a.work/(label+suffix)).read_bytes()
        fields = {}
        for solid in ([False, True] if body == 'elastic' else [False]):
            for rank in range(ranks):
                suffix = ('_solid' if solid else '') + (f'_rank{rank}' if ranks > 1 else '')
                tree = ET.parse(a.work/(label+suffix+'.vtu'))
                arrays = {e.attrib['Name']: (int(e.attrib.get('NumberOfComponents', 1)), list(map(float, e.text.split())))
                          for e in tree.findall('.//PointData/DataArray')}
                # Only nodes of this output domain have meaningful physical values.
                used = set(map(int, tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
                for i in used:
                    node = int(arrays['mesh_node_id'][1][i])
                    for name, (width, values) in arrays.items():
                        if name in ('owner', 'mesh_node_id', 'algebra_node_id'):
                            continue
                        fields[(solid, node, name)] = values[width*i:width*(i+1)]
        return fields, rows, log

    def error(x, y, name=None):
        keys = {k for k in x if name is None or k[2] == name}
        assert keys == {k for k in y if name is None or k[2] == name}
        diffs = [(v-w)**2 for k in keys for v, w in zip(x[k], y[k])]
        return math.sqrt(sum(diffs)/len(diffs))

    if a.checks == 'convergence':
        cfg = copy.deepcopy(base)
        cfg['fsi'].update(output_interval=0, dt=.000015625, steps=2560)
        cfg['time'] = dict(scheme='bdf2')
        reference, _, _ = solve('reference', cfg)
        evidence = []
        for scheme in ('be', 'bdf2', 'generalized_alpha'):
            previous = {}
            cfg['time'] = dict(scheme=scheme)
            for h in ((.00025, .000125, .0000625) if scheme == 'be' else (.0005, .00025, .000125)):
                cfg['fsi'].update(dt=h, steps=round(.04/h))
                actual, _, _ = solve(f'{scheme}-{h}', cfg)
                row = dict(scheme=scheme, h=h)
                for name in ('velocity', 'pressure', 'mesh_displacement'):
                    value = error(actual, reference, name)
                    row[name] = value
                    if name in previous:
                        order = math.log(previous[name]/value, 2)
                        row[name+'_order'] = order
                        assert order > (.85 if scheme == 'be' else 1.7), row
                    previous[name] = value
                evidence.append(row)
                print(row, flush=True)
        (a.work/'results.json').write_text(json.dumps(evidence, indent=2)+'\n')
        return

    for scheme in ('be', 'bdf2', 'generalized_alpha'):
        cfg = copy.deepcopy(base)
        cfg['time'] = dict(scheme=scheme)
        cfg['time_control'] = dict(step_sizes=[.003, .005]*5)
        one, rows, _ = solve(scheme+'-r1', cfg)
        assert max(r['endpoint_position'] for r in rows) > 0
        two, rows2, _ = solve(scheme+'-r2', cfg, ranks=2)
        assert error(one, two) < 2e-9
        for r, s in zip(rows, rows2):
            for k in ('endpoint_position', 'endpoint_velocity', 'evaluation_fluid_force'):
                assert abs(r[k]-s[k]) < 2e-9
        for stop in (2, 5):  # within startup, then within the periodic regime
            chk = a.work/f'checkpoint-{scheme}-{stop}'
            label = f'{scheme}-partial-{stop}'
            solve(label, cfg, ranks=2, extra=['-checkpoint', chk, '-stop_after', stop])
            original = (a.work/(label+'.pvd')).read_bytes()
            resumed, resumed_rows, _ = solve(label, cfg, ranks=2, extra=['-restart', chk], restart_step=stop)
            assert error(two, resumed) < 2e-9
            assert resumed_rows[0]['step'] == stop+1
            assert (a.work/(label+'.pvd')).read_bytes() == original
            changed = copy.deepcopy(cfg)
            changed['fsi']['pressure_time']['amplitude'] += .1
            solve(label+'-mismatch', changed, ranks=2, extra=['-restart', chk], fail='Checkpoint mesh/partition/physics mismatch')
    # Constant legacy path equals an explicitly constant waveform, including rigid FSI.
    for body in ('elastic', 'rigid'):
        cfg = copy.deepcopy(base)
        if body == 'rigid':
            cfg['fsi'].pop('domains')
            cfg['fsi']['body'] = body
            cfg['solver'].pop('fields')
        cfg['fsi'].pop('pressure_time')
        old, _, _ = solve(body+'-constant', cfg)
        cfg['fsi']['pressure_time'] = dict(amplitude=0, period=1)
        new, _, _ = solve(body+'-constant-profile', cfg)
        assert error(old, new) < 1e-13
    # Existing full-system Jacobian checker at a nonzero stage pressure.
    cfg = copy.deepcopy(base)
    cfg['time'] = dict(scheme='generalized_alpha')
    _, _, log = solve('jacobian', cfg, extra=['-stop_after', 3, '-snes_test_jacobian'])
    ratios = list(map(float, re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)', log)))
    assert ratios and max(ratios) < 1e-6, log[-4000:]
    # A rank-local piece failure must not strand peers or publish a PVD/PVTU.
    (a.work/'broken_step3_rank1.vtu').mkdir(exist_ok=True)
    solve('broken', ranks=2, fail='FSI piece write failed on rank 1')
    assert not (a.work/'broken.pvd').exists()
    assert not (a.work/'broken_step3.pvtu').exists()
    with (a.work/'broken.csv').open() as f:
        assert len(list(csv.DictReader(f))) == 2
    for key, value in [('period', 0), ('ramp_time', -1), ('amplitude', '.inf')]:
        cfg = copy.deepcopy(base)
        cfg['fsi']['pressure_time'][key] = value
        solve('invalid-'+key, cfg, fail='Invalid fsi.pressure_time')
    # Real nonlinear retries, followed by replay of exactly the accepted dt.
    for scheme in ('bdf2', 'generalized_alpha'):
        cfg = copy.deepcopy(base)
        cfg['time'] = dict(scheme=scheme)
        cfg['fsi'].update(material='neo_hookean', pressure=20, output_interval=1)
        cfg['fsi']['pressure_time'] = dict(amplitude=2, period=.02, ramp_time=.001)
        chk = a.work/('retry-'+scheme)
        solve('start-'+scheme, cfg, extra=['-checkpoint', chk, '-stop_after', 2])
        cfg['time_control'] = dict(max_retries=16, minimum_dt=1e-10, reduction=.5)
        actual, rows, log = solve('retry-'+scheme, cfg, extra=['-restart', chk, '-snes_max_it', 2, '-stop_after', 3], restart_step=2)
        assert 'step_retry=' in log and len(rows) == 1
        cfg['time_control']['step_sizes'] = [.004, .004, rows[0]['accepted_dt']]
        replay, _, _ = solve('replay-'+scheme, cfg, extra=['-stop_after', 3])
        assert error(actual, replay) < 2e-9
    print('FSI pressure state/history/MPI/Jacobian/retry checks passed', flush=True)


if __name__ == '__main__':
    main()
