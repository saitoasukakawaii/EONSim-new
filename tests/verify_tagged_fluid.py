"""Rotated/scaled channel: analytic affine flow, arbitrary tags, loads, MPI and restart."""
import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cases/fluid'))
from generate_rotated_channel import rotated_mesh, ORIGIN, EX, EY, LENGTHS, TAGS
p = argparse.ArgumentParser()
p.add_argument('--executable', type=Path, required=True)
p.add_argument('--mpiexec', required=True)
p.add_argument('--work', type=Path, required=True)
a = p.parse_args(); a.work.mkdir(parents=True, exist_ok=True)
mesh = a.work / 'rotated.msh'
# Preserve IDs above the exact double integer range through gauge parsing/checkpoint signatures.
first_node = 2**53 + 1
rotated_mesh(mesh, id_offset=first_node)
speed, pressure = .2, 2.
gradient = [[speed / LENGTHS[1] * EX[i] * EY[j] for j in range(3)] for i in range(3)]
velocity = dict(type='velocity', value=[0., 0., 0.], origin=ORIGIN, gradient=gradient)
base = dict(mesh=str(mesh.resolve()), output=str((a.work/'solution.vtu').resolve()),
            fluid=dict(mode='stokes', boundaries=[dict(copy.deepcopy(velocity), tag=t) for t in TAGS]),
            solver=dict(relative_tolerance=1e-10, absolute_tolerance=1e-12, maximum_iterations=30))
base['fluid']['boundaries'][1] = dict(tag=TAGS[1], type='traction',
    value=[speed/LENGTHS[1]*EY[i]-pressure*EX[i] for i in range(3)])

