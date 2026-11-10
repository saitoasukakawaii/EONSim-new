"""Input-only geometry control: radial projection at fixed topology and DoF count."""
from pathlib import Path
import math,json,hashlib,shutil,sys
b=Path(__file__).resolve().parent;root=b.parents[1];sys.path.insert(0,str(root/'scripts'));import study_rigid_tube as tube
src=b/'elastic-s24-l1-n800';out=b/'elastic-geometry48-preparation';assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={name:sha(src/name) for name in ['case.json','fluid.msh','solid.msh','geometry.json']}
g=json.loads((src/'geometry.json').read_text());assert g['sectors']==24 and g['red_refinements']==1
sectors=g['sectors'];width=2*math.pi/sectors;rows=[];interfaces=[]
for domain,region,tag in [('fluid',10,3),('solid',20,13)]:
 nodes,cells,faces=tube.read_mesh(src/(domain+'.msh'));projected={}
 for i,(x,y,z) in nodes.items():
  if y==0 and z==0:projected[i]=(x,y,z);continue
  angle=math.atan2(z,y);middle=(math.floor(angle/width)+.5)*width
  scale=math.cos(angle-middle)/math.cos(math.pi/sectors)
  projected[i]=(x,y*scale,z*scale)
 values=[tube.determinant(projected,c)/6 for c in cells];assert min(values)>0
 volume=math.fsum(values);r2=1 if domain=='fluid' else 1.2**2-1
 expected=48*.5*math.sin(2*math.pi/48)*r2*g['length'];assert abs(volume-expected)<1e-12*expected
 interface={n for marker,face in faces if marker==tag for n in face}
 assert max(abs(math.hypot(projected[n][1],projected[n][2])-1) for n in interface)<1e-14
 interfaces.append({tuple(round(x,12) for x in projected[n]) for n in interface})
 path=out/(domain+'.msh');tube.write_mesh(path,projected,cells,faces,region=region)
 loaded=tube.read_mesh(path);assert loaded==(projected,cells,faces)
 assert len(projected)==len(nodes) and all(projected[n][0]==nodes[n][0] for n in nodes)
 rows.append(dict(domain=domain,nodes=len(nodes),cells=len(cells),boundary_faces=len(faces),volume=volume,expected_volume=expected,min_cell_volume=min(values),source_sha256=before[domain+'.msh'],projected_sha256=sha(path),topology_and_tags_identical=True,axial_coordinates_identical=True))
assert interfaces[0]==interfaces[1]
shutil.copy2(src/'case.json',out/'case.json')
g.update(sectors=48,seed_sectors=24,fluid_volume=rows[0]['volume'],interface_area=2*48*math.sin(math.pi/48)*g['length'],geometry_control='Radial projection of fixed S24 level1 topology; not an extra field refinement')
(out/'geometry.json').write_text(json.dumps(g,indent=2)+'\n')
assert before=={name:sha(src/name) for name in before}
r=dict(source=str(src),source_inputs=before,prepared_inputs={name:sha(out/name) for name in before},projection_formula='For theta in seed sector with midpoint theta_c: (y,z) *= cos(theta-theta_c)/cos(pi/24); x unchanged. Center unchanged.',domains=rows,matching_interface_nodes=len(interfaces[0]),source_area_relative_deficit=1-24*math.sin(2*math.pi/24)/(2*math.pi),projected_area_relative_deficit=1-48*math.sin(2*math.pi/48)/(2*math.pi),scope='Prepared input only. Same nodes/cells/tags/physics/time, different polygon geometry24->48; solver/response not yet tested. Old nested-space budget stays unchanged; projected mesh must not enter that budget as a field refinement.')
(out/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
