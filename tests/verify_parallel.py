"""P1: offline partitions, local-only input, owner/ghost and 1/2 rank agreement."""
import argparse
from collections import Counter
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

def require(condition, message):
    if not condition: raise RuntimeError(message)

def mesh_piece(path):
    """Read geometry/identity evidence independently of the partition files."""
    piece = ET.parse(path).find('.//Piece')
    require(piece is not None, f'Missing mesh piece: {path}')
    arrays = {a.attrib['Name']: (a.text or '').split()
              for a in piece.findall('./PointData/DataArray')}
    nodes = list(map(int, arrays['mesh_node_id']))
    owners = list(map(int, arrays['owner']))
    algebra = list(map(int, arrays['algebra_node_id']))
    xyz = list(map(float, (piece.find('./Points/DataArray').text or '').split()))
    require(len(nodes) == len(set(nodes)) == int(piece.attrib['NumberOfPoints'])
            and len(owners) == len(nodes) and len(algebra) == len(nodes)
            and len(xyz) == 3*len(nodes), f'Invalid node records: {path}')
    data = {a.attrib['Name']: list(map(int, (a.text or '').split()))
            for a in piece.findall('./CellData/DataArray')}
    cell_arrays = {a.attrib['Name']: list(map(int, (a.text or '').split()))
                   for a in piece.findall('./Cells/DataArray')}
    ids, tags = data['mesh_element_id'], data['physical_tag']
    offsets, connectivity = cell_arrays['offsets'], cell_arrays['connectivity']
    require(len(ids) == len(set(ids)) == int(piece.attrib['NumberOfCells'])
            and len(tags) == len(ids) == len(offsets), f'Invalid cell records: {path}')
    cells, start = {}, 0
    for cell, tag, end in zip(ids, tags, offsets):
        require(start < end <= len(connectivity), f'Invalid cell offset: {path}')
        local_nodes = connectivity[start:end]
        require(all(0 <= node < len(nodes) for node in local_nodes), f'Invalid cell node: {path}')
        cells[cell] = (tuple(nodes[node] for node in local_nodes), tag)
        start = end
    require(start == len(connectivity), f'Trailing cell connectivity: {path}')
    return dict(nodes=nodes, owners=owners, algebra=algebra, cells=cells,
                coordinates={node: tuple(xyz[3*i:3*i+3]) for i,node in enumerate(nodes)})

def verify_partition_layout(serial_path, parallel_path, ranks, cell_tags=None):
    """Reconstruct owner/numbering and boundary placement from full Tet4 topology.

    The existing serial and MPI solves supply all observations; no extra solve
    or HDF5 implementation is used by this check.
    """
    serial = mesh_piece(serial_path)
    if cell_tags is not None:
        serial['cells'] = {cell: (nodes, cell_tags[cell]) for cell,(nodes,_) in serial['cells'].items()}
    boundary = mesh_piece(serial_path.with_name(serial_path.stem+'_boundary.vtu'))
    pieces = [mesh_piece(parallel_path.with_name(f'{parallel_path.stem}_rank{rank}.vtu'))
              for rank in range(ranks)]
    cell_owner = {}
    for rank, piece in enumerate(pieces):
        for cell, topology in piece['cells'].items():
            require(cell in serial['cells'] and topology == serial['cells'][cell],
                    f'Partition changed cell connectivity or physical tag: {cell}')
            require(cell not in cell_owner, f'Duplicate partition cell: {cell}')
            cell_owner[cell] = rank
    require(cell_owner.keys() == serial['cells'].keys(), 'Partition lost a source cell')
    node_owner = {node: min(cell_owner[cell] for cell, (nodes, _) in serial['cells'].items()
                            if node in nodes) for node in serial['nodes']}
    node_order = {node: index for index,node in enumerate(serial['nodes'])}
    algebra = {node: index for index,node in enumerate(sorted(serial['nodes'],
               key=lambda node: (node_owner[node], node_order[node])))}
    face_cells = {}
    for cell, (nodes, _) in serial['cells'].items():
        require(len(nodes) == 4, 'Partition oracle expects Tet4 cells')
        for omitted in range(4):
            key = tuple(sorted(nodes[:omitted]+nodes[omitted+1:]))
            face_cells.setdefault(key, []).append(cell)
    face_owner = {}
    for face, (nodes, _) in boundary['cells'].items():
        adjacent = face_cells.get(tuple(sorted(nodes)), [])
        require(len(adjacent) == 1, f'Boundary face is not exterior: {face}')
        face_owner[face] = cell_owner[adjacent[0]]
    for rank, piece in enumerate(pieces):
        expected_cells = [cell for cell in serial['cells'] if cell_owner[cell] == rank]
        needed = {node for cell in expected_cells for node in serial['cells'][cell][0]}
        expected_nodes = sorted(needed, key=lambda node: (node_owner[node] != rank, node_order[node]))
        require(piece['nodes'] == expected_nodes, f'Owned/ghost node order changed on rank {rank}')
        require(list(piece['cells']) == expected_cells, f'Cell input order changed on rank {rank}')
        require(piece['owners'] == [node_owner[node] for node in expected_nodes], 'Node owner mismatch')
        require(piece['algebra'] == [algebra[node] for node in expected_nodes], 'Algebra numbering mismatch')
        require(all(piece['coordinates'][node] == serial['coordinates'][node] for node in needed),
                'Partition changed node coordinates')
        face_piece = mesh_piece(parallel_path.with_name(f'{parallel_path.stem}_rank{rank}_boundary.vtu'))
        expected_faces = [face for face in boundary['cells'] if face_owner[face] == rank]
        require(list(face_piece['cells']) == expected_faces, f'Boundary input order/owner changed on rank {rank}')
        require(all(face_piece['cells'][face] == boundary['cells'][face] for face in expected_faces),
                'Partition changed boundary orientation or physical tag')