def run(args, error=None):
    r = subprocess.run([str(x) for x in args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=50)
    if error is None:
        if r.returncode or 'status=success' not in r.stdout: raise RuntimeError(r.stdout)
    elif r.returncode == 0 or error not in r.stdout:
        raise RuntimeError(f'Expected {error}:\n{r.stdout}')
    return r.stdout

def case_file(name, config):
    path = a.work/f'{name}.yaml'; path.write_text(json.dumps(config, indent=2).replace('Infinity', '.inf')); return path

def values(path, ranks):
    owned = {}; ghosts = []
    for rank in range(ranks):
        target = path if ranks == 1 else path.with_name(f'{path.stem}_rank{rank}.vtu')
        root = ET.parse(target)
        data = {x.attrib['Name']: x.text.split() for x in root.findall('.//PointData/DataArray')}
        coordinates = list(map(float, root.find('.//Points/DataArray').text.split()))
        for i, node in enumerate(data['mesh_node_id']):
            state = [float(v) for v in data['velocity'][3*i:3*i+3]] + [float(data['pressure'][i])]
            item = (state, coordinates[3*i:3*i+3])
            if int(data['owner'][i]) == rank:
                assert int(node) not in owned; owned[int(node)] = item
            else: ghosts.append((int(node), item))
    for node, (v, _) in ghosts: assert max(abs(x-y) for x,y in zip(v, owned[node][0])) < 2e-10
    return owned

def compare(x, y):
    assert x.keys() == y.keys()
    assert max(abs(v-w) for node in x for v,w in zip(x[node][0], y[node][0])) < 2e-9

def analytic(state, uniform=False):
    error = 0.
    for v, x in state.values():
        eta = sum(EY[d]*(x[d]-ORIGIN[d]) for d in range(3))
        exact = [speed*(1 if uniform else eta/LENGTHS[1])*d for d in EX] + [pressure]
        error = max(error, max(abs(u-w) for u,w in zip(v, exact)))
    assert error < 2e-9, error
    return error

def summary(text):
    rows = re.findall(r'boundary_tag=(\d+) area=(\S+) outward_flow=(\S+) mean_pressure=(\S+)', text)
    return {int(tag): tuple(map(float, values)) for tag, *values in rows}

case = case_file('traction', base)
partition = a.work/'partition2'
# Preprocessing prints its own success marker.
run([a.executable, '-case', case, '-prepare', partition, '-parts', 2])
for variant in ('traction', 'velocity_gauge', 'pressure'):
    config = copy.deepcopy(base)
    if variant == 'velocity_gauge':
        config['fluid']['boundaries'][1] = dict(velocity, tag=TAGS[1])
        config['fluid']['pressure_gauge'] = dict(node=first_node, value=pressure)
    elif variant == 'pressure':
        config['fluid']['boundaries'] = [dict(tag=t, type='velocity', value=[speed*d for d in EX]) for t in TAGS]
        config['fluid']['boundaries'][1] = dict(tag=TAGS[1], type='pressure', value=pressure)
    case = case_file(variant, config)
    outputs = []
    for ranks in (1, 2):
        path = a.work/f'{variant}{ranks}.vtu'
        prefix = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [a.executable, '-case', case]
        if ranks > 1: prefix += ['-partition', partition]
        text = run(prefix + ['-output', path]); state = values(path, ranks)
        err = analytic(state, variant == 'pressure'); outputs.append(state)
        rows = summary(text); flow = speed*LENGTHS[1]*LENGTHS[2]*(1 if variant == 'pressure' else .5)
        for tag, (area, flux, mean) in rows.items():
            expected_area = (LENGTHS[1]*LENGTHS[2], LENGTHS[0]*LENGTHS[2], LENGTHS[0]*LENGTHS[1])[TAGS.index(tag)//2]
            assert abs(area-expected_area) < 1e-12
            assert abs(flux-(-flow if tag == TAGS[0] else flow if tag == TAGS[1] else 0)) < 2e-10
            assert abs(mean-pressure) < 2e-9
        assert abs(float(re.search(r'net_outward_flow=(\S+)', text)[1])) < 2e-10
        assert float(re.search(r'divergence_l2=(\S+)', text)[1]) < 2e-9
        print(variant, ranks, 'analytic max error', err)
    compare(*outputs)

# A nonuniform traction exercises spatial load evaluation on the new surface path.
config = copy.deepcopy(base)
config['fluid']['boundaries'][1]['gradient'] = [[.03, 0, 0], [0, -.02, 0], [0, 0, .01]]
case = case_file('affine_traction', config)
outputs = []
for ranks in (1, 2):
    path = a.work/f'affine{ranks}.vtu'
    prefix = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [a.executable, '-case', case]
    if ranks > 1: prefix += ['-partition', partition]
    run(prefix + ['-output', path]); outputs.append(values(path, ranks))
compare(*outputs)

# Changing a boundary parameter must invalidate a checkpoint. Test time ramps and accepted-state continuation.
config = copy.deepcopy(base); config['fluid'].update(mode='transient', dt=.03, steps=4)
for b in config['fluid']['boundaries']: b['ramp_time'] = .09
case = case_file('transient', config)
for ranks in (1, 2):
    prefix = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [a.executable, '-case', case]
    if ranks > 1: prefix += ['-partition', partition]
    full, resumed, checkpoint = a.work/f'full{ranks}.vtu', a.work/f'resumed{ranks}.vtu', a.work/f'checkpoint{ranks}'
    run(prefix + ['-output', full])
    run(prefix + ['-checkpoint', checkpoint, '-stop_after', 2, '-output', a.work/'partial.vtu'])
    run(prefix + ['-restart', checkpoint, '-output', resumed])
    compare(values(full, ranks), values(resumed, ranks))
    changed = copy.deepcopy(config); changed['fluid']['boundaries'][1]['value'][0] += .1
    bad_case = case_file('changed', changed)
    bad_prefix = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [a.executable, '-case', bad_case]
    if ranks > 1: bad_prefix += ['-partition', partition]
    run(bad_prefix + ['-restart', checkpoint], 'Checkpoint mesh/partition/physics mismatch')

bad = []
c = copy.deepcopy(base); c['fluid']['boundaries'].pop(); bad.append((c, 'Missing condition'))
c = copy.deepcopy(base); c['fluid']['boundaries'].append(dict(velocity, tag=999)); bad.append((c, 'Configured boundary tag not found'))
c = copy.deepcopy(base); c['fluid']['boundaries'][2]['value'][0] = 1; bad.append((c, 'Conflicting velocity'))
c = copy.deepcopy(base); c['fluid']['pressure_gauge'] = dict(node=first_node, value=pressure); bad.append((c, 'Pressure gauge cannot accompany'))
c = copy.deepcopy(base); c['fluid']['boundaries'][1] = dict(velocity, tag=TAGS[1]); bad.append((c, 'All-velocity boundaries require'))
c = copy.deepcopy(base); c['fluid']['boundaries'][0]['gradient'] = [[0,0,0]]; bad.append((c, 'Boundary gradient requires'))
c = copy.deepcopy(base); c['fluid']['boundaries'][0]['value'] = [0,0,float('inf')]; bad.append((c, 'must be finite'))
c = copy.deepcopy(base); c['fluid']['boundaries'][1] = dict(copy.deepcopy(velocity), tag=TAGS[1]); c['fluid']['pressure_gauge'] = dict(node=first_node+1, value=pressure); bad.append((c, 'Pressure gauge must name'))
c = copy.deepcopy(base); c['fluid']['boundaries'] = [dict(tag=t, type='velocity', value=[0,0,0], gradient=[[1,0,0],[0,0,0],[0,0,0]]) for t in TAGS]; c['fluid']['pressure_gauge'] = dict(node=first_node, value=pressure); bad.append((c, 'Incompatible prescribed net boundary flux'))
c = copy.deepcopy(base); c['fluid'].update(mode='transient'); c['fluid']['boundaries'][0]['ramp_time'] = .1; bad.append((c, 'Conflicting velocity'))
for i, (config, error) in enumerate(bad):
    case = case_file(f'invalid{i}', config)
    run([a.executable, '-case', case], error)
    # Cross-rank failures must terminate, including a conflict found only by its owner.
    if i < 3: run([a.mpiexec, '-n', 2, a.executable, '-case', case, '-partition', partition], error)
print('tagged fluid verification passed')
