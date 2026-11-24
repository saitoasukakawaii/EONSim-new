"""Audit the axial mirror transform of both elastic-tube solvers, including every node."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np


def reflected_mesh(base, reflected):
    nodes, cells, faces = base
    mirror_nodes, mirror_cells, mirror_faces = reflected
    if nodes.keys() != mirror_nodes.keys():
        raise ValueError("Mirrored input changed the node identifiers")
    original = np.array([nodes[n] for n in nodes])
    transformed = np.array([mirror_nodes[n] for n in nodes])
    original[:, 0] = original[:, 0].min() + original[:, 0].max() - original[:, 0]
    if not np.array_equal(transformed, original):
        raise ValueError("Mirrored coordinates disagree with the exact axial reflection")
    if Counter((a, c, b, d) for a, b, c, d in cells) != Counter(mirror_cells):
        raise ValueError("Mirrored cell orientation or topology differs")
    ends = {1: 2, 2: 1, 11: 12, 12: 11}
    expected = Counter((ends.get(tag, tag), tuple(sorted(nodes))) for tag, nodes in faces)
    observed = Counter((tag, tuple(sorted(nodes))) for tag, nodes in mirror_faces)
    if expected != observed:
        raise ValueError("Boundary tags or faces do not reflect consistently")


def compare_field(base, mirror, name):
    if base.keys() != mirror.keys():
        raise ValueError("Output node IDs differ")
    reference = np.array([getattr(base[n], name) for n in base])
    observed = np.array([getattr(mirror[n], name) for n in base])
    if name != "pressure":
        reference[:, 0] *= -1
    difference = float(np.max(np.abs(reference - observed)))
    scale = float(np.max(np.abs(reference)))
    # The upstream VTU writer supports single-precision output fields.
    if not np.isfinite(difference) or difference > 5e-7 * scale + 1e-13:
        raise ValueError(f"Axial reflection changed {name} by {difference} at scale {scale}")
    return dict(max_absolute_difference=difference, max_original_absolute_value=scale)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "mirrored", "reference-scripts", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    args = cli.parse_args()
    sys.path.insert(0, str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as external
    import study_hydrostatic_fsi as fsi
    import study_rigid_tube as tube

    roots = [args.original, args.mirrored]
    reports = [json.loads((p/"results.json").read_text()) for p in roots]
    base, mirror = reports
    for key in ("mesh", "cells", "steps", "krylov", "nonlinear_limit", "peak_pressure",
                "equilibrium_area_strain", "source_executables"):
        if base[key] != mirror[key]:
            raise ValueError(f"Different paired controls for {key}")
    if base["reflected"] or not mirror["reflected"]:
        raise ValueError("Need a native mesh followed by its axial reflection")
    if not all(all(r["run_hash_receipts"].values()) for r in reports):
        raise ValueError("Missing a run-time binary hash")
    for deck in ("eon/case.json", "matched/svFSI.inp"):
        if (roots[0]/deck).read_bytes() != (roots[1]/deck).read_bytes():
            raise ValueError(f"Different paired solver configuration at {deck}")
    meshes = [[tube.read_mesh(root/"reference"/filename) for filename in ("fluid.msh", "solid.msh")]
              for root in roots]
    for original_mesh, mirror_mesh in zip(*meshes):
        reflected_mesh(original_mesh, mirror_mesh)
    records = []
    for index, step in enumerate((base["steps"]//2, base["steps"])):
        solvers = []
        for root, mesh in zip(roots, meshes):
            solvers.append({
                "eon": [fsi.recovered_state(root/"eon", f"tube_step{step}"+suffix, domain, bool(i), 1)
                        for i, (domain, suffix) in enumerate(zip(mesh, ("", "_solid")))],
                "svfsi": external.external_fields(root/f"matched/1-procs/result_{step:03d}.vtu", mesh),
            })
        for mode in ("eon", "svfsi"):
            record = dict(time=step/base["steps"], solver=mode, fields={})
            for i, region in enumerate(("fluid", "solid")):
                quantities = ("displacement", "velocity", "pressure") if i == 0 else ("displacement", "velocity")
                record["fields"][region] = {
                    q: compare_field(solvers[0][mode][i], solvers[1][mode][i], q) for q in quantities
                }
            original = np.array(base["results"][index][mode]["strains"])
            measured = np.array(mirror["results"][index][mode]["strains"])
            if not np.allclose(base["axial_sections"], 2-np.array(mirror["axial_sections"][::-1]),
                               rtol=0, atol=4e-16):
                raise ValueError("Reflected sample locations differ")
            record.update(original_ends=original[[0, -1]].tolist(), reflected_ends=measured[[0, -1]].tolist(),
                          max_reflected_strain_delta=float(np.max(np.abs(original-measured[::-1]))))
            records.append(record)
    result = dict(mesh=base["mesh"], steps=base["steps"], peak_pressure=base["peak_pressure"],
                  source_executables=base["source_executables"], mesh_sha256=[r["mesh_sha256"] for r in reports],
                  samples=records)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
