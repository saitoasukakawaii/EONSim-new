"""Focused P0 evidence: manufactured convergence, lifting, VTU I/O, and failures."""

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_piece(path):
    """Decode ASCII/raw-appended VTU independently, retaining exact integer IDs.

    Arrays are keyed by (section, name); the sole Points array has name ''.
    Binary offsets start after '_', and every uncompressed block has a UInt64
    byte-count header. Checking these separately catches offset/header errors
    that a comparison of only solution values would miss.
    """
    raw = Path(path).read_bytes()
    appended = raw.find(b"<AppendedData")
    binary = appended >= 0
    payload_start = 0
    if binary:
        opening = re.match(rb'<AppendedData\s+encoding="raw"\s*>\s*_', raw[appended:])
        require(opening is not None, f"{path}: expected raw appended data")
        payload_start = appended + opening.end()
        root = ET.fromstring(raw[:appended] + b"</VTKFile>")
        require(root.get("header_type") == "UInt64", f"{path}: missing UInt64 header type")
        require("compressor" not in root.attrib, f"{path}: unexpected compression")
    else:
        root = ET.fromstring(raw)
    require(root.get("type") == "UnstructuredGrid" and root.get("byte_order") == "LittleEndian",
            f"{path}: invalid grid type or byte order")
    pieces = root.findall("./UnstructuredGrid/Piece")
    require(len(pieces) == 1, f"{path}: expected one piece")
    piece = pieces[0]
    result = {"number_of_points": int(piece.attrib["NumberOfPoints"]),
              "number_of_cells": int(piece.attrib["NumberOfCells"]),
              "binary": binary, "arrays": {}}
    require(result["number_of_points"] >= 0 and result["number_of_cells"] >= 0,
            f"{path}: negative piece size")
    codes = {"Float64": "d", "Int64": "q", "Int32": "i", "UInt8": "B"}
    next_offset = 0
    for section in ("Points", "Cells", "PointData", "CellData"):
        for array in piece.findall(f"./{section}/DataArray"):
            key = (section, array.get("Name", ""))
            kind, components = array.attrib["type"], int(array.get("NumberOfComponents", "1"))
            require(key not in result["arrays"] and kind in codes and components > 0,
                    f"{path}: invalid array {key}")
            if binary:
                require(array.get("format") == "appended", f"{path}: mixed array encodings")
                offset = int(array.attrib["offset"])
                require(offset == next_offset, f"{path}: noncontiguous/incorrect offset for {key}")
                header = payload_start + offset
                require(header + 8 <= len(raw), f"{path}: truncated UInt64 header")
                byte_count, = struct.unpack_from("<Q", raw, header)
                width = struct.calcsize("<" + codes[kind])
                require(byte_count % width == 0 and header + 8 + byte_count <= len(raw),
                        f"{path}: invalid binary array length for {key}")
                values = struct.unpack_from(f"<{byte_count // width}{codes[kind]}", raw, header + 8)
                next_offset = offset + 8 + byte_count
            else:
                require(array.get("format") == "ascii", f"{path}: expected ASCII array")
                convert = float if kind == "Float64" else int
                values = tuple(map(convert, (array.text or "").split()))
            require(len(values) % components == 0, f"{path}: incomplete tuple for {key}")
            require(kind != "Float64" or all(math.isfinite(v) for v in values),
                    f"{path}: non-finite floating array {key}")
            result["arrays"][key] = {"type": kind, "components": components, "values": values}
    if binary:
        require(re.fullmatch(rb"\s*</AppendedData>\s*</VTKFile>\s*", raw[payload_start + next_offset:]) is not None,
                f"{path}: appended payload length or closing markup mismatch")
    arrays = result["arrays"]
    points, cells = result["number_of_points"], result["number_of_cells"]
    require(arrays[("Points", "")]["type"] == "Float64" and arrays[("Points", "")]["components"] == 3
            and len(arrays[("Points", "")]["values"]) == 3 * points, f"{path}: invalid coordinates")
    for (section, name), array in arrays.items():
        if section in ("PointData", "CellData"):
            count = points if section == "PointData" else cells
            require(len(array["values"]) == count * array["components"], f"{path}: invalid shape for {name}")
    for key in (("PointData", "mesh_node_id"), ("PointData", "algebra_node_id"),
                ("CellData", "mesh_element_id"), ("Cells", "connectivity"), ("Cells", "offsets")):
        require(arrays[key]["type"] == "Int64" and arrays[key]["components"] == 1,
                f"{path}: lost Int64 identity/connectivity metadata for {key}")
    require(arrays[("Cells", "types")]["type"] == "UInt8", f"{path}: invalid cell type storage")
    for key in (("PointData", "mesh_node_id"), ("CellData", "mesh_element_id")):
        values = arrays[key]["values"]
        require(len(set(values)) == len(values), f"{path}: duplicate stable IDs for {key}")
    offsets, types = arrays[("Cells", "offsets")]["values"], arrays[("Cells", "types")]["values"]
    connectivity = arrays[("Cells", "connectivity")]["values"]
    require(len(offsets) == cells and len(types) == cells, f"{path}: incorrect cell count")
    previous = 0
    arities = {3: 2, 5: 3, 9: 4, 10: 4}
    for offset, cell_type in zip(offsets, types):
        require(cell_type in arities and offset - previous == arities[cell_type],
                f"{path}: cell offsets do not match mixed topology")
        previous = offset
    require(previous == len(connectivity) and all(0 <= node < points for node in connectivity),
            f"{path}: invalid connectivity")
    return result


