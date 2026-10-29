"""Generate a rotated 2 x 1.5 x 0.7 Tet4 channel with arbitrary boundary tags."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'poisson'))
from generate_mesh import write_mesh
ORIGIN = (2., -1., .3)
EX, EY, EZ = (.6, .8, 0.), (-.8, .6, 0.), (0., 0., 1.)
LENGTHS = (2., 1.5, .7)
TAGS = (11, 22, 33, 44, 55, 66)

def rotated_mesh(path, subdivisions=3, id_offset=101):
    write_mesh(path, subdivisions, id_offset=id_offset)
    lines = Path(path).read_text().splitlines()
    begin = lines.index('$Nodes') + 2
    end = lines.index('$EndNodes')
    for i in range(begin, end):
        row = lines[i].split(); point = list(map(float, row[1:]))
        xyz = [ORIGIN[c] + sum(LENGTHS[d] * point[d] * (EX, EY, EZ)[d][c] for d in range(3)) for c in range(3)]
        lines[i] = row[0] + ' ' + ' '.join(format(x, '.17g') for x in xyz)
    for i in range(lines.index('$PhysicalNames') + 2, lines.index('$EndPhysicalNames')):
        row = lines[i].split()
        if row[0] == '2': row[1] = str(TAGS[int(row[1])-1]); lines[i] = ' '.join(row)
    for i in range(lines.index('$Elements') + 2, lines.index('$EndElements')):
        row = lines[i].split()
        if row[1] == '2':
            row[3] = row[4] = str(TAGS[int(row[3])-1])
            # Deliberately reverse half the triangles; outward normals must survive.
            if i % 2: row[-1], row[-2] = row[-2], row[-1]
            lines[i] = ' '.join(row)
    Path(path).write_text('\n'.join(lines) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('rotated_channel.msh'))
    parser.add_argument('--subdivisions', type=int, default=3)
    args = parser.parse_args()
    rotated_mesh(args.output, args.subdivisions)
