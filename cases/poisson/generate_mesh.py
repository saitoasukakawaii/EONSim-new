"""Generate a conforming unit-cube Tet4 mesh in Gmsh 2.2 ASCII; no Gmsh dependency."""

import argparse
import itertools
import math
from pathlib import Path


def write_mesh(path, subdivisions=4, warp=False, id_offset=101):
    if subdivisions < 1:
        raise ValueError("Use at least one subdivision")
    n = subdivisions
    points = []
    indices = {}
    for k in range(n + 1):
        for j in range(n + 1):
            for i in range(n + 1):
                indices[i, j, k] = len(points)
                x, y, z = i / n, j / n, k / n
                if warp and 0 < i < n and 0 < j < n and 0 < k < n:
                    amplitude = 0.08 / n
                    x += amplitude * math.sin(2 * j + k)
                    y += amplitude * math.sin(i + 2 * k)
                    z += amplitude * math.sin(2 * i + j)
                points.append((x, y, z))

    cells = []
    faces = {}
    for k, j, i in itertools.product(range(n), repeat=3):
        for permutation in itertools.permutations(range(3)):
            corner = [i, j, k]
            cell = [indices[tuple(corner)]]
            for axis in permutation:
                corner[axis] += 1
                cell.append(indices[tuple(corner)])
            inversions = sum(permutation[a] > permutation[b] for a in range(3) for b in range(a + 1, 3))
            if inversions % 2:
                cell[1], cell[2] = cell[2], cell[1]
            cells.append(cell)
            for local in ((1, 2, 3), (0, 3, 2), (0, 1, 3), (0, 2, 1)):
                face = tuple(cell[a] for a in local)
                key = tuple(sorted(face))
                if key in faces:
                    faces[key] = None
                else:
                    faces[key] = face

    boundary = []
    for face in faces.values():
        if face is None:
            continue
        for axis in range(3):
            for side in (0, 1):
                if all(points[node][axis] == side for node in face):
                    boundary.append((2 * axis + side + 1, face))
                    break
            else:
                continue
            break
        else:
            raise ValueError("Generated an unexpected exterior face")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    node_id = lambda index: id_offset + 7 * index
    with path.open("w", encoding="utf-8") as out:
        out.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n7\n')
        for tag, name in enumerate(("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"), 1):
            out.write(f'2 {tag} "{name}"\n')
        out.write('3 10 "domain"\n$EndPhysicalNames\n$Nodes\n')
        out.write(f'{len(points)}\n')
        for index, point in enumerate(points):
            out.write(f'{node_id(index)} ' + ' '.join(format(x, '.17g') for x in point) + '\n')
        out.write(f'$EndNodes\n$Elements\n{len(boundary) + len(cells)}\n')
        element_id = 1
        for tag, face in boundary:
            out.write(f'{element_id} 2 2 {tag} {tag} ' + ' '.join(str(node_id(a)) for a in face) + '\n')
            element_id += 1
        for cell in cells:
            out.write(f'{element_id} 4 2 10 1 ' + ' '.join(str(node_id(a)) for a in cell) + '\n')
            element_id += 1
        out.write('$EndElements\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subdivisions", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("cube.msh"))
    parser.add_argument("--warp", action="store_true", help="Perturb interior nodes for a non-axis-aligned patch test")
    args = parser.parse_args()
    write_mesh(args.output, args.subdivisions, args.warp)