def compare_piece_arrays(reference, candidate):
    """Require exact numerical/data-type equality, regardless of file encoding."""
    for key in ("number_of_points", "number_of_cells"):
        require(reference[key] == candidate[key], f"VTU {key} changed")
    require(reference["arrays"].keys() == candidate["arrays"].keys(), "VTU array inventory changed")
    for key, array in reference["arrays"].items():
        require(array == candidate["arrays"][key], f"VTU array changed: {key}")


def compare_boundary(volume, boundary, compact=True):
    """Check used-node compaction, original local ordering, and every point field."""
    source, target = volume["arrays"], boundary["arrays"]
    volume_ids = source[("PointData", "mesh_node_id")]["values"]
    boundary_ids = target[("PointData", "mesh_node_id")]["values"]
    original = {node: i for i, node in enumerate(volume_ids)}
    require(all(node in original for node in boundary_ids), "Boundary contains unknown stable node IDs")
    indices = [original[node] for node in boundary_ids]
    require(indices == sorted(indices), "Boundary changed original local node order")
    used = set(target[("Cells", "connectivity")]["values"])
    if compact:
        require(used == set(range(boundary["number_of_points"])), "Compact boundary retains unused points")
    else:
        require(boundary_ids == volume_ids, "Full boundary omitted volume points")
    source_fields = {key for key in source if key[0] in ("Points", "PointData")}
    require(source_fields == {key for key in target if key[0] in ("Points", "PointData")},
            "Boundary point field inventory changed")
    for key in source_fields:
        a, b = source[key], target[key]
        require(a["type"] == b["type"] and a["components"] == b["components"],
                f"Boundary point metadata changed: {key}")
        components = a["components"]
        expected = tuple(a["values"][i * components + c] for i in indices for c in range(components))
        require(b["values"] == expected, f"Boundary point remap changed values: {key}")


