"""Check frozen tube elimination, owner/ghost slots and constant-pressure actions on saved AIJ."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
from refine_system import DATA, FIELDS, finite, matrix, norm, sha, vector


def partition_arrays(path, h5dump):
    names = ('meta', 'node_ids', 'owners', 'boundary_offsets', 'boundary_tags',
             'region_offsets', 'region_tags')
    try:
        import h5py
    except ImportError:
        # Existing HDF5 CLI; only seven small integer datasets from one rank at a time.
        command = [h5dump, '-y', '-w', '0']
        for name in names:
            command.extend(['-d', name])
        text = subprocess.check_output([*command, str(path)], text=True)
        blocks = re.findall(r'DATASET\s+"([^"]+)"\s*\{.*?\bDATA\s*\{([^}]*)\}', text, re.S)
        arrays = {name.strip('/'): np.fromstring(data.strip(), dtype=np.int64, sep=',')
                  for name, data in blocks}
        if arrays.keys() != set(names):
            raise ValueError(f'Incomplete h5dump result for {path}')
        return arrays
    with h5py.File(path) as h5:
        return {key: h5[key][:] for key in names}


def has_tag(part, group, tag):
    offsets, tags = part[group+'_offsets'], part[group+'_tags']
    if offsets[0] or offsets[-1] != len(tags) or np.any(np.diff(offsets) < 0):
        raise ValueError(f'Invalid {group} CSR')
    nodes = np.repeat(np.arange(len(offsets)-1), np.diff(offsets))
    result = np.zeros(len(offsets)-1, dtype=bool)
    result[nodes[tags == tag]] = True
    return result


def physical_slots(part, fsi):
    d = fsi['domains']
    fluid = has_tag(part, 'region', d['fluid_region'])
    solid = has_tag(part, 'region', d['solid_region'])
    interface = fluid & solid
    if not np.all(fluid | solid):
        raise ValueError('Joined partition includes a third physical region')
    free = np.zeros((len(fluid), 10), dtype=bool)
    free[:, :7] = fluid[:, None]
    free[:, 7:] = solid[:, None]
    for field, offset, tag in [('fluid', 0, 'fluid_interface'), ('mesh', 4, 'fluid_interface'),
                               ('solid', 7, 'solid_interface')]:
        for bc in d.get(field+'_constraints', []):
            nodes = interface if bc['tag'] == d[tag] else has_tag(part, 'boundary', bc['tag'])
            free[np.ix_(nodes, np.asarray(bc['components']) + offset)] = False
    inlet = has_tag(part, 'boundary', fsi['inlet']['tag'])
    free[inlet, :3] = False
    free[inlet, 4:7] = False
    if np.any((~free[:, :3] | ~free[:, 4:7]) & free[:, 7:] & interface[:, None]):
        raise ValueError('Fixed fluid/mesh slot on a free structural interface component')
    # The mesh trial uses the structure master times mesh_dt; the mesh test slot
    # contributes no interface equation. Fluid and structure share that row.
    free[interface, :3] = False
    free[interface, 4:7] = False
    return free, interface, inlet


def inspect_layout(fsi, shards, partition, sizes, port, h5dump, report):
    field_by_slot = np.array([1, 1, 1, 2, 0, 0, 0, 3, 3, 3])
    comp_by_slot = np.array([0, 1, 2, 0, 0, 1, 2, 0, 1, 2])
    ranks, n = sizes
    fields = np.full(n, -1, dtype=np.int8)
    first = total_inlet = eliminated = trace_aliases = 0
    ghosts = 0
    node_copies = []
    for rank in range(ranks):
        part = partition_arrays(partition/f'rank_{rank}.h5', h5dump)
        ver, actual_rank, size, own, _, nodes, _ = map(int, part['meta'])
        if (ver, actual_rank, size) != (2, rank, ranks):
            raise ValueError('Invalid rank metadata')
        if rank == 0:
            canonical = np.full((nodes+1, 10), -2, dtype=np.int32)
            owners = np.full(nodes+1, -1, dtype=np.int32)
            boundary = np.zeros(nodes+1, dtype=bool)
        ids = part['node_ids']
        if (nodes+1 != len(owners) or np.any(ids<1) or np.any(ids>nodes) or
                len(np.unique(ids)) != len(ids) or np.any(part['owners'][:own] != rank)
                or np.any(part['owners'][own:] == rank) or np.any(owners[ids[:own]] != -1)):
            raise ValueError('Invalid node or ownership ordering')
        free, interface, inlet = physical_slots(part, fsi)
        local_nodes, cols = np.nonzero(free[:own])
        stop = first+len(cols)
        owner_slots = np.full((own, 10), -1, dtype=np.int32)
        owner_slots[local_nodes, cols] = np.arange(first, stop)
        mask = interface[:own]
        owner_slots[mask, :3] = owner_slots[mask, 7:]
        owner_slots[mask, 4:7] = owner_slots[mask, 7:]
        canonical[ids[:own]] = owner_slots
        owners[ids[:own]] = rank
        boundary[ids[:own]] = mask
        node_copies.append((ids, part['owners']))
        total_inlet += int(inlet[:own].sum())
        eliminated += int(np.count_nonzero(owner_slots == -1))
        trace_aliases += int(2*np.count_nonzero(owner_slots[mask, 7:] >= 0))
        ghosts += len(ids)-own
        fields[first:stop] = field_by_slot[cols]
        checked = np.zeros(len(cols) + int(rank == ranks-1), dtype=bool)
        with (shards/f'rows-{rank}.csv').open() as stream:
            for row in csv.DictReader(stream):
                global_row = int(row['row'])
                idx = global_row-first
                if idx < 0 or idx >= len(checked) or checked[idx]:
                    raise ValueError(f'Duplicate or incorrect owner row {global_row}')
                checked[idx] = True
                if idx == len(cols):
                    if global_row != int(port['pressure_row']) or global_row != n-1:
                        raise ValueError('Boundary row index differs')
                    expected = ('pressure', int(port['tag']), 3, 0, 0)
                    fields[global_row] = FIELDS.index('RCR')
                else:
                    j, col = local_nodes[idx], cols[idx]
                    expected = (FIELDS[field_by_slot[col]], int(ids[j]), 0,
                                int(comp_by_slot[col]), int(interface[j]))
                actual = (row['field'], *(int(row[k]) for k in ('entity', 'kind', 'component', 'interface')))
                if actual != expected:
                    raise ValueError(f'Owner {rank} row {global_row} has {actual}, expected {expected}')
        if not checked.all():
            raise ValueError('Missing owner row or RCR boundary row')
        first = stop
    if first+1 != n or np.any(owners[1:] < 0) or np.any(fields < 0):
        raise ValueError('Physical slots do not reconstruct all reduced rows')
    for rank, (ids, local_owners) in enumerate(node_copies):
        actual = np.loadtxt(shards/f'slots-{rank}.csv', delimiter=',', skiprows=1, dtype=np.int64, ndmin=2)
        if not len(ids) and not actual.size:
            continue
        if (actual.shape != (len(ids), 13) or not np.array_equal(actual[:, 0], ids)
                or not np.array_equal(actual[:, 1], local_owners)
                or not np.array_equal(actual[:, 1], owners[ids])
                or not np.array_equal(actual[:, 2], boundary[ids])
                or not np.array_equal(actual[:, 3:], canonical[ids])):
            raise ValueError(f'Rank {rank} exported slots differ from independently reconstructed owner map')
    report.update(nodes=len(owners)-1, ghost_node_copies=int(ghosts), inlet_nodes=total_inlet,
                  interface_nodes=int(boundary.sum()), eliminated_slots=eliminated,
                  interface_alias_slots=trace_aliases, port_owner=ranks-1)
    return fields


def inspect_matrix(a, b, f):
    n = len(b)
    p = ((f == FIELDS.index('pressure')) | (f == FIELDS.index('RCR'))).astype(float)
    right = finite(a @ p)
    left = finite(a.T @ p)
    row_abs, col_abs = np.empty(n), np.zeros(n)
    for i in range(0, n, 8192):
        block = abs(a[i:i+8192])
        row_abs[i:i+block.shape[0]] = np.asarray(block.sum(axis=1)).ravel()
        col_abs += np.asarray(block.sum(axis=0)).ravel()
    finite(row_abs)
    finite(col_abs)
    def scale(values):
        return [float(np.min(values)), float(np.median(values)), float(np.max(values))]
    return dict(pressure_and_port_entries=int(p.sum()), right_norm=norm(right), left_norm=norm(left),
                port_right=float(right[-1]), port_left=float(left[-1]), left_rhs_dot=float(p@b),
                port_rhs=float(b[-1]), port_diagonal=float(a[-1,-1]),
                fields={name: dict(rows=int((f==k).sum()), right_norm=norm(right[f==k]),
                                   left_norm=norm(left[f==k]), row_l1_min_median_max=scale(row_abs[f==k]),
                                   column_l1_min_median_max=scale(col_abs[f==k])) for k,name in enumerate(FIELDS)})


def run(args, report):
    old = args.archive
    tube = args.tube
    bcase = tube == 'B'
    system = old/('B-system/lu-refined' if bcase else 'C-first-64')
    layout = old/(tube+'-layout')
    ranks = 32 if bcase else 64
    expected_n = 101085 if bcase else 924953
    partition = old/'B-system/partition' if bcase else old.parent/'fsi-scalable-02-runs/C20-fixed/partition'
    receipt = old/('B-system/summary.json' if bcase else 'C-first-64/diagnosis.json')
    index = json.loads((DATA/'fsi-scalable-03/log-index.json').read_text())
    raw = [receipt, system/'operator.petsc', system/'rhs.petsc', *sorted(layout.glob('*.csv'))]
    for path in raw:
        key = '$HOME/' + path.resolve().relative_to(Path.home()).as_posix()
        if sha(path) != index[key]['sha256']:
            raise ValueError(f'Changed original record {path}')
    previous = json.loads(receipt.read_text())
    if previous['inputs']['case.json'] != sha(system/'case.json'):
        raise ValueError('Frozen input changed')
    report.update(operator_sha256=sha(raw[1]), rhs_sha256=sha(raw[2]), original_receipt_sha256=sha(receipt),
                  binary_sha256=previous['binary'], source_job=previous['slurm'] if bcase else previous['job'],
                  case_sha256=previous['inputs']['case.json'])
    report['partition_sha256'] = {p.name: sha(p) for p in sorted(partition.iterdir()) if p.is_file()}
    if not bcase and report['partition_sha256'] != previous['partition']:
        raise ValueError('C partition differs from archived solve')
    fsi = json.loads((system/'case.json').read_text())['fsi']
    with (layout/'port.csv').open() as stream:
        port, = csv.DictReader(stream)
    rcr = fsi['domains']['rcr_outlet']
    if (int(port['rows']) != expected_n or int(port['tag']) != rcr['tag']
            or float(port['dt']) != fsi['dt'] or float(port['initial_capacitor_pressure']) != rcr['initial_capacitor_pressure']):
        raise ValueError('Frozen circuit and exported port disagree')
    fields = inspect_layout(fsi, layout, partition, (ranks, expected_n), port, args.h5dump, report)
    a, b = matrix(system/'operator.petsc'), finite(vector(system/'rhs.petsc'))
    if a.shape != (expected_n, expected_n) or b.shape != (expected_n,):
        raise ValueError('Inconsistent PETSc dimensions')
    report['constant_pressure'] = inspect_matrix(a, b, fields)
    report['scope'] = 'reduced ownership, eliminated slots, port and fixed pressure-direction test on first system'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('tube', choices=('B','C'))
    cli.add_argument('--archive', type=Path, default=Path.home()/'workspace/fsi-scalable-03-runs')
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--h5dump', default='h5dump', help='fallback executable when h5py is unavailable')
    args = cli.parse_args()
    start = time.perf_counter()
    report = dict(tube=args.tube, job=os.environ.get('SLURM_JOB_ID'), script_sha256=sha(Path(__file__)),
                  options=sys.argv[1:], status='FAILED')
    try:
        run(args, report)
        report['status'] = 'PASS_LAYOUT_AUDIT'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['seconds'] = time.perf_counter()-start
        with args.output.open('x') as stream:
            json.dump(report, stream, allow_nan=False, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
