"""Export the EONSim rigid tube for svFSI 2022.09.26 on the same tetrahedra."""
import argparse
import base64
import cmath
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import study_rigid_tube as tube
import study_womersley as study


SVFSI_REVISION = '94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571'
FACE_NAMES = {1:'inlet', 2:'outlet', 3:'wall'}
CROSS_CODE_LIMIT = .05


def write_piece(path, nodes, node_ids, cells, element_ids, surface=False):
    """VTK connectivity is local and zero based. svFSI parent IDs are one based."""
    kind = 'PolyData' if surface else 'UnstructuredGrid'
    root = ET.Element('VTKFile',type=kind,version='0.1',byte_order='LittleEndian',header_type='UInt32')
    count = 'NumberOfPolys' if surface else 'NumberOfCells'
    piece = ET.SubElement(ET.SubElement(root,kind),'Piece',NumberOfPoints=str(len(nodes)),
                          **{count:str(len(cells))})

    blocks = []
    offset = 0

    def array(parent, name, dtype, rows, width=1):
        nonlocal offset
        # svFSI infers connectivity length from the byte count. VTK requires
        # scalar connectivity, even though each tetrahedron has four indices.
        packer = struct.Struct('<'+{'Float64':'d','Int32':'i','UInt8':'B'}[dtype]*width)
        payload = b''.join(packer.pack(*row) for row in rows)
        block = base64.b64encode(struct.pack('<I',len(payload))+payload).decode('ascii')
        data = ET.SubElement(parent,'DataArray',type=dtype,Name=name,format='appended',offset=str(offset))
        if name=='Points':
            data.set('NumberOfComponents','3')
        blocks.append(block)
        offset += len(block)

    array(ET.SubElement(piece,'PointData'),'GlobalNodeID','Int32',((i,) for i in node_ids))
    array(ET.SubElement(piece,'CellData'),'GlobalElementID','Int32',((i,) for i in element_ids))
    array(ET.SubElement(piece,'Points'),'Points','Float64',nodes,3)
    elements = ET.SubElement(piece,'Polys' if surface else 'Cells')
    arity = 3 if surface else 4
    array(elements,'connectivity','Int32',cells,arity)
    array(elements,'offsets','Int32',((arity*i,) for i in range(1,len(cells)+1)))
    if not surface:
        array(elements,'types','UInt8',((10,) for _ in cells))
    ET.SubElement(root,'AppendedData',encoding='base64').text = '\n_'+''.join(blocks)+'\n'
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def export_mesh(path, directory):
    coordinates,cells,faces = tube.read_mesh(path)
    ids = sorted(coordinates)
    index = {node:i for i,node in enumerate(ids)}
    write_piece(directory/'fluid.vtu',[coordinates[n] for n in ids],range(1,len(ids)+1),
                [tuple(index[n] for n in tet) for tet in cells],range(1,len(cells)+1))
    tags = {tuple(sorted(face)):tag for tag,face in faces}
    if len(tags)!=len(faces) or set(tags.values())!=set(FACE_NAMES):
        raise ValueError('Expected three distinct tube boundary groups without duplicate faces')
    groups = {tag:[] for tag in FACE_NAMES}
    mapped = set()
    for number,tet in enumerate(cells,1):
        for skip,opposite in enumerate(tet):
            face = tet[:skip]+tet[skip+1:]
            key = tuple(sorted(face))
            tag = tags.get(key)
            if tag is None:
                continue
            if key in mapped:
                raise ValueError('A tagged triangle has two adjacent tetrahedra')
            mapped.add(key)
            a,b,c = (coordinates[n] for n in face)
            normal = tube.cross(tube.sub(b,a),tube.sub(c,a))
            if sum(x*y for x,y in zip(normal,tube.sub(coordinates[opposite],a))) > 0:
                face = (face[0],face[2],face[1])
            groups[tag].append((face,number))
    if len(mapped)!=len(faces):
        raise ValueError('A boundary triangle lacks a unique adjacent tetrahedron')
    for tag,group in groups.items():
        active = sorted({n for face,_ in group for n in face})
        local = {node:i for i,node in enumerate(active)}
        write_piece(directory/(FACE_NAMES[tag]+'.vtp'),[coordinates[n] for n in active],
                    [index[n]+1 for n in active],[tuple(local[n] for n in face) for face,_ in group],
                    [number for _,number in group],surface=True)


