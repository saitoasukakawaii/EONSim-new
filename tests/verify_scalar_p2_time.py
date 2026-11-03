"""P2 diffusion: time order, distributed histories, conservation and failures."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cases/scalar2d'))
from generate import generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--checks', choices=('time', 'restart', 'failure'), required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    evidence = []

    def run(command, error=None):
        result = subprocess.run(list(map(str, command)), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=60)
        if error:
            assert result.returncode != 0 and error in result.stdout, result.stdout
        else:
            assert result.returncode == 0, result.stdout
        return result.stdout

    def case(label, scheme='bdf2', ranks=1, dt=.04, steps=8, change=None):
        folder = args.work / label
        path = generate(folder, 4, 'tri', '4.1', True, ranks == 2)
        cfg = json.loads(path.read_text())
        cfg['scalar2d'].update(degree=2, mode='diffusion', manufactured='quadratic',
                               manufactured_rate=-1, dt=dt, steps=steps)
        cfg['time'] = dict(scheme=scheme)
        if change:
            change(cfg)
        path.write_text(json.dumps(cfg))
        run([args.executable, '-case', path, '-prepare', folder / 'part', '-parts', ranks])
        return folder, path, ranks

    def solve(problem, extra=(), error=None, log='run.log'):
        folder, path, ranks = problem
        text = run([args.mpiexec, '-n', ranks, args.executable, '-case', path,
                    '-partition', folder / 'part', *extra], error)
        (folder / log).write_text(text)
        if error:
            return {}, [], text
        reports = [dict((k, float(v)) for k, v in
                        (entry.split('=') for entry in line.split()[1:]))
                   for line in text.splitlines() if line.startswith('scalar_p2 ')]
        assert reports and 'status=success' in text, text
        cfg = json.loads(path.read_text())['scalar2d']
        values = {}
        for rank in range(ranks):
            name = 'solution.vtu' if ranks == 1 else f'solution_rank{rank}.vtu'
            tree = ET.parse(folder / name)
            fields = {x.attrib['Name']: x.text.split() for x in tree.findall('.//PointData/DataArray')}
            assert set(tree.find('.//Cells/DataArray[@Name="types"]').text.split()) == {'22'}
            coords = list(map(float, tree.find('.//Points/DataArray').text.split()))
            for i in range(len(fields['u'])):
                x, y = coords[3*i:3*i+2]
                for boundary in cfg['boundaries']:
                    on_edge = {'left': abs(x)<1e-14, 'right': abs(x-1)<1e-14,
                               'bottom': abs(y)<1e-14, 'top': abs(y-1)<1e-14}[boundary['region']]
                    if on_edge and boundary['type'] == 'dirichlet':
                        if cfg.get('manufactured'):
                            expected = (1+x+2*y+x*x+2*y*y)*math.exp(-reports[-1]['time'])
                        else:
                            data = boundary['value']
                            terms = data['polynomial']
                            expected = sum(v*b for v,b in zip(terms, [1,x,y,x*x,x*y,y*y]))*math.exp(data.get('rate',0)*reports[-1]['time'])
                        assert abs(float(fields['u'][i])-expected) < 2e-9

            for i, owner in enumerate(fields['owner']):
                if int(owner) == rank:
                    key = (int(fields['entity_first'][i]), int(fields['entity_second'][i]))
                    assert key not in values
                    values[key] = [float(fields['u'][i])]
                    if 'algorithmic_rate' in fields:
                        values[key].append(float(fields['algorithmic_rate'][i]))
        assert len(values) == reports[-1]['dofs']
        evidence.append(dict(case=folder.name, ranks=ranks, **reports[-1]))
        return values, reports, text

    def compare(left, right, tolerance=2e-8):
        assert left.keys() == right.keys()
        assert all(len(left[k]) == len(right[k]) for k in left)
        difference = max(abs(v-w) for key in left for v, w in zip(left[key], right[key]))
        assert difference < tolerance, difference

    def snapshot(folder):
        return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.rglob('*') if p.is_file()}

    def check_series(folder, filename='solution.pvd', end=.32):
        entries = ET.parse(folder / filename).findall('.//DataSet')
        times = [float(x.attrib['timestep']) for x in entries]
        assert times == sorted(set(times)) and abs(times[-1]-end) < 1e-14
        for entry in entries:
            path = folder / entry.attrib['file']
            tree = ET.parse(path)
            for piece in tree.findall('.//Piece'):
                if 'Source' in piece.attrib:
                    assert (path.parent / piece.attrib['Source']).is_file()
        return times

    if args.checks == 'time':
        for scheme, rho in [('be', .5), ('bdf2', .5), ('generalized_alpha', 0),
                            ('generalized_alpha', .5), ('generalized_alpha', 1)]:
            previous = None
            for steps in (8, 16, 32):
                def options(cfg):
                    if scheme == 'generalized_alpha':
                        cfg['time']['rho_infinity'] = rho
                problem = case(f'order-{scheme}-{rho}-{steps}', scheme, dt=.32/steps,
                               steps=steps, change=options)
                values, reports, _ = solve(problem)
                report = reports[-1]
                if previous:
                    order = math.log(previous / report['l2_error'], 2)
                    evidence[-1]['l2_order'] = order
                    assert order > (.85 if scheme == 'be' else 1.7), (scheme, rho, order, report)
                previous = report['l2_error']
            parallel = case(f'order-{scheme}-{rho}-mpi', scheme, ranks=2,
                            dt=.01, steps=32, change=options)
            fields, _, _ = solve(parallel)
            compare(values, fields)
            check_series(parallel[0])
        previous = None
        for steps in (8, 16, 32):
            def alternating(cfg):
                h = .32/steps
                cfg['time_control'] = dict(step_sizes=[.75*h, 1.25*h]*(steps//2))
            _, reports, _ = solve(case(f'variable-order-{steps}', dt=.32/steps,
                                       steps=steps, change=alternating))
            error = reports[-1]['l2_error']
            if previous:
                order = math.log(previous/error, 2)
                evidence[-1]['l2_order'] = order
                assert order > 1.7, (steps, order)
            previous = error
        for scheme in ('be', 'bdf2', 'generalized_alpha'):
            for ranks in (1, 2):
                def insulated(cfg):
                    c = cfg['scalar2d']
                    c.pop('manufactured'); c.pop('manufactured_rate')
                    c.update(source=1, initial=2, capacity=2)
                    for b in c['boundaries']:
                        b.update(type='neumann', value=0); b.pop('coefficient', None)
                fields, reports, _ = solve(case(f'mass-{scheme}-{ranks}', scheme, ranks, change=insulated))
                assert max(abs(v[0]-2.16) for v in fields.values()) < 2e-9
                assert abs(reports[-1]['integral']-2.16) < 2e-9
        # Explicit exponential polynomial data exercises the user boundary path.
        def robin_user(cfg):
            c = cfg['scalar2d'];c.pop('manufactured');c.pop('manufactured_rate')
            c['initial'] = {'polynomial': [1, 1, 2, 1, 0, 2]}
            c['source'] = {'polynomial': [-7, -1, -2, -1, 0, -2], 'rate': -1}
            data = {'left': [1,2,4,2,0,4], 'right': [5,2,4,2,0,4],
                    'bottom': [0,2,4,2,0,4], 'top': [8,2,4,2,0,4]}
            for b in c['boundaries']:
                b.update(type='robin', coefficient=2,
                         value={'polynomial': data[b['region']], 'rate': -1})
        def robin_exact(cfg):
            for b in cfg['scalar2d']['boundaries']:
                b.update(type='robin', coefficient=2)
        user, _, _ = solve(case('robin-user', ranks=2, change=robin_user))
        exact, _, _ = solve(case('robin-exact', ranks=2, change=robin_exact))
        compare(user, exact)
        def mixed_user(cfg):
            robin_user(cfg)
            for b in cfg['scalar2d']['boundaries']:
                if b['region'] in ('left', 'bottom'):
                    b.update(type='dirichlet', value={'polynomial': [1,1,2,1,0,2], 'rate': -1})
                    b.pop('coefficient')
                elif b['region'] == 'top':
                    b.update(type='neumann', value={'polynomial': [6,0,0,0,0,0], 'rate': -1})
                    b.pop('coefficient')
        user, _, _ = solve(case('mixed-user', 'generalized_alpha', ranks=2, change=mixed_user))
        exact, _, _ = solve(case('mixed-exact', 'generalized_alpha', ranks=2))
        compare(user, exact)
    elif args.checks == 'restart':
        for scheme in ('be', 'bdf2', 'generalized_alpha'):
            for ranks in (1, 2):
                def variable(cfg):
                    cfg['time_control'] = dict(step_sizes=[.03, .05, .02, .04], events=[.08])
                problem = case(f'{scheme}-{ranks}', scheme, ranks, change=variable)
                expected, reports, _ = solve(problem)
                assert any(abs(r['time']-.08) < 1e-14 for r in reports)
                after_event = next(r for r in reports if r['time'] > .08+1e-14)
                assert after_event['time_order'] == 1
                original = {p.name: p.read_bytes() for p in problem[0].glob('solution_step*')}
                original['solution.pvd'] = (problem[0]/'solution.pvd').read_bytes()
                for stop in (2, 4):
                    partial = case(f'{scheme}-{ranks}-partial{stop}', scheme, ranks, change=variable)
                    checkpoint = (partial[0]/'checkpoint').resolve()
                    solve(partial, ['-checkpoint', checkpoint, '-stop_after', stop])
                    restored, _, _ = solve(problem, ['-restart', checkpoint], log=f'restart{stop}.log')
                    compare(expected, restored)
                    assert all((problem[0]/name).read_bytes() == data for name, data in original.items())
                    check_series(problem[0], f'solution_restart{stop}.pvd')
                # Different physical capacity and missing rank file must fail collectively.
                cfg = json.loads(problem[1].read_text());cfg['scalar2d']['capacity'] = 2
                problem[1].write_text(json.dumps(cfg))
                solve(problem, ['-restart', checkpoint], error='Checkpoint mesh/partition/physics mismatch', log='mismatch.log')
                cfg['scalar2d'].pop('capacity');problem[1].write_text(json.dumps(cfg))
                generation = (checkpoint/'current').read_text().split()[1]
                missing = checkpoint/generation/f'state_rank{ranks-1}.h5'
                missing.rename(missing.with_suffix('.saved'))
                solve(problem, ['-restart', checkpoint], error='Missing checkpoint rank file', log='missing.log')
    else:
        for scheme in ('be', 'bdf2', 'generalized_alpha'):
            for ranks in (1, 2):
                def retry(cfg):
                    cfg['time_control'] = dict(max_retries=12, minimum_dt=1e-9)
                problem = case(f'{scheme}-{ranks}', scheme, ranks, change=retry)
                checkpoint = (problem[0]/'checkpoint').resolve()
                solve(problem, ['-checkpoint', checkpoint, '-stop_after', 2])
                before = snapshot(checkpoint)
                published = {p.name: p.read_bytes() for p in problem[0].glob('solution*') if p.is_file()}
                solve(problem, ['-restart', checkpoint, '-checkpoint', checkpoint, '-ksp_max_it', 0],
                      error='Time-step retries exhausted', log='exhausted.log')
                assert snapshot(checkpoint) == before
                assert all((problem[0]/name).read_bytes() == data for name, data in published.items())
                # An actual iteration budget forces rejection; reduced dt changes
                # the mass/stiffness balance and permits a subsequent solve.
                fields, reports, text = solve(problem, ['-restart', checkpoint, '-ksp_max_it', 20,
                                                        '-stop_after', 3], log='retry.log')
                assert 'step_retry=' in text, text
                h = reports[-1]['accepted_dt']
                def replay(cfg):
                    retry(cfg);cfg['time_control']['step_sizes'] = [.04, .04, h]
                direct, _, _ = solve(case(f'replay-{scheme}-{ranks}', scheme, ranks, change=replay),
                                     ['-stop_after', 3])
                compare(fields, direct)
                assert snapshot(checkpoint) == before
                check_series(problem[0], 'solution_restart2.pvd', .08+h)
        # A rank-local piece failure must not publish a PVTU or PVD or hang.
        broken = case('piece-failure', ranks=2)
        (broken[0]/'solution_rank1.vtu.tmp').mkdir(exist_ok=True)
        solve(broken, error='P2 piece write failed on rank 1', log='io-error.log')
        assert not (broken[0]/'solution.pvtu').exists()
        assert not (broken[0]/'solution.pvd').exists()
    (args.work/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
