"""Uniform accelerating flow: exact discrete oracle for a sinusoidal traction.

Slip sides eliminate spatial error. The pressure is affine and velocity uniform,
so BE/BDF2/alpha can be checked against their scalar momentum recurrence without
using a fine-step FEM result as the oracle. Includes MPI, cadence and restart.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'cases/poisson'))
from generate_mesh import write_mesh


def pressure(time, mean=0.):
    x = min(max(time/.09, 0.), 1.)
    return x**3*(10-15*x+6*x*x)*(mean+.2*math.sin(2*math.pi*time/.4))


def expected(scheme, steps=11, h=.037):
    previous = velocity = rate = p = 0.
    for step in range(1, steps+1):
        if scheme == 'generalized_alpha' and step > 1:
            am, af, gamma = 5/6, 2/3, 2/3  # rho_infinity = .5, new-time weights
            stage_p = pressure((step-1+af)*h)
            next_rate = (stage_p-(1-am)*rate)/am
            next_velocity = velocity+h*((1-gamma)*rate+gamma*next_rate)
            p = (stage_p-(1-af)*p)/af
            rate = next_rate
        else:
            p = pressure(step*h)
            next_velocity = ((2*velocity-.5*previous+h*p)/1.5
                             if scheme == 'bdf2' and step > 1 else velocity+h*p)
            rate = (next_velocity-velocity)/h
        previous, velocity = velocity, next_velocity
    return velocity, p


def fields(path, ranks):
    owned, ghosts = {}, []
    for rank in range(ranks):
        piece = path if ranks == 1 else path.with_name(path.stem+f'_rank{rank}.vtu')
        tree = ET.parse(piece)
        arrays = {v.attrib['Name']: v.text.split() for v in tree.findall('.//PointData/DataArray')}
        coordinates = list(map(float, tree.find('.//Points/DataArray').text.split()))
        for i, node in enumerate(arrays['mesh_node_id']):
            value = tuple(map(float, arrays['velocity'][3*i:3*i+3]+[arrays['pressure'][i]]))
            assert all(math.isfinite(v) for v in value)
            node = int(node)
            if int(arrays['owner'][i]) == rank:
                assert node not in owned
                owned[node] = (value, coordinates[3*i])
            else:
                ghosts.append((node, value))
    for node, value in ghosts:
        assert max(abs(x-y) for x,y in zip(value, owned[node][0])) < 2e-9
    return owned


def difference(a, b):
    assert a.keys() == b.keys()
    return max(abs(x-y) for node in a for x,y in zip(a[node][0], b[node][0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True, type=Path)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='run-', dir=args.work)).resolve()
    mesh = work/'cube.msh'
    write_mesh(mesh, 2)
    boundaries = []
    for tag in (1, 2):
        boundaries += [dict(tag=tag, type='pressure', value=0., components=[0]),
                       dict(tag=tag, type='velocity', value=[0,0,0], components=[1,2])]
    boundaries[0]['pressure_time'] = dict(amplitude=.2, period=.4, ramp_time=.09)
    boundaries += [dict(tag=tag, type='velocity', value=[0,0,0], components=[component])
                   for tag,component in ((3,1),(4,1),(5,2),(6,2))]
    base = dict(mesh=str(mesh), fluid=dict(mode='transient', density=1, viscosity=1,
                dt=.037, steps=11, boundaries=boundaries, checkpoint_interval=4),
                solver=dict(relative_tolerance=1e-11, absolute_tolerance=1e-13, maximum_iterations=30))

    def command(argv, log, failure=None):
        result = subprocess.run(list(map(str,argv)), text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=90)
        log.write_text(result.stdout)
        if failure is not None:
            assert result.returncode and failure in result.stdout and 'status=success' not in result.stdout, result.stdout[-6000:]
        elif result.returncode or 'status=success' not in result.stdout:
            raise RuntimeError(result.stdout[-6000:])
        return result.stdout

    def solve(name, config, ranks=1, extra=(), failure=None, checkpoint=False):
        directory = work/name
        directory.mkdir()
        cfg = copy.deepcopy(config)
        output = directory/'solution.vtu'
        cfg['output'] = str(output)
        case = directory/'case.json'
        case.write_text(json.dumps(cfg, indent=2)+'\n')
        argv = [args.executable.resolve(), '-case', case]
        if ranks > 1:
            partition = work/f'parts{ranks}'
            if not partition.exists():
                command(argv+['-prepare',partition,'-parts',ranks],directory/'prepare.log')
            argv = [args.mpiexec,'-n',ranks]+argv+['-partition',partition]
        if checkpoint:
            argv += ['-checkpoint',directory/'checkpoint']
        text = command(argv+list(extra), directory/'solve.log', failure)
        if failure is not None:
            return None, directory
        state = fields(output, ranks)
        assert abs(float(re.search(r'net_outward_flow=(\S+)',text)[1])) < 1e-10
        return state, directory

    report = []
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg = copy.deepcopy(base)
        cfg['time'] = dict(scheme=scheme)
        if scheme == 'generalized_alpha':
            cfg['time']['rho_infinity'] = .5
        serial = None
        for ranks in (1,2,4):
            state, directory = solve(f'{scheme}-r{ranks}',cfg,ranks,checkpoint=True)
            velocity, p = expected(scheme)
            error = max(max(abs(a-b) for a,b in zip(v,(velocity,0.,0.,p*(1-x)))) for v,x in state.values())
            assert error < 2e-9, (scheme,ranks,error)
            serial = serial or state
            delta = difference(serial,state)
            assert delta < 2e-9
            manifests = [p.read_text().split() for p in (directory/'checkpoint').glob('generation_*/manifest')]
            assert sorted(int(m[2]) for m in manifests) == [4,8,11]
            assert all(abs(float(m[3])-int(m[2])*.037)<1e-14 for m in manifests)
            report.append(dict(scheme=scheme,ranks=ranks,discrete_oracle_error=error,mpi_difference=delta))
        _, partial = solve(scheme+'-partial',cfg,2,['-stop_after',5],checkpoint=True)
        checkpoint = partial/'checkpoint'
        assert sorted(int(p.read_text().split()[2]) for p in checkpoint.glob('generation_*/manifest')) == [4,5]
        resumed, _ = solve(scheme+'-resume',cfg,2,['-restart',checkpoint])
        assert difference(serial,resumed) < 2e-9
        for key in ('amplitude','period','ramp_time'):
            changed = copy.deepcopy(cfg)
            changed['fluid']['boundaries'][0]['pressure_time'][key] += .01
            solve(scheme+'-changed-'+key,changed,2,['-restart',checkpoint],failure='Checkpoint mesh/partition/physics mismatch')

    for name, mutate, message in (
        ('period',lambda c:c['fluid']['boundaries'][0]['pressure_time'].update(period=0),'Invalid fluid.boundaries.pressure_time'),
        ('ramp',lambda c:c['fluid']['boundaries'][0].update(ramp_time=0),'Use pressure_time.ramp_time'),
        ('steady',lambda c:c['fluid'].update(mode='stokes'),'Boundary pressure_time requires transient fluid'),
        ('cadence',lambda c:c['fluid'].update(checkpoint_interval=0),'fluid.checkpoint_interval must be positive'),
        ('velocity',lambda c:c['fluid']['boundaries'][1].update(pressure_time=dict(amplitude=1,period=1)),'Unknown key:'),
    ):
        cfg = copy.deepcopy(base)
        mutate(cfg)
        solve('invalid-'+name,cfg,failure=message)
    (work/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(work=str(work),states=report,checks='cadence/restart/profile mismatch/input rejection passed')))


if __name__ == '__main__':
    main()