def input_text(config):
    fluid = config['fluid']
    return f"""Continue previous simulation: 0
Number of spatial dimensions: 3
Number of time steps: {fluid['steps']}
Time step size: {fluid['dt']:.17g}
Spectral radius of infinite time step: 0
Save results to VTK format: 1
Name prefix of saved VTK files: result
Increment in saving VTK files: {fluid['steps']}
Start saving after time step: 1
Increment in saving restart files: {fluid['steps']}
Verbose: 1
Warning: 1

Add mesh: tube {{
   Mesh file path: fluid.vtu
   Add face: inlet {{
      Face file path: inlet.vtp
   }}
   Add face: outlet {{
      Face file path: outlet.vtp
   }}
   Add face: wall {{
      Face file path: wall.vtp
   }}
}}
Add equation: fluid {{
   Coupled: 1
   Min iterations: 2
   Max iterations: 12
   Tolerance: 1e-8
   Backflow stabilization coefficient: 0
   Density: {fluid['density']}
   Viscosity: Constant {{ Value: {fluid['viscosity']} }}
   Output: Spatial {{
      Velocity: t
      Pressure: t
   }}
   Output: Boundary_integral {{
      Velocity: t
      Pressure: t
   }}
   LS type: GMRES {{
      Max iterations: 10
      Tolerance: 1e-10
      Absolute tolerance: 1e-15
      Krylov space dimension: 150
   }}
   Add BC: inlet {{
      Type: Neu
      Time dependence: Unsteady
      Fourier coefficients file path: inlet.fcs
   }}
   Add BC: outlet {{
      Type: Neu
      Value: 0
   }}
   Add BC: inlet {{
      Type: Dir
      Effective direction: (0,1,1)
      Value: 0
   }}
   Add BC: outlet {{
      Type: Dir
      Effective direction: (0,1,1)
      Value: 0
   }}
   Add BC: wall {{
      Type: Dir
      Value: 0
   }}
}}
"""


def prepare(case, directory):
    config,_,_,_ = study.study_parameters(case)
    if config['time']!=dict(scheme='generalized_alpha',rho_infinity=0.):
        raise ValueError('The matched svFSI case requires generalized_alpha with rho_infinity=0')
    if 'stabilization_tau' in config['fluid']:
        raise ValueError('The matched case uses the default stabilization in each solver')
    directory.mkdir(parents=True)
    export_mesh(case/config['mesh'],directory)
    (directory/'svFSI.inp').write_text(input_text(config))
    # Upstream IFFT adds r*cos(k*t) - i*sin(k*t), starting with k=0.
    (directory/'inlet.fcs').write_text(f'0\n{study.PERIOD:.17g}\n0\n0\n2\n0 0\n0 {-tube.DROP:.17g}\n')


def check_convergence(log, steps):
    """svFSI can write results at its iteration cap or exit zero after a fatal input error."""
    if re.search(r'ERROR occurred|fatal error|Singular matrix detected|\bNaN\b',log,re.I):
        raise ValueError('svFSI reported a solver or input failure')
    pattern = re.compile(r'^\s*NS\s+(\d+)-(\d+)s?\s+\S+\s+\[\s*-?\d+\s+'
                         r'(\S+)\s+(\S+)\s+[^\]]+\]\s+([!\[])\s*(\d+)')
    final_norms = {}
    zero_corrections = 0
    prior_step = prior_iteration = 0
    for line in log.splitlines():
        if not re.match(r'^\s*NS\s+\d+-',line):
            continue
        row = pattern.match(line)
        if row is None:
            raise ValueError('Unrecognized svFSI iteration record: '+line)
        step,iteration = map(int,row.group(1,2))
        if not ((step==prior_step and iteration==prior_iteration+1)
                or (step==prior_step+1 and iteration==1 and (not prior_step or prior_iteration>=2))):
            raise ValueError('Incomplete svFSI iteration history')
        prior_step,prior_iteration = step,iteration
        norms = tuple(map(float,row.group(3,4)))
        if not all(math.isfinite(n) and n>=0 for n in norms):
            raise ValueError('Invalid svFSI normalized residual')
        # PIC.f accepts either normalization. GMRES.f can return with zero
        # iterations when the correction is already below its absolute tolerance.
        final_norms[step] = min(norms)
        if row[5]=='!':
            if int(row[6])!=0 or min(norms)>1e-8:
                raise ValueError('Unconverged svFSI linear solve: '+line)
            zero_corrections += 1
    if prior_iteration<2 or set(final_norms)!=set(range(1,steps+1)) or max(final_norms.values())>1e-8:
        raise ValueError('Incomplete or unconverged svFSI time step')
    return max(final_norms.values()), zero_corrections


def read_table(path, areas, steps):
    lines = [line.split() for line in path.read_text().splitlines() if line.strip()]
    if len(lines)!=steps+2 or set(lines[0])!=set(areas) or len(lines[0])!=len(areas):
        raise ValueError(f'Unexpected columns or step count in {path.name}')
    if len(lines[1])!=len(areas) or any(not math.isclose(float(a),areas[name],rel_tol=2e-6)
                                       for name,a in zip(lines[0],lines[1])):
        raise ValueError(f'Unexpected surface area in {path.name}')
    table = []
    for raw in lines[2:]:
        values = list(map(float,raw))
        if len(values)!=len(areas) or not all(map(math.isfinite,values)):
            raise ValueError(f'Invalid boundary integral in {path.name}')
        table.append(dict(zip(lines[0],values)))
    return table


