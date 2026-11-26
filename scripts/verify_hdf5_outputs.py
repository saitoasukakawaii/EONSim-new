#!/usr/bin/env python3
"""Independently compare an ASCII VTU result with shared HDF5/XDMF output.

Uses owner copies by stable mesh-node IDs and cell records by stable element IDs.
No partition reader or writer implementation is reused. Needs h5py for offline
inspection only; the EONSim runtime has no Python dependency.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def vtu(path, ranks, boundary):
    nodes, cells = {}, {}
    for rank in range(ranks):
        suffix = (f"_rank{rank}" if ranks > 1 else "") + ("_boundary" if boundary else "") + ".vtu"
        source = path.with_name(path.stem + suffix)
        piece = ET.parse(source).find(".//Piece")
        require(piece is not None, f"Missing piece in {source}")
        point = {}
        for item in piece.findall("./PointData/DataArray"):
            width = int(item.get("NumberOfComponents", "1"))
            cast = float if item.get("type", "").startswith("Float") else int
            values = [cast(x) for x in (item.text or "").split()]
            require(len(values) == width * int(piece.get("NumberOfPoints")), f"Invalid array in {source}")
            point[item.get("Name")] = [values[i:i+width] for i in range(0, len(values), width)]
        xyz = list(map(float, (piece.find("./Points/DataArray").text or "").split()))
        point["coordinates"] = [xyz[i:i+3] for i in range(0, len(xyz), 3)]
        ids = [x[0] for x in point["mesh_node_id"]]
        for i, node in enumerate(ids):
            # Compact boundary pieces can lack the owner copy. All of their
            # fields must still match the owner's globally stored result.
            record = {name: values[i] for name, values in point.items()}
            if boundary or point["owner"][i][0] == rank:
                if node in nodes:
                    require(nodes[node] == record, f"Inconsistent duplicate node {node}")
                nodes[node] = record
        arrays = {a.get("Name"): list(map(int, (a.text or "").split())) for a in piece.findall("./Cells/DataArray")}
        cell_data = {a.get("Name"): list(map(int, (a.text or "").split())) for a in piece.findall("./CellData/DataArray")}
        start = 0
        for i, end in enumerate(arrays["offsets"]):
            identifier = cell_data["mesh_element_id"][i]
            require(identifier not in cells, f"Cell {identifier} appears on multiple ranks")
            cells[identifier] = (cell_data["physical_tag"][i], tuple(ids[n] for n in arrays["connectivity"][start:end]))
            start = end
        require(start == len(arrays["connectivity"]), "Trailing connectivity")
    return nodes, cells


def verify(ascii_path, xdmf_path, ranks):
    import h5py
    import numpy as np
    tree = ET.parse(xdmf_path)
    grid = tree.find("./Domain/Grid")
    require(grid is not None and grid.get("CollectionType") == "Spatial", "Missing spatial XDMF collection")
    files = set()
    for item in tree.findall(".//DataItem"):
        require(item.get("Format") == "HDF", "Unexpected inline/missing HDF data item")
        file, dataset = item.text.strip().split(":/", 1)
        files.add(file)
        with h5py.File(xdmf_path.parent/file, "r") as data:
            require(tuple(map(int, item.get("Dimensions").split())) == data["/"+dataset].shape,
                    f"XDMF shape disagrees with /{dataset}")
    require(len(files) == 1, "One snapshot must reference exactly one shared payload")
    checked_nodes, checked_cells = 0, 0
    with h5py.File(xdmf_path.parent/next(iter(files)), "r") as data:
        node_ids = data["Mesh/mesh_node_id"][:].tolist()
        require(len(node_ids) == len(set(node_ids)), "Duplicate shared points")
        actual = {"coordinates": data["Mesh/coordinates"][:],
                  **{name: dataset[:] for name, dataset in data["Fields"].items()},
                  **{name: data["Mesh/"+name][:] for name in ("mesh_node_id", "owner", "algebra_node_id")}}
        for name, array in actual.items():
            require(np.isfinite(array).all(), f"Nonfinite output: {name}")
        positions = {node: i for i, node in enumerate(node_ids)}
        for child in grid.findall("./Grid"):
            name = child.get("Name")
            require(name in ("Volume", "Boundary"), "Unexpected XDMF grid")
            expected_nodes, expected_cells = vtu(ascii_path, ranks, name == "Boundary")
            if name == "Volume":
                require(set(expected_nodes) == set(node_ids), "Global owned point set differs")
            for node, fields in expected_nodes.items():
                require(node in positions, f"Node {node} missing from shared output")
                require(fields.keys() == actual.keys(), "Point-field set differs")
                for field, values in fields.items():
                    require(np.array_equal(np.asarray(values), np.asarray(actual[field][positions[node]]).reshape(-1)),
                            f"Exact point data mismatch: {name}/{node}/{field}")
                checked_nodes += 1
            conn = data[name+"/connectivity"][:]
            cells = {}
            offset = 0
            for cell, tag in zip(data[name+"/mesh_element_id"][:], data[name+"/physical_tag"][:]):
                if conn.ndim == 2:
                    indices = conn[len(cells)]
                else:
                    kind = int(conn[offset]);offset += 1
                    require(kind in (4, 5), f"Unsupported mixed cell {kind}")
                    arity = 3 if kind == 4 else 4
                    indices = conn[offset:offset+arity];offset += arity
                cells[int(cell)] = (int(tag), tuple(node_ids[int(i)] for i in indices))
            require(cells == expected_cells, f"Cell topology/tag/ID mismatch: {name}")
            checked_cells += len(cells)
        modes = data["Partition/io_modes"][:].tolist()
        require(len(modes) == ranks and all(n == c+i and n > 0 for n,c,i in modes), "Invalid I/O mode diagnostics")
        if ranks > 1:
            require(all(c > 0 for n,c,i in modes), "A rank performed no actual collective I/O")
    return {"status": "passed", "ranks": ranks, "checked_node_records": checked_nodes,
            "checked_cells": checked_cells, "actual_io_modes": modes,
            "comparison": "exact", "xdmf": str(xdmf_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ascii", type=Path, required=True)
    parser.add_argument("--xdmf", type=Path, required=True)
    parser.add_argument("--ranks", type=int, required=True)
    args = parser.parse_args()
    require(args.ranks >= 1, "Rank count must be positive")
    print(json.dumps(verify(args.ascii, args.xdmf, args.ranks), indent=2))


if __name__ == "__main__":
    main()
