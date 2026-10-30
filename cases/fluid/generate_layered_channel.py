"""Generate a unit-cube Tet4 channel with conforming viscosity layers at y=0.5."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'poisson'))
from generate_mesh import write_mesh


def layered_mesh(path, subdivisions=4):
    if subdivisions < 2 or subdivisions % 2:
        raise ValueError('Use an even subdivision count to resolve the material interface')
    write_mesh(path, subdivisions)
    path = Path(path)
    lines = path.read_text().splitlines()
    positions = {int(row[0]): list(map(float, row[1:])) for row in
                 (line.split() for line in lines[lines.index('$Nodes')+2:lines.index('$EndNodes')])}
    for i in range(lines.index('$Elements')+2, lines.index('$EndElements')):
        row = lines[i].split()
        if row[1] == '4' and sum(positions[int(node)][1] for node in row[-4:])/4 > .5:
            row[3] = row[4] = '20'
            lines[i] = ' '.join(row)
    lines[lines.index('$PhysicalNames')+1] = '8'
    lines[lines.index('3 10 "domain"')] = '3 10 "lower_fluid"'
    lines.insert(lines.index('$EndPhysicalNames'), '3 20 "upper_fluid"')
    path.write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subdivisions', type=int, default=4)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('layered_channel.msh'))
    args = parser.parse_args()
    layered_mesh(args.output, args.subdivisions)