def verify_prepare_report(log, output, ranks, weights):
    def records(prefix):
        return [dict(token.split('=', 1) for token in line.split()[1:])
                for line in log.splitlines() if line.startswith(prefix+' ')]
    totals, rank_rows, tag_rows = records('partition_report'), records('partition_rank'), records('partition_tag')
    require(len(totals) == 1 and len(rank_rows) == ranks, 'Missing/duplicate partition report')
    total = totals[0]
    require(int(total['ranks']) == ranks and int(total['weighted']) == bool(weights), 'Incorrect partition report mode')
    times = {key: float(total[key]) for key in ('total_seconds', 'metis_seconds', 'layout_seconds', 'write_seconds')}
    require(all(math.isfinite(value) and value >= 0 for value in times.values()), 'Invalid partition timer')
    require(math.isclose(times['total_seconds'], times['metis_seconds']+times['layout_seconds']+times['write_seconds'],
                         rel_tol=1e-10, abs_tol=1e-9), 'Partition timer scopes do not cover total')
    by_rank = {int(row['rank']): row for row in rank_rows}
    require(set(by_rank) == set(range(ranks)), 'Partition report rank coverage mismatch')
    reported_tags = {(int(row['rank']), int(row['tag'])): int(row['cells']) for row in tag_rows}
    require(len(reported_tags) == len(tag_rows), 'Duplicate partition tag report')
    expected_tags, cost = {}, 0
    for rank in range(ranks):
        path = output if ranks == 1 else output.with_name(f'{output.stem}_rank{rank}.vtu')
        piece = mesh_piece(path)
        boundary = mesh_piece(path.with_name(path.stem+'_boundary.vtu'))
        counts = Counter(tag for _, tag in piece['cells'].values())
        local_cost = sum(weights.get(tag, 1)*count for tag,count in counts.items())
        owned = sum(owner == rank for owner in piece['owners'])
        expected = dict(cells=len(piece['cells']), nodes=len(piece['nodes']), owned=owned,
                        ghost=len(piece['nodes'])-owned, faces=len(boundary['cells']), weighted_cost=local_cost)
        require(all(int(by_rank[rank][key]) == value for key,value in expected.items()),
                f'Partition report differs from saved topology on rank {rank}')
        expected_tags.update({(rank, tag): count for tag,count in counts.items()})
        cost += local_cost
    require(reported_tags == expected_tags and int(total['total_weighted_cost']) == cost,
            'Partition tag counts or total weight mismatch')
    return total

