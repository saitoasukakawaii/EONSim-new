#!/usr/bin/env python3
"""Independently compare an ASCII VTU result with shared HDF5/XDMF output.

Uses owner copies by stable mesh-node IDs and cell records by stable element IDs.
No partition reader or writer implementation is reused. Uses native h5dump XML
and NumPy for offline inspection; the EONSim runtime has no Python dependency.
"""
import argparse
import json
import operator
from pathlib import Path
import shutil
import subprocess
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
        count = int(piece.get("NumberOfCells"))
        require(all(len(values) == count for values in (arrays["offsets"], arrays["types"],
                    cell_data["mesh_element_id"], cell_data["physical_tag"])), f"Invalid cell array length in {source}")
        start = 0
        for i, end in enumerate(arrays["offsets"]):
            identifier = cell_data["mesh_element_id"][i]
            require(identifier not in cells, f"Cell {identifier} appears on multiple ranks")
            require(start <= end <= len(arrays["connectivity"]), f"Invalid cell offset in {source}")
            indices = arrays["connectivity"][start:end]
            require(all(0 <= n < len(ids) for n in indices), f"Invalid point index in {source}")
            cells[identifier] = (cell_data["physical_tag"][i], tuple(ids[n] for n in indices), arrays["types"][i])
            start = end
        require(start == len(arrays["connectivity"]), "Trailing connectivity")
    return nodes, cells


def snapshot_grids(grid, datasets):
    """Every payload domain must be exposed once, including the volume."""
    children = grid.findall("./Grid")
    names = [child.get("Name") for child in children]
    expected = {"Volume"}
    if any(name.startswith("Boundary/") for name in datasets):
        expected.add("Boundary")
    require(len(names) == len(set(names)) and set(names) == expected,
            "Missing, duplicate or unexpected XDMF grid")
    require(all(child.get("GridType") == "Uniform" for child in children), "Invalid XDMF child grid type")
    return children


def require_binding(element, dataset):
    """Check semantic references, not only the referenced array's dimensions."""
    require(element is not None, f"Missing XDMF element for /{dataset}")
    items = element.findall("./DataItem")
    require(len(items) == 1 and (items[0].text or "").strip().split(":/", 1)[-1] == dataset,
            f"Incorrect XDMF dataset binding for /{dataset}")


def cell_records(name, topology, shape, identifiers, tags, connectivity, node_ids):
    """Decode all cell records without allowing zip/dict/indexing to hide corruption."""
    def integer(value):
        try:
            return operator.index(value)
        except TypeError:
            raise RuntimeError(f"Non-integer HDF5 cell data: {name}") from None

    require(topology is not None, f"Missing XDMF topology: {name}")
    count = len(identifiers)
    require(len(tags) == count, f"Cell ID/tag lengths differ: {name}")
    require(topology.get("NumberOfElements") == str(count), f"XDMF cell count mismatch: {name}")
    kind = topology.get("TopologyType")
    require(kind in (("Mixed", "Tetrahedron") if name == "Volume" else ("Triangle", "Polyline")),
            f"Invalid XDMF topology type: {name}")
    width, vtk_type = {"Mixed": (0, 0), "Tetrahedron": (4, 10), "Triangle": (3, 5), "Polyline": (2, 3)}[kind]
    if width:
        require(tuple(shape) == (count, width), f"Topology connectivity shape mismatch: {name}")
        if width == 2:
            require(topology.get("NodesPerElement") == "2", "Invalid XDMF polyline width")
    else:
        require(len(shape) == 1, "Mixed topology needs one connectivity stream")
    cells, offset = {}, 0
    for row, cell in enumerate(identifiers):
        identifier = integer(cell)
        require(identifier not in cells, f"Duplicate HDF5 cell ID: {name}/{identifier}")
        if width:
            indices = connectivity[row]
            cell_type = vtk_type
        else:
            require(offset < len(connectivity), "Truncated mixed connectivity")
            code = integer(connectivity[offset]);offset += 1
            require(code in (4, 5), f"Unsupported mixed cell {code}")
            arity, cell_type = (3, 5) if code == 4 else (4, 9)
            require(offset + arity <= len(connectivity), "Truncated mixed connectivity")
            indices = connectivity[offset:offset+arity];offset += arity
        indices = tuple(integer(i) for i in indices)
        require(all(0 <= i < len(node_ids) for i in indices), f"Invalid HDF5 point index: {name}")
        cells[identifier] = (integer(tags[row]), tuple(node_ids[i] for i in indices), cell_type)
    if not width:
        require(offset == len(connectivity), "Trailing mixed connectivity")
    return cells


