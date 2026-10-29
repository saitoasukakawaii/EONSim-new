"""Independent Tet4 domains: equal interface mesh, different interior layer spacing/counts."""
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'poisson'))
from generate_mesh import write_mesh

def generate(directory,n=2):
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 fluid=directory/'fluid.msh';solid=directory/'solid.msh';write_mesh(fluid,n);write_mesh(solid,n)
 # Independent solid numbering and ordering, different axial spacing. Positive orientation preserved.
 lines=solid.read_text().splitlines()
 for i in range(lines.index('$Nodes')+2,lines.index('$EndNodes')):
  r=lines[i].split();x,y,z=map(float,r[1:]);lines[i]=f'{int(r[0])+100000} {1+.25*x*x:.17g} {y:.17g} {z:.17g}'
 for i in range(lines.index('$PhysicalNames')+2,lines.index('$EndPhysicalNames')):
  r=lines[i].split();r[1]=str(int(r[1])+10);lines[i]=' '.join(r)
 for i in range(lines.index('$Elements')+2,lines.index('$EndElements')):
  r=lines[i].split();r[3]=str(int(r[3])+10);start=3+int(r[2]);r[start:]=[str(int(x)+100000) for x in r[start:]];lines[i]=' '.join(r)
 solid.write_text('\n'.join(lines)+'\n')
 # Refine one interior solid tetrahedron only: adds a node and 3 cells without touching interface.
 lines=solid.read_text().splitlines();ns=lines.index('$Nodes');ne=lines.index('$EndNodes');es=lines.index('$Elements');ee=lines.index('$EndElements')
 nodes={int(r[0]):tuple(map(float,r[1:])) for r in (line.split() for line in lines[ns+2:ne])}
 records=[line.split() for line in lines[es+2:ee]]
 target=next(i for i,r in enumerate(records) if r[1]=='4' and all(nodes[int(v)][0]>1 for v in r[-4:]))
 old=records.pop(target);ids=list(map(int,old[-4:]));nid=max(nodes)+1;center=[sum(nodes[v][d] for v in ids)/4 for d in range(3)]
 nodes[nid]=center
 # Replacing each vertex with the barycenter preserves orientation.
 eid=max(int(r[0]) for r in records)+1
 for a in range(4):
  v=ids.copy();v[a]=nid;records.append([str(eid+a),'4','2','20','1']+list(map(str,v)))
 solid.write_text('\n'.join(lines[:ns+1]+[str(len(nodes))]+[str(k)+' '+' '.join(format(x,'.17g') for x in p) for k,p in reversed(list(nodes.items()))]+['$EndNodes','$Elements',str(len(records))]+[' '.join(r) for r in records]+['$EndElements','']))
 constraint=lambda t,c:dict(tag=t,components=c)
 domains=dict(solid_mesh='solid.msh',fluid_region=10,solid_region=20,fluid_interface=2,solid_interface=11,pressure_tags=[1],
  fluid_constraints=[constraint(1,[1,2]),constraint(3,[1]),constraint(4,[1]),constraint(5,[2]),constraint(6,[2])],
  mesh_constraints=[constraint(1,[0,1,2]),constraint(3,[1]),constraint(4,[1]),constraint(5,[2]),constraint(6,[2])],
  solid_constraints=[constraint(12,[0,1,2]),constraint(13,[1]),constraint(14,[1]),constraint(15,[2]),constraint(16,[2])])
 case=dict(mesh='fluid.msh',output='solution.vtu',fsi=dict(body='elastic',domains=domains,young=100,poisson=.3,dt=.02,steps=5,pressure=1),solver=dict(relative_tolerance=1e-10,absolute_tolerance=1e-12,maximum_iterations=30))
 (directory/'case.yaml').write_text(json.dumps(case,indent=2)+'\n')
 return directory/'case.yaml'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).with_name('domains'));p.add_argument('--subdivisions',type=int,default=2);a=p.parse_args();generate(a.output,a.subdivisions)
