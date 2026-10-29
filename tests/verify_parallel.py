"""P1: offline partitions, local-only input, owner/ghost and 1/2 rank agreement."""
import argparse
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

def require(condition, message):
    if not condition: raise RuntimeError(message)

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
        run(base+['-prepare', str(directory), '-parts', str(ranks)], f'prepare{ranks}')
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
    require(fields[1].keys() == fields[2].keys(), 'Different mesh IDs')
    maximum = max(abs(fields[1][node]-fields[2][node]) for node in fields[1])
    require(maximum < 1e-10, f'1/2 rank solution mismatch: {maximum}')
    for quantity in ('volume', 'solution_integral', 'l2_error', 'h1_seminorm_error'):
        require(abs(metrics[1][quantity]-metrics[2][quantity]) < 1e-10, 'Integral mismatch: '+quantity)
    require(len(ET.parse(args.work/'solve2.pvtu').findall('.//Piece')) == 2, 'Missing PVTU pieces')
    missing = args.work/'part2/rank_1.h5'
    backup = missing.with_suffix('.saved')
    missing.rename(backup)
    try:
        run([args.mpiexec, '-n', '2', *base, '-partition', str(args.work/'part2')], 'missing_partition', failure=True)
    finally:
        backup.rename(missing)
    print(f'PASS: 1/2 rank max difference={maximum:.3e}; local HDF5 input, ghost values, field IS, integrals and MPI failure exit')

if __name__ == '__main__': main()