def write_weight_fixture(serial_path, destination):
    """Reuse the accepted geometry, with two explicit volume tags of unequal cost."""
    serial = mesh_piece(serial_path)
    boundary = mesh_piece(serial_path.with_name(serial_path.stem+'_boundary.vtu'))
    tags = {cell: 31 if index % 3 else 37 for index,cell in enumerate(serial['cells'])}
    lines = ['$MeshFormat', '2.2 0 8', '$EndMeshFormat', '$Nodes', str(len(serial['nodes']))]
    lines += [f"{node} "+' '.join(format(x, '.17g') for x in serial['coordinates'][node]) for node in serial['nodes']]
    lines += ['$EndNodes', '$Elements', str(len(serial['cells'])+len(boundary['cells']))]
    for cell, (nodes, tag) in boundary['cells'].items():
        lines.append(f"{cell} 2 2 {tag} {tag} "+' '.join(map(str, nodes)))
    for cell, (nodes, _) in serial['cells'].items():
        lines.append(f"{cell} 4 2 {tags[cell]} {tags[cell]} "+' '.join(map(str, nodes)))
    lines.append('$EndElements')
    destination.write_text('\n'.join(lines)+'\n')
    return tags

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    def run(command, name, failure=False):
        result = subprocess.run(command, capture_output=True, text=True, timeout=40)
        text = result.stdout+result.stderr
        (args.work / (name+'.log')).write_text(text)
        require((result.returncode != 0) if failure else (result.returncode == 0 and 'status=success' in text), text)
        return {k: float(v) for k,v in re.findall(r'\b([a-z][a-z0-9_]*)=([-+0-9.eE]+)(?=\s|$)', text)}
    base = [args.executable, '-case', args.case]
    metrics = {}
    fields = {}
    for ranks in (1,2):
        directory = args.work / f'part{ranks}'
        run(base+['-prepare', str(directory), '-parts', str(ranks)]
            + (['-partition_report'] if ranks == 2 else []), f'prepare{ranks}')
        output = args.work / f'solve{ranks}.vtu'
        # A nonexistent source mesh proves solving consumes only the local HDF5 inputs.
        command = [args.mpiexec, '-n', str(ranks), *base, '-partition', str(directory),
                   '-mesh', str(args.work/'must_not_be_read.msh'), '-output', str(output), '-diagnostics', 'full']
        if ranks == 2:
            command += ['-pc_type', 'fieldsplit', '-pc_fieldsplit_type', 'additive',
                        '-fieldsplit_scalar_ksp_type', 'preonly', '-fieldsplit_scalar_pc_type', 'jacobi']
        metrics[ranks] = run(command, f'solve{ranks}')
        all_values, owned_ids, cell_ids = {}, set(), set()
        for rank in range(ranks):
            piece_path = output if ranks == 1 else output.with_name(f'{output.stem}_rank{rank}.vtu')
            piece = ET.parse(piece_path).find('.//Piece')
            arrays = {a.attrib['Name']: a.text.split() for a in piece.findall('./PointData/DataArray')}
            nlocal = int(piece.attrib['NumberOfPoints'])
            if ranks == 2: require(nlocal < metrics[ranks]['nodes'], 'A rank replicated the full node set')
            for node, owner, value in zip(arrays['mesh_node_id'], arrays['owner'], arrays['u']):
                node, owner, value = int(node), int(owner), float(value)
                if node in all_values: require(abs(value-all_values[node]) < 1e-10, 'Stale ghost value')
                all_values[node] = value
                if owner == rank:
                    require(node not in owned_ids, 'Duplicate node ownership')
                    owned_ids.add(node)
            for cell in piece.find("./CellData/DataArray[@Name='mesh_element_id']").text.split():
                require(cell not in cell_ids, 'A cell was integrated on multiple ranks')
                cell_ids.add(cell)
        require(len(owned_ids) == metrics[ranks]['nodes'] and len(cell_ids) == metrics[ranks]['cells'], 'Incomplete partition')
        fields[ranks] = all_values
    verify_partition_layout(args.work/'solve1.vtu', args.work/'solve2.vtu', 2)
    require('partition_report ' not in (args.work/'prepare1.log').read_text(), 'Default prepare unexpectedly enabled profiling')
    partition_capacity = verify_prepare_report((args.work/'prepare2.log').read_text(), args.work/'solve2.vtu', 2, {})
    require(fields[1].keys() == fields[2].keys(), 'Different mesh IDs')
    maximum = max(abs(fields[1][node]-fields[2][node]) for node in fields[1])
    require(maximum < 1e-10, f'1/2 rank solution mismatch: {maximum}')
    for quantity in ('volume', 'solution_integral', 'l2_error', 'h1_seminorm_error'):
        require(abs(metrics[1][quantity]-metrics[2][quantity]) < 1e-10, 'Integral mismatch: '+quantity)
    # A partial tag-to-cost map must leave the other tag at cost 1. We check the
    # emitted actual partition, never a particular METIS assignment or balance.
    weighted_mesh = args.work/'weighted.msh'
    cell_tags = write_weight_fixture(args.work/'solve1.vtu', weighted_mesh)
    weighted_part, weighted_output = args.work/'weighted-part', args.work/'weighted.vtu'
    weighted_base = base+['-mesh', str(weighted_mesh)]
    run(weighted_base+['-prepare', str(weighted_part), '-parts', '2',
                      '-partition_cell_weights', '31:5', '-partition_report'], 'prepare-weighted')
    run([args.mpiexec, '-n', '2', *base, '-partition', str(weighted_part),
         '-mesh', str(args.work/'must_not_be_read.msh'), '-output', str(weighted_output)], 'solve-weighted')
    verify_partition_layout(args.work/'solve1.vtu', weighted_output, 2, cell_tags)
    verify_prepare_report((args.work/'prepare-weighted.log').read_text(), weighted_output, 2, {31: 5})
    for rank in range(2):
        piece = ET.parse(weighted_output.with_name(f'weighted_rank{rank}.vtu')).find('.//Piece')
        arrays = {a.attrib['Name']: (a.text or '').split() for a in piece.findall('./PointData/DataArray')}
        require(all(abs(float(value)-fields[1][int(node)]) < 1e-10
                    for node,value in zip(arrays['mesh_node_id'], arrays['u'])), 'Weighted partition changed the solution')
    # Identical mesh/rank metadata does not authorize mixing layouts. This
    # fixture uses the same tagged mesh for both preparations, isolating the
    # weighted/unweighted identity boundary without another successful solve.
    unweighted_part = args.work/'unweighted-tagged-part'
    run(weighted_base+['-prepare', str(unweighted_part), '-parts', '2'], 'prepare-unweighted-tagged')
    shard = weighted_part/'rank_1.h5'
    backup = shard.with_suffix('.saved')
    shard.rename(backup)
    try:
        shard.write_bytes((unweighted_part/'rank_1.h5').read_bytes())
        run([args.mpiexec, '-n', '2', *base, '-partition', str(weighted_part)],
            'mixed-weighted-partition', failure=True)
        rejection = (args.work/'mixed-weighted-partition.log').read_text()
        require('Inconsistent partition set' in rejection or 'Incomplete cell partition' in rejection,
                'Mixed weighted/unweighted partition identity was not rejected')
    finally:
        shard.unlink(missing_ok=True)
        backup.rename(shard)
    large_cost = 2147483647
    large_total = sum(large_cost if tag == 31 else 1 for tag in cell_tags.values())
    overflow = large_total > int(partition_capacity['metis_index_max'])
    large_part = args.work/'large-weight-part'
    run(weighted_base+['-prepare', str(large_part), '-parts', '1',
                      '-partition_cell_weights', f'31:{large_cost}', '-partition_report'],
        'large-weight', failure=overflow)
    large_log = (args.work/'large-weight.log').read_text()
    if overflow:
        require('Total partition cell weight exceeds METIS index range' in large_log,
                'Total weight overflow was not rejected')
        require(not (large_part/'manifest.yaml').exists(), 'Overflowing weights published a partition')
    else:
        rows = [dict(token.split('=', 1) for token in line.split()[1:])
                for line in large_log.splitlines() if line.startswith('partition_report ')]
        require(len(rows) == 1 and int(rows[0]['total_weighted_cost']) == large_total,
                'Valid large total weight was truncated')
    for name, text, error in (
        ('unknown', '999999:2', 'unknown physical tag'),
        ('zero', '31:0', 'positive costs'),
        ('negative', '31:-2', 'positive costs'),
        ('duplicate', '31:2,31:3', 'unique physical tags'),
        ('malformed', '31:2x', 'tag:positive_cost'),
        ('cost-range', '31:2147483648', 'tag:positive_cost'),
    ):
        directory = args.work/f'invalid-weights-{name}'
        run(weighted_base+['-prepare', str(directory), '-parts', '1',
                          '-partition_cell_weights', text], f'invalid-weights-{name}', failure=True)
        require(error in (args.work/f'invalid-weights-{name}.log').read_text(), 'Incorrect weight rejection: '+name)
        require(not (directory/'manifest.yaml').exists(), 'Rejected weights published a partition')
    for name, options in (('weights', ['-partition_cell_weights', '31:5']),
                          ('report', ['-partition_report', 'false'])):
        run(base+options, 'prepare-only-'+name, failure=True)
        require('require offline -prepare' in (args.work/('prepare-only-'+name+'.log')).read_text(),
                'Prepare-only option accepted in solve mode')
    require(len(ET.parse(args.work/'solve2.pvtu').findall('.//Piece')) == 2, 'Missing PVTU pieces')
    missing = args.work/'part2/rank_1.h5'
    backup = missing.with_suffix('.saved')
    missing.rename(backup)
    try:
        run([args.mpiexec, '-n', '2', *base, '-partition', str(args.work/'part2')], 'missing_partition', failure=True)
    finally:
        backup.rename(missing)
    print(f'PASS: 1/2 rank max difference={maximum:.3e}; local HDF5 input, topology/owner/numbering/order, weighted partition reports/identity, ghost values, field IS, integrals and MPI failure exit')

if __name__ == '__main__': main()
