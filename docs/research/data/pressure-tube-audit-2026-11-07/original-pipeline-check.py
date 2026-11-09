"""Exercise both analysis paths using manufactured fields, not solver results."""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
a=p.parse_args();repo=a.repo.resolve();work=a.work.resolve();work.mkdir()
sys.path[:0]=[str(repo/'scripts'),str(repo/'cases/fsi')]
from generate_pressure_tube import generate
from audit_pressure_tube import Domain,analyze
from export_svfsi_tube import array,save_vtk,export

case=generate(work/'input',sectors=12,radial=1,axial=2,steps_per_cycle=16,cycles=3)
domains=[Domain(case.parent/name) for name in ('fluid.msh','solid.msh')]
config=json.loads(case.read_text());dt=config['fsi']['dt'];steps=config['fsi']['steps']
eon=work/'eonsim';eon.mkdir();ref=work/'reference';export(case,ref,stage_pressure=True)
(ref/'results').mkdir()
series=[ET.Element('VTKFile',type='Collection',version='0.1') for _ in domains]
collections=[ET.SubElement(root,'Collection') for root in series]

def grid(domain_list):
    coords=[];cells=[];meshids=[];offset=0
    for j,domain in enumerate(domain_list,1):
        ids=sorted(domain.nodes);index={n:offset+i for i,n in enumerate(ids)}
        coords += [v for n in ids for v in domain.nodes[n]]
        cells += [tuple(index[n] for n in c) for c in domain.cells]
        meshids += [j]*len(domain.cells);offset+=len(ids)
    root=ET.Element('VTKFile',type='UnstructuredGrid',version='0.1',byte_order='LittleEndian')
    piece=ET.SubElement(ET.SubElement(root,'UnstructuredGrid'),'Piece',NumberOfPoints=str(offset),NumberOfCells=str(len(cells)))
    array(ET.SubElement(piece,'Points'),'Points',coords,3)
    container=ET.SubElement(piece,'Cells')
    array(container,'connectivity',[n for c in cells for n in c],kind='Int32')
    array(container,'offsets',range(4,4*len(cells)+1,4),kind='Int32')
    array(container,'types',[10]*len(cells),kind='UInt8')
    return root,piece,offset,meshids

for step in range(1,steps+1):
    pressure=.02+.01*math.sin(step*dt)
    for j,domain in enumerate(domains):
        root,piece,n,_=grid([domain]);data=ET.SubElement(piece,'PointData')
        array(data,'mesh_node_id',sorted(domain.nodes),kind='Int64')
        array(data,'velocity',[0.]*(3*n),3)
        array(data,'displacement' if j else 'mesh_displacement',[0.]*(3*n),3)
        if not j:array(data,'pressure',[pressure]*n)
        name=f'solution_step{step}'+('_solid' if j else '')+'.vtu'
        ET.ElementTree(root).write(eon/name,encoding='utf-8',xml_declaration=True)
        ET.SubElement(collections[j],'DataSet',timestep=format(step*dt,'.17g'),file=name)
    root,piece,n,meshids=grid(domains);data=ET.SubElement(piece,'PointData')
    array(data,'Velocity',[0.]*(3*n),3);array(data,'Pressure',[pressure]*n)
    array(data,'Solid_displacement',[0.]*(3*n),3);array(data,'Mesh_displacement',[0.]*(3*n),3)
    array(ET.SubElement(piece,'CellData'),'Mesh_ID',meshids,kind='Int32')
    save_vtk(root,ref/'results'/f'result_{step:03d}.vtu')
for j,root in enumerate(series):
    ET.ElementTree(root).write(eon/('solution_solid.pvd' if j else 'solution.pvd'),encoding='utf-8',xml_declaration=True)

results={}
for name,directory,reference in (('eonsim',eon,False),('svfsi',ref,True)):
    value=analyze(case,directory,reference)
    assert value['periodic'] and all(item['passed'] for item in value['quality_gates'].values()),value
    assert abs(value['harmonics']['mid_pressure']['mean']-.02)<1e-14
    assert abs(value['harmonics']['mid_pressure']['amplitude']-.01)<1e-14
    assert abs(value['harmonics']['mid_pressure']['phase_degrees'])<1e-10
    assert value['endpoint_trapezoidal_volume_budget']['max_absolute_defect']==0.
    expected=dt*(2/3 if reference else 1.)
    assert abs(value['rows'][0]['evaluation_time']-expected)<1e-15
    value['synthetic_fixture_not_a_solver_result']=True
    (work/(name+'-analysis.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    results[name]=dict(periodic=value['periodic'],quality=value['quality_gates'],mid_pressure=value['harmonics']['mid_pressure'],
                       first_evaluation_time=value['rows'][0]['evaluation_time'])

summary=dict(synthetic_no_solver_execution=True,steps=steps,samples_per_cycle=16,results=results,
             source_script_sha256=hashlib.sha256((repo/'scripts/audit_pressure_tube.py').read_bytes()).hexdigest(),
             scope='Manufactured zero-motion uniform-pressure I/O and analysis pipeline; not a coupled elastic solution')
shutil.copy2(__file__,work/'original-pipeline-check.py')
(work/'report.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,allow_nan=False))