def compare_boundary_arrays(reference, candidate):
    """Compare full/compact boundary topology and fields through stable IDs."""
    require(reference["number_of_cells"] == candidate["number_of_cells"], "Boundary cell count changed")
    source, target = reference["arrays"], candidate["arrays"]
    require(source.keys() == target.keys(), "Boundary array inventory changed")
    for key in source:
        require((source[key]["type"], source[key]["components"]) ==
                (target[key]["type"], target[key]["components"]), f"Boundary array metadata changed: {key}")
        if key[0] == "CellData" or key in (("Cells", "offsets"), ("Cells", "types")):
            require(source[key] == target[key], f"Boundary cell array changed: {key}")
    ids = [arrays[("PointData", "mesh_node_id")]["values"] for arrays in (source, target)]
    connectivity = [tuple(node_ids[i] for i in arrays[("Cells", "connectivity")]["values"])
                    for arrays, node_ids in zip((source, target), ids)]
    require(connectivity[0] == connectivity[1], "Boundary stable-ID topology changed")
    used_ids = sorted(set(connectivity[0]))
    index = [{node: i for i, node in enumerate(node_ids)} for node_ids in ids]
    for key in source:
        if key[0] not in ("Points", "PointData"):
            continue
        components = source[key]["components"]
        values = [tuple(arrays[key]["values"][lookup[node] * components + c]
                        for node in used_ids for c in range(components))
                  for arrays, lookup in zip((source, target), index)]
        require(values[0] == values[1], f"Boundary used-point field changed: {key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("cube_generator", args.case.parent / "generate_mesh.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    case_text = args.case.read_text(encoding="utf-8")

    def run(name, mesh, exact="quadratic", extra=(), failure=None, binary=False, boundary=True, compact=True):
        case = args.work / f"{name}.yaml"
        case.write_text(case_text.replace("exact_solution: quadratic", f"exact_solution: {exact}"), encoding="utf-8")
        output = args.work / f"{name}.vtu"
        command = [str(args.executable), "-case", str(case), "-mesh", str(mesh),
                   "-output", str(output), "-diagnostics", "full", *extra]
        if binary:
            command += ["-vtu_format", "binary"]
        if not boundary:
            command += ["-vtu_boundary", "false"]
        if not compact:
            command += ["-vtu_compact_boundary", "false"]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        log = completed.stdout + completed.stderr
        (args.work / f"{name}.log").write_text(log, encoding="utf-8")
        if failure:
            require(completed.returncode != 0 and failure in log and "status=success" not in log,
                    f"{name}: failure was not propagated\n{log}")
            return None
        require(completed.returncode == 0 and "status=success" in log, f"{name}: solve failed\n{log}")
        metrics = {key: float(value) for key, value in re.findall(r"\b([a-z][a-z0-9_]*)=([-+0-9.eE]+)(?=\s|$)", log)}
        for key in ("volume", "l2_error", "h1_seminorm_error", "boundary_max_error", "true_residual"):
            require(key in metrics and math.isfinite(metrics[key]), f"{name}: missing/non-finite {key}")
        require(abs(metrics["volume"] - 1) < 1e-12, "Incorrect unit-cube volume")
        require(metrics["boundary_max_error"] < 1e-9, "Nonzero Dirichlet lifting failed")
        require(metrics["true_residual"] <= max(metrics["atol"], metrics["rtol"] * metrics["rhs_norm"]),
                "True residual exceeds configured tolerance")
        require(metrics["owned"] > metrics["constrained"], "Case has no free unknowns")
        piece = read_piece(output)
        require(piece["binary"] == binary, "VTU output format option was ignored")
        require(piece["number_of_points"] == int(metrics["nodes"]), "VTU point count mismatch")
        values = piece["arrays"][("PointData", "u")]["values"]
        require(len(values) == int(metrics["nodes"]) and all(math.isfinite(v) for v in values), "Invalid VTU field")
        boundary_path = output.with_name(output.stem + "_boundary.vtu")
        if boundary:
            boundary_piece = read_piece(boundary_path)
            require(boundary_piece["binary"] == binary, "Boundary encoding differs from volume")
            compare_boundary(piece, boundary_piece, compact)
            tags = set(boundary_piece["arrays"][("CellData", "physical_tag")]["values"])
            require(tags == {1, 2, 3, 4, 5, 6}, "Boundary physical tags were not preserved")
        else:
            require(not boundary_path.exists(), "Disabled boundary output was still written")
        return metrics

    coarse_mesh, fine_mesh = args.work / "cube4.msh", args.work / "cube8.msh"
    generator.write_mesh(coarse_mesh, 4)
    generator.write_mesh(fine_mesh, 8)
    coarse = run("quadratic4", coarse_mesh)
    fine = run("quadratic8", fine_mesh)
    l2_order = math.log2(coarse["l2_error"] / fine["l2_error"])
    h1_order = math.log2(coarse["h1_seminorm_error"] / fine["h1_seminorm_error"])
    require(1.8 < l2_order < 2.2 and 0.9 < h1_order < 1.1, "Incorrect Tet4/P1 convergence rates")
    warped = args.work / "warped.msh"
    large_id = (1 << 53) + 1  # Also catches any accidental Int64 -> Float64 round trip.
    generator.write_mesh(warped, 4, warp=True, id_offset=large_id)
    affine = run("affine_warped", warped, "affine")
    require(affine["l2_error"] < 1e-9 and affine["h1_seminorm_error"] < 1e-8, "Affine patch test failed")
    require(abs(affine["solution_integral"] - 4.0) < 1e-9, "Incorrect affine integral")
    ascii_piece = read_piece(args.work / "affine_warped.vtu")
    ascii_boundary = read_piece(args.work / "affine_warped_boundary.vtu")
    ids = ascii_piece["arrays"][("PointData", "mesh_node_id")]["values"]
    require(set(ids) == {large_id + 7 * i for i in range(len(ids))}, "64-bit mesh IDs were lost")
    require(ascii_boundary["number_of_points"] < ascii_piece["number_of_points"],
            "Default boundary output did not compact interior nodes")
    # Reuse the warped affine oracle. One additional full-boundary binary solve
    # exercises exact array round trips and full/compact stable-ID topology.
    run("affine_binary", warped, "affine", binary=True, compact=False)
    binary_piece = read_piece(args.work / "affine_binary.vtu")
    binary_boundary = read_piece(args.work / "affine_binary_boundary.vtu")
    compare_piece_arrays(ascii_piece, binary_piece)
    compare_boundary_arrays(ascii_boundary, binary_boundary)
    run("affine_volume_only", warped, "affine", binary=True, boundary=False)
    compare_piece_arrays(ascii_piece, read_piece(args.work / "affine_volume_only.vtu"))

    # A small mixed Tri3/Quad4 mesh checks variable offsets, UInt8 types, and
    # compact binary boundary edges; the 3D fixture above has uniform arity.
    scalar_generator_path = Path(__file__).resolve().parents[1] / "cases/scalar2d/generate.py"
    scalar_spec = importlib.util.spec_from_file_location("scalar2d_io_generator", scalar_generator_path)
    scalar_generator = importlib.util.module_from_spec(scalar_spec)
    scalar_spec.loader.exec_module(scalar_generator)
    mixed_case = scalar_generator.generate(args.work / "mixed2d", n=3, topology="mixed", distorted=True, permuted=True)
    mixed_output = args.work / "mixed2d_binary.vtu"
    command = [str(args.executable), "-case", str(mixed_case), "-output", str(mixed_output), "-vtu_format", "binary"]
    mixed_run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    mixed_log = mixed_run.stdout + mixed_run.stderr
    (args.work / "mixed2d_binary.log").write_text(mixed_log, encoding="utf-8")
    require(mixed_run.returncode == 0 and "status=success" in mixed_log, f"Mixed 2D output failed\n{mixed_log}")
    mixed = read_piece(mixed_output)
    mixed_boundary = read_piece(mixed_output.with_name(mixed_output.stem + "_boundary.vtu"))
    require(mixed["binary"] and mixed_boundary["binary"], "Mixed 2D output ignored binary mode")
    require(set(mixed["arrays"][("Cells", "types")]["values"]) == {5, 9}, "Mixed 2D cells lost their types")
    require(set(mixed_boundary["arrays"][("Cells", "types")]["values"]) == {3}, "2D boundary is not line cells")
    compare_boundary(mixed, mixed_boundary)
    require(mixed_boundary["number_of_points"] < mixed["number_of_points"], "2D boundary retained interior nodes")
    coordinates = mixed["arrays"][("Points", "")]["values"]
    solution = mixed["arrays"][("PointData", "u")]["values"]
    for i, value in enumerate(solution):
        require(abs(value - (1 + coordinates[3 * i] + 2 * coordinates[3 * i + 1])) < 2e-9,
                "Mixed 2D binary fields do not match the affine patch")

    run("nonconverged", coarse_mesh, extra=("-ksp_max_it", "1"), failure="did not converge")
    run("invalid_vtu_format", coarse_mesh, extra=("-vtu_format", "invalid"), failure="-vtu_format")
    bad_mesh = args.work / "inverted.msh"
    lines = coarse_mesh.read_text(encoding="utf-8").splitlines()
    first = lines.index("$Elements") + 2
    for index in range(first, len(lines)):
        fields = lines[index].split()
        if len(fields) > 2 and fields[1] == "4":
            fields[-1], fields[-2] = fields[-2], fields[-1]
            lines[index] = " ".join(fields)
            break
    bad_mesh.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run("invalid_geometry", bad_mesh, failure="Inverted or degenerate Tet4")
    report = {"quadratic4": coarse, "quadratic8": fine, "affine_warped": affine,
              "l2_order": l2_order, "h1_order": h1_order,
              "vtu": {"volume_points": ascii_piece["number_of_points"],
                      "compact_boundary_points": ascii_boundary["number_of_points"],
                      "full_boundary_points": binary_boundary["number_of_points"],
                      "ascii_volume_bytes": (args.work / "affine_warped.vtu").stat().st_size,
                      "binary_volume_bytes": (args.work / "affine_binary.vtu").stat().st_size,
                      "mixed2d_cells": mixed["number_of_cells"]}}
    (args.work / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: L2 order={l2_order:.6f}, H1 order={h1_order:.6f}, affine L2={affine['l2_error']:.3e}")
    print("PASS: true residual, nonzero lifting, VTU tags, 64-bit IDs, solver/geometry failure propagation")
    print("PASS: independent UInt64/LittleEndian binary decoder, exact arrays, compact/full boundary maps, volume-only, mixed 2D offsets")


if __name__ == "__main__":
    main()