def compare(case, directory):
    eon = study.analyze(case)
    executable_sha = (directory/'executable.sha256').read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}',executable_sha):
        raise ValueError('Missing svFSI executable SHA-256')
    # Verify the external mesh, both end conditions, Fourier coefficients and
    # solver settings against the original EONSim case when replaying results.
    with tempfile.TemporaryDirectory() as temporary:
        fresh = Path(temporary)/'inputs'
        prepare(case,fresh)
        for path in fresh.iterdir():
            if path.read_bytes()!=(directory/path.name).read_bytes():
                raise ValueError(f'svFSI input differs from matched case: {path.name}')
    samples = eon['samples_per_cycle']
    steps = samples*eon['cycles']
    results = directory/'1-procs'
    final_norm,zero = check_convergence((results/'histor.dat').read_text(),steps)
    angle = 2*math.pi/eon['sectors']
    cap = eon['sectors']*tube.RADIUS**2*math.sin(angle)/2
    areas = dict(inlet=cap,outlet=cap,wall=2*eon['sectors']*tube.RADIUS*tube.LENGTH*math.sin(angle/2))
    flows = read_table(results/'B_NS_Velocity_flux.txt',areas,steps)
    pressures = read_table(results/'B_NS_Pressure_average.txt',areas,steps)
    q = [(r['outlet']-r['inlet'])/2 for r in flows]
    phases = [2*math.pi*i/samples for i in range(1,samples+1)]
    measured = study.harmonic(q[-samples:],phases)
    p = study.harmonic([r['inlet']-r['outlet'] for r in pressures[-samples:]],phases)
    reference = study.reference_flow()
    eon_q = cmath.rect(eon['flow_amplitude'],math.radians(eon['flow_phase_degrees']))
    difference = abs(measured-eon_q)/abs(reference)
    cycle_change = max(abs(a-b) for a,b in zip(q[-samples:],q[-2*samples:-samples]))/abs(reference)
    return dict(svfsi_target_revision=SVFSI_REVISION,svfsi_executable_sha256=executable_sha,
                steps=steps,ranks=1,samples_per_cycle=samples,
                sectors=eon['sectors'],radial=eon['radial'],axial=eon['axial'],
                svfsi_max_final_normalized_residual=final_norm,svfsi_zero_corrections=zero,
                svfsi_flow_amplitude=abs(measured),svfsi_flow_phase_degrees=math.degrees(cmath.phase(measured)),
                svfsi_amplitude_relative_error=abs(abs(measured)/abs(reference)-1),
                svfsi_phase_error_degrees=abs(math.degrees(cmath.phase(measured/reference))),
                svfsi_pressure_drop_amplitude=abs(p),svfsi_pressure_drop_phase_degrees=math.degrees(cmath.phase(p)),
                svfsi_cycle_max_change_relative=cycle_change,eonsim_flow_amplitude=abs(eon_q),
                eonsim_flow_phase_degrees=eon['flow_phase_degrees'],relative_phasor_difference=difference,
                passed=(difference<CROSS_CODE_LIMIT and cycle_change<study.LIMITS['cycle_max_change_relative']
                        and eon['cycle_max_change_relative']<study.LIMITS['cycle_max_change_relative']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True,help='EONSim study directory')
    parser.add_argument('--work',type=Path,required=True,help='New svFSI comparison directory')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--executable',type=Path,help='Run the pinned svFSI binary after exporting')
    mode.add_argument('--analyze-only',action='store_true',help='Replay the two recorded histories')
    parser.add_argument('--check',action='store_true',help='Require the periodic cross-code target')
    args=parser.parse_args()
    if args.check and not (args.executable or args.analyze_only):
        parser.error('--check requires a solve or --analyze-only')
    if not args.analyze_only:
        prepare(args.case,args.work)
    if args.executable:
        executable = args.executable.resolve()
        with (args.work/'solve.log').open('w') as log:
            subprocess.run([executable,'svFSI.inp'],cwd=args.work,stdout=log,stderr=subprocess.STDOUT,check=True)
        (args.work/'executable.sha256').write_text(hashlib.sha256(executable.read_bytes()).hexdigest()+'\n')
    if args.analyze_only or args.executable:
        result = compare(args.case,args.work)
        print(json.dumps(result,indent=2,allow_nan=False))
        if args.check and not result['passed']:
            raise SystemExit('Periodic cross-code flow target missed')
    else:
        print(json.dumps(dict(svfsi_revision=SVFSI_REVISION,input=str(args.work/'svFSI.inp'))))


if __name__=='__main__':
    main()
