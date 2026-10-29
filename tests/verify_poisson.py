"""Focused P0 evidence: manufactured convergence, lifting, and failure propagation."""

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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

    def run(name, mesh, exact="quadratic", extra=(), failure=None):
        case = args.work / f"{name}.yaml"
        case.write_text(case_text.replace("exact_solution: quadratic", f"exact_solution: {exact}"), encoding="utf-8")
        output = args.work / f"{name}.vtu"
        command = [str(args.executable), "-case", str(case), "-mesh", str(mesh),
                   "-output", str(output), "-diagnostics", "full", *extra]
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
        piece = ET.parse(output).find(".//Piece")
        require(int(piece.attrib["NumberOfPoints"]) == int(metrics["nodes"]), "VTU point count mismatch")
        values = [float(v) for v in piece.find("./PointData/DataArray[@Name='u']").text.split()]
        require(len(values) == int(metrics["nodes"]) and all(math.isfinite(v) for v in values), "Invalid VTU field")
        boundary = ET.parse(output.with_name(output.stem + "_boundary.vtu"))
        tags = {int(v) for v in boundary.find(".//CellData/DataArray[@Name='physical_tag']").text.split()}
        require(tags == {1, 2, 3, 4, 5, 6}, "Boundary physical tags were not preserved")
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
    generator.write_mesh(warped, 4, warp=True, id_offset=5_000_000_000)
    affine = run("affine_warped", warped, "affine")
    require(affine["l2_error"] < 1e-9 and affine["h1_seminorm_error"] < 1e-8, "Affine patch test failed")
    require(abs(affine["solution_integral"] - 4.0) < 1e-9, "Incorrect affine integral")
    ids = ET.parse(args.work / "affine_warped.vtu").find(".//PointData/DataArray[@Name='mesh_node_id']")
    require(min(map(int, ids.text.split())) == 5_000_000_000, "64-bit mesh IDs were lost")

    run("nonconverged", coarse_mesh, extra=("-ksp_max_it", "1"), failure="did not converge")
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
              "l2_order": l2_order, "h1_order": h1_order}
    (args.work / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: L2 order={l2_order:.6f}, H1 order={h1_order:.6f}, affine L2={affine['l2_error']:.3e}")
    print("PASS: true residual, nonzero lifting, VTU tags, 64-bit IDs, solver/geometry failure propagation")


if __name__ == "__main__":
    main()