def grid_bindings(child, field_components):
    """Validate geometry and attribute names, centers, shapes and dataset references."""
    name = child.get("Name")
    require(len(child.findall("./Topology")) == len(child.findall("./Geometry")) == 1,
            "Missing or duplicate XDMF topology/geometry")
    require_binding(child.find("./Topology"), name + "/connectivity")
    geometry = child.find("./Geometry")
    require(geometry is not None and geometry.get("GeometryType") == "XYZ", "Invalid XDMF geometry")
    require_binding(geometry, "Mesh/coordinates")
    expected = {key: ("Fields/" + key, "Node", components) for key, components in field_components.items()}
    for key in ("mesh_node_id", "algebra_node_id", "owner"):
        expected[key] = ("Mesh/" + key, "Node", 1)
    for key in ("physical_tag", "mesh_element_id"):
        expected[key] = (name + "/" + key, "Cell", 1)
    attributes = child.findall("./Attribute")
    names = [item.get("Name") for item in attributes]
    require(len(names) == len(set(names)) and set(names) == set(expected), "Missing or duplicate XDMF attributes")
    for item in attributes:
        dataset, center, components = expected[item.get("Name")]
        shape = ("Scalar" if components == 1 else "Vector" if components <= 3 else
                 "Tensor6" if components == 6 else "Tensor" if components == 9 else "Matrix")
        require(item.get("Center") == center and item.get("AttributeType") == shape,
                f"Invalid XDMF attribute metadata: {item.get('Name')}")
        require_binding(item, dataset)


def read_hdf5(path, h5dump):
    """Read exact integer and round-trip binary64 text using the native CLI."""
    import numpy as np
    result = subprocess.run([str(h5dump), "-x", "-m", "%.17g", str(path)],
                            capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, f"h5dump failed for {path}: {result.stderr}")
    root = ET.fromstring(result.stdout)
    ns = {"h": "http://hdfgroup.org/HDF5/XML/schema/HDF5-File.xsd"}
    arrays = {}
    for item in root.findall(".//h:Dataset", ns):
        name = item.get("H5Path").lstrip("/")
        require(name not in arrays, f"Duplicate HDF5 dataset: {name}")
        dimensions = item.find("./h:Dataspace/h:SimpleDataspace", ns)
        require(dimensions is not None, f"Unsupported HDF5 dataspace: {name}")
        shape = tuple(int(d.get("DimSize")) for d in dimensions.findall("./h:Dimension", ns))
        atomic = item.find("./h:DataType/h:AtomicType", ns)
        require(atomic is not None and len(atomic) == 1, f"Unsupported HDF5 datatype: {name}")
        kind = atomic[0].tag.rsplit("}", 1)[-1]
        size = int(atomic[0].get("Size"))
        if kind == "IntegerType":
            dtype = np.dtype(("i" if atomic[0].get("Sign") == "true" else "u") + str(size))
            cast = int
        else:
            require(kind == "FloatType" and size in (4, 8), f"Unsupported numeric type: {name}")
            dtype = np.dtype("f" + str(size))
            cast = float
        values = item.find("./h:Data/h:DataFromFile", ns)
        tokens = [] if values is None else "".join(values.itertext()).split()
        array = np.asarray([cast(v) for v in tokens], dtype=dtype)
        require(array.size == int(np.prod(shape)), f"h5dump data length disagrees with shape: {name}")
        arrays[name] = array.reshape(shape)
    require(arrays, f"No numeric datasets in {path}")
    return arrays


