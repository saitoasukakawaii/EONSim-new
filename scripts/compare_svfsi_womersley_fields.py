"""Audit final EONSim/svFSI P1 fields on matched cells. Reading svFSI output requires VTK."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct

from audit_rigid_tube_fields import p1_square
import compare_svfsi_womersley as sv
import study_rigid_tube as tube
import study_womersley as study


def read_svfsi_state(path, nodes, cells):
    from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridReader
    reader = vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(path))
    reader.Update()
    mesh = reader.GetOutput()
    if (reader.GetErrorCode() or mesh.GetNumberOfPoints()!=len(nodes)
            or mesh.GetNumberOfCells()!=len(cells)):
        raise ValueError('svFSI result mesh does not match the source mesh dimensions')
    # This svFSI version writes result geometry as Float32 without GlobalNodeID.
    # Match the exact rounded original coordinates, independent of output ordering.
    lookup = {struct.pack('<3f',*xyz):n for n,xyz in nodes.items()}
    if len(lookup)!=len(nodes):
        raise ValueError('Source nodes coincide at the svFSI output coordinate precision')
    ids = [lookup[struct.pack('<3f',*mesh.GetPoint(i))] for i in range(len(nodes))]
    if set(ids)!=nodes.keys():
        raise ValueError('svFSI results do not cover the original node IDs')
    exported = Counter()
    for i in range(len(cells)):
        tet = mesh.GetCell(i)
        if tet.GetCellType()!=10 or tet.GetNumberOfPoints()!=4:
            raise ValueError('Expected only linear tetrahedra in the svFSI result')
        exported[tuple(sorted(ids[tet.GetPointId(j)] for j in range(4)))] += 1
    if exported!=Counter(tuple(sorted(t)) for t in cells):
        raise ValueError('svFSI result tetrahedra differ from the original mesh')
    data = mesh.GetPointData()
    velocity,pressure = data.GetArray('Velocity'),data.GetArray('Pressure')
    for array,width in ((velocity,3),(pressure,1)):
        if array is None or array.GetNumberOfComponents()!=width or array.GetNumberOfTuples()!=len(ids):
            raise ValueError('Invalid svFSI velocity or pressure array')
    state = {n:(*velocity.GetTuple3(i),pressure.GetTuple1(i)) for i,n in enumerate(ids)}
    if not all(math.isfinite(v) for row in state.values() for v in row):
        raise ValueError('Nonfinite svFSI field')
    return state


def compare_fields(case, directory):
    result = sv.compare(case,directory)
    config,_,_,_ = study.study_parameters(case)
    nodes,cells,faces = tube.read_mesh(case/config['mesh'])
    eon = tube.fields(case,1)
    if eon.keys()!=nodes.keys():
        raise ValueError('EONSim result does not cover the original node IDs')
    steps = result['steps']
    outputs = directory/'1-procs'
    external = read_svfsi_state(outputs/f'result_{steps:03d}.vtu',nodes,cells)
    volume = reference2 = velocity2 = pressure2 = 0.
    for tet in cells:
        v = tube.determinant(nodes,tet)/6
        if v<=0:
            raise ValueError('Nonpositive source tetrahedron')
        volume += v
        for c in range(3):
            reference2 += p1_square([eon[n][c] for n in tet],v)
            velocity2 += p1_square([external[n][c]-eon[n][c] for n in tet],v)
        pressure2 += p1_square([external[n][3]-eon[n][3] for n in tet],v)
    flux,area,p = tube.surface_integrals(nodes,faces,external)
    areas = {sv.FACE_NAMES[t]:v for t,v in area.items()}
    for file,quantity in [('B_NS_Velocity_flux.txt',flux),
                          ('B_NS_Pressure_average.txt',{t:v/area[t] for t,v in p.items()})]:
        recorded = sv.read_table(outputs/file,areas,steps)[-1]
        for tag,value in quantity.items():
            # The boundary text tables have fewer digits than the binary fields.
            if not math.isclose(value,recorded[sv.FACE_NAMES[tag]],rel_tol=1e-4,abs_tol=5e-9):
                raise ValueError(f'svFSI boundary table and VTU differ for tag {tag} in {file}')
    return dict(step=steps,nodes=len(nodes),tetrahedra=len(cells),
                velocity_l2_difference_over_eonsim_norm=math.sqrt(velocity2/reference2),
                pressure_rms_difference_over_drop_amplitude=math.sqrt(pressure2/volume)/tube.DROP,
                svfsi_vtu_end_flow=(flux[2]-flux[1])/2,
                svfsi_vtu_pressure_drop=p[1]/area[1]-p[2]/area[2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(compare_fields(args.case,args.work),indent=2,allow_nan=False))


if __name__=='__main__':
    main()
