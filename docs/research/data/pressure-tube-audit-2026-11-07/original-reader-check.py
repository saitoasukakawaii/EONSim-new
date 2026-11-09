"""Synthetic I/O oracle only: this helper does not execute either solver."""
import argparse,hashlib,json,math,shutil,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
a=p.parse_args();repo=a.repo.resolve();work=a.work.resolve();work.mkdir()
sys.path[:0]=[str(repo/'scripts'),str(repo/'cases/fsi')]
import vtk
from generate_pressure_tube import generate
from audit_pressure_tube import Domain,eonsim_frame,svfsi_frame,interface_errors
from export_svfsi_tube import array,save_vtk

case=generate(work/'input',sectors=12,radial=1,axial=2)
domains=(Domain(case.parent/'fluid.msh'),Domain(case.parent/'solid.msh'))
frames=[]
for domain,field,dilation in zip(domains,('mesh_displacement','displacement'),(.017,.013)):
    frame={n:dict(reference_position=x,velocity=(-.004*x[0],.002*x[1],.002*x[2]),
                  **{field:(0.,dilation*x[1],dilation*x[2])}) for n,x in domain.nodes.items()}
    if field=='mesh_displacement':
        for n,x in domain.nodes.items():frame[n]['pressure']=(.02+.001*x[0],)
    frames.append(frame)

ids=[sorted(d.nodes) for d in domains]
offset=len(ids[0]);mapping=[{n:i+(offset if j else 0) for i,n in enumerate(names)} for j,names in enumerate(ids)]
coordinates=[x for domain,names in zip(domains,ids) for n in names for x in domain.nodes[n]]
cells=[tuple(index[n] for n in c) for domain,index in zip(domains,mapping) for c in domain.cells]
fields={
    'Velocity':[v for frame,names in zip(frames,ids) for n in names for v in frame[n]['velocity']],
    'Pressure':[frames[0][n]['pressure'][0] for n in ids[0]]+[float('nan')]*len(ids[1]),
    'Solid_displacement':[float('nan')]*(3*len(ids[0]))+[v for n in ids[1] for v in frames[1][n]['displacement']],
    'Mesh_displacement':[v for n in ids[0] for v in frames[0][n]['mesh_displacement']]+[float('nan')]*(3*len(ids[1]))}

def xml(points,connectivity):
    root=ET.Element('VTKFile',type='UnstructuredGrid',version='0.1',byte_order='LittleEndian')
    piece=ET.SubElement(ET.SubElement(root,'UnstructuredGrid'),'Piece',NumberOfPoints=str(len(points)//3),NumberOfCells=str(len(connectivity)))
    array(ET.SubElement(piece,'Points'),'Points',points,3)
    container=ET.SubElement(piece,'Cells')
    array(container,'connectivity',[n for c in connectivity for n in c],kind='Int32')
    array(container,'offsets',range(4,4*len(connectivity)+1,4),kind='Int32')
    array(container,'types',[10]*len(connectivity),kind='UInt8')
    return root,piece

for legacy in (False,True):
    root,piece=xml(coordinates,cells)
    array(ET.SubElement(piece,'CellData'),'Mesh_ID',[1]*len(domains[0].cells)+[2]*len(domains[1].cells),kind='Int32')
    data=ET.SubElement(piece,'PointData')
    for name,values in fields.items():
        alias='Displacement' if legacy and name.endswith('displacement') else name
        array(data,alias,values,1 if name=='Pressure' else 3)
    save_vtk(root,work/('reference-legacy.vtu' if legacy else 'reference-aliased.vtu'))

actual=svfsi_frame(work/'reference-aliased.vtu',domains)
differences={}
for j,(domain,frame,read) in enumerate(zip(domains,frames,actual)):
    for field in frame[next(iter(frame))]:
        differences[f'svfsi-{j}-{field}']=max(abs(x-y) for n in frame for x,y in zip(frame[n][field],read[n][field]))

for j,(domain,frame,names) in enumerate(zip(domains,frames,ids)):
    # Common point table, physical cells only; unused points carry NaNs.
    displacement='displacement' if j else 'mesh_displacement'
    points=list(coordinates)
    for n in names:
        i=mapping[j][n]
        points[3*i:3*i+3]=[x+d for x,d in zip(domain.nodes[n],frame[n][displacement])]
    root,piece=xml(points,[tuple(mapping[j][n] for n in c) for c in domain.cells])
    data=ET.SubElement(piece,'PointData')
    array(data,'mesh_node_id',[9007199254740993+i for i in range(sum(map(len,ids)))],kind='Int64')
    for name in ('velocity',displacement)+(() if j else ('pressure',)):
        width=1 if name=='pressure' else 3
        values=[float('nan')]*(sum(map(len,ids))*width)
        for n in names:
            i=mapping[j][n];values[width*i:width*i+width]=frame[n][name]
        array(data,name,values,width)
    path=work/f'eonsim-{j}.vtu';ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    read=eonsim_frame(path,domain,bool(j))
    for field in frame[next(iter(frame))]:
        differences[f'eonsim-{j}-{field}']=max(abs(x-y) for n in frame for x,y in zip(frame[n][field],read[n][field]))

reader=vtk.vtkXMLUnstructuredGridReader();reader.SetFileName(str(work/'reference-legacy.vtu'));reader.Update()
data=reader.GetOutput().GetPointData()
legacy_names=[data.GetArrayName(i) for i in range(data.GetNumberOfArrays())]
try:
    svfsi_frame(work/'reference-legacy.vtu',domains)
except ValueError as error:
    rejection=str(error)
else:
    raise AssertionError('Legacy ambiguous fields were not rejected')
defects=interface_errors(*domains,*actual)
assert abs(defects['interface_displacement']-.004)<1e-14,defects
assert max(differences.values())<2e-14,differences
report=dict(synthetic_no_solver_execution=True,vtk=vtk.vtkVersion.GetVTKVersion(),
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    maximum_field_errors=differences,legacy_vtk_array_names=legacy_names,legacy_rejection=rejection,
    intentionally_mismatched_interface=defects,
    sources={name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in (
        'scripts/audit_pressure_tube.py','scripts/export_svfsi_tube.py','cases/fsi/generate_pressure_tube.py')},
    scope='Independent VTK and EONSim-layout synthetic file reading; not actual coupled or physical acceptance')
shutil.copy2(__file__,work/'original-reader-check.py')
(work/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,allow_nan=False))