def verify(ascii_path, xdmf_path, ranks, h5dump=None):
    import numpy as np
    h5dump = h5dump or shutil.which("h5dump")
    require(h5dump is not None, "Set --h5dump to the native HDF5 command")
    tree = ET.parse(xdmf_path)
    grid = tree.find("./Domain/Grid")
    require(grid is not None and grid.get("CollectionType") == "Spatial", "Missing spatial XDMF collection")
    files = {}
    for item in tree.findall(".//DataItem"):
        require(item.get("Format") == "HDF", "Unexpected inline/missing HDF data item")
        file, dataset = item.text.strip().split(":/", 1)
        if file not in files:
            files[file] = read_hdf5(xdmf_path.parent/file, h5dump)
        require(dataset in files[file], f"Missing HDF5 dataset: /{dataset}")
        array = files[file][dataset]
        require(tuple(map(int, item.get("Dimensions").split())) == array.shape,
                f"XDMF shape disagrees with /{dataset}")
        require(int(item.get("Precision")) == array.dtype.itemsize and
                {"Float": "f", "Int": "i", "UInt": "u"}.get(item.get("NumberType")) == array.dtype.kind,
                f"XDMF number type disagrees with /{dataset}")
    require(len(files) == 1, "One snapshot must reference exactly one shared payload")
    checked_nodes, checked_cells = 0, 0
    for data in files.values():
        require(data["Mesh/mesh_node_id"].ndim == 1, "Invalid HDF5 point ID shape")
        node_ids = data["Mesh/mesh_node_id"][:].tolist()
        require(len(node_ids) == len(set(node_ids)), "Duplicate shared points")
        require(data["Mesh/coordinates"].shape == (len(node_ids), 3), "Invalid HDF5 coordinate shape")
        for name in ("mesh_node_id", "owner", "algebra_node_id"):
            require(data["Mesh/"+name].shape == (len(node_ids),), f"Invalid HDF5 point metadata shape: {name}")
            require(data["Mesh/"+name].dtype.kind == "i", f"Invalid HDF5 point metadata type: {name}")
        field_components = {}
        for name, values in data.items():
            if name.startswith("Fields/"):
                require(values.ndim in (1, 2) and values.shape[0] == len(node_ids), f"Invalid HDF5 point field shape: {name}")
                components = 1 if values.ndim == 1 else values.shape[1]
                require(components > 0, f"Empty HDF5 point field: {name}")
                field_components[name[len("Fields/"):]] = components
        actual = {"coordinates": data["Mesh/coordinates"][:],
                  **{name[len("Fields/"):]: values for name, values in data.items() if name.startswith("Fields/")},
                  **{name: data["Mesh/"+name][:] for name in ("mesh_node_id", "owner", "algebra_node_id")}}
        for name, array in actual.items():
            require(np.isfinite(array).all(), f"Nonfinite output: {name}")
        positions = {node: i for i, node in enumerate(node_ids)}
        for child in snapshot_grids(grid, data):
            name = child.get("Name")
            grid_bindings(child, field_components)
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
            identifiers, tags = data[name+"/mesh_element_id"][:], data[name+"/physical_tag"][:]
            require(identifiers.ndim == tags.ndim == 1, f"Invalid HDF5 cell metadata shape: {name}")
            require(all(values.dtype.kind == "i" for values in (conn, identifiers, tags)),
                    f"Invalid HDF5 cell data type: {name}")
            cells = cell_records(name, child.find("./Topology"), conn.shape, identifiers, tags, conn, node_ids)
            require(cells == expected_cells, f"Cell topology/tag/ID mismatch: {name}")
            checked_cells += len(cells)
        require(data["Partition/io_modes"].shape == (ranks, 3) and data["Partition/io_modes"].dtype.kind == "u",
                "Invalid I/O mode diagnostic shape/type")
        modes = data["Partition/io_modes"][:].tolist()
        require(len(modes) == ranks and all(n == c+i and n > 0 for n,c,i in modes), "Invalid I/O mode diagnostics")
        if ranks > 1:
            require(all(c > 0 for n,c,i in modes), "A rank performed no actual collective I/O")
    return {"status": "passed", "ranks": ranks, "checked_node_records": checked_nodes,
            "checked_cells": checked_cells, "actual_io_modes": modes,
            "comparison": "exact", "reader": "native-h5dump-xml", "xdmf": str(xdmf_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ascii", type=Path, required=True)
    parser.add_argument("--xdmf", type=Path, required=True)
    parser.add_argument("--ranks", type=int, required=True)
    parser.add_argument("--h5dump", type=Path, help="Native h5dump executable; default: search PATH")
    args = parser.parse_args()
    require(args.ranks >= 1, "Rank count must be positive")
    print(json.dumps(verify(args.ascii, args.xdmf, args.ranks, args.h5dump), indent=2))


if __name__ == "__main__":
    main()
