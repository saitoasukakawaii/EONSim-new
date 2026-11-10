"""Separate fixed polygon field refinement from analytic circular geometry error."""
from pathlib import Path
import sys,math,json,hashlib
b=Path(__file__).resolve().parent;root=b.parents[1];sys.path.insert(0,str(root/'scripts'));import study_rigid_tube as tube
out=b/'fresh-mesh-geometry.json';assert not out.exists()
rows=[]
for family,sectors,length,coarse,fine,domains in [
 ('womersley',96,2,'alpha1-s96-l0-n400','alpha1-s96-l1-n400',['fluid']),
 ('elastic',24,12,'elastic-s24-l0-n800','elastic-s24-l1-n400',['fluid','solid'])]:
 for domain in domains:
  paths=[b/coarse/(domain+'.msh'),b/fine/(domain+'.msh')];meshes=[tube.read_mesh(p) for p in paths]
  expected=tube.refine(*meshes[0]);assert expected==meshes[1],(family,domain,'Not the same midpoint refinement')
  volumes=[]
  for nodes,cells,faces in meshes:
   values=[tube.determinant(nodes,c)/6 for c in cells];assert min(values)>0;volumes.append(math.fsum(values))
  r_outer=1. if domain=='fluid' else 1.2;r_inner=0. if domain=='fluid' else 1.
  circular=math.pi*(r_outer*r_outer-r_inner*r_inner)*length
  polygon=sectors*.5*math.sin(2*math.pi/sectors)*(r_outer*r_outer-r_inner*r_inner)*length
  assert all(abs(v-polygon)<1e-12*polygon for v in volumes)
  assert abs(volumes[0]-volumes[1])<1e-13*polygon
  rows.append(dict(family=family,domain=domain,sectors=sectors,length=length,mesh_paths=[str(p.relative_to(b)) for p in paths],mesh_sha256=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],nodes=[len(m[0]) for m in meshes],cells=[len(m[1]) for m in meshes],volume=volumes,analytic_polygon_volume=polygon,analytic_circular_volume=circular,circular_area_volume_relative_deficit=1-polygon/circular,maximum_boundary_radial_deficit_over_radius=1-math.cos(math.pi/sectors),exact_midpoint_refinement=True,scope='Refinement preserves the polygonal domain. Circular area/radial deficits are geometry metrics, not solution error estimates or a replacement for geometry-response refinement.'))
result=dict(passed=True,rows=rows,source_sha256=hashlib.sha256((root/'scripts/study_rigid_tube.py').read_bytes()).hexdigest(),scope='Actual fresh coarse/fine meshes verified against exact midpoint refinement and independent regular-polygon volume; no new PDE solve or geometry-response qualification')
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(rows,indent=2))
