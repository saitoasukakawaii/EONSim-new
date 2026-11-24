"""Write a tagged Gmsh Tet4 domain and outward boundary triangles for svFSI."""
import base64
import struct
import xml.etree.ElementTree as ET

import study_rigid_tube as tube


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


def export_mesh(path, directory, volume_name, face_names):
    coordinates,cells,faces = tube.read_mesh(path)
    ids = sorted(coordinates)
    index = {node:i for i,node in enumerate(ids)}
    write_piece(directory/(volume_name+'.vtu'),[coordinates[n] for n in ids],range(1,len(ids)+1),
                [tuple(index[n] for n in tet) for tet in cells],range(1,len(cells)+1))
    tags = {tuple(sorted(face)):tag for tag,face in faces}
    if len(tags)!=len(faces) or set(tags.values())!=set(face_names):
        raise ValueError('Expected a label for each boundary group and no duplicate faces')
    groups = {tag:[] for tag in face_names}
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
        write_piece(directory/(face_names[tag]+'.vtp'),[coordinates[n] for n in active],
                    [index[n]+1 for n in active],[tuple(local[n] for n in face) for face,_ in group],
                    [number for _,number in group],surface=True)
