"""Small conforming XY Tri3/Quad4 meshes in supported Gmsh ASCII formats."""
import argparse
import json
import math
from pathlib import Path


def generate(directory, n=4, topology='mixed', version='4.1', distorted=False, permuted=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    nodes=[]
    for j in range(n+1):
        for i in range(n+1):
            x,y=i/n,j/n
            if distorted:
                x+=.12/n*math.sin(math.pi*x)*math.sin(2*math.pi*y)
                y+=.10/n*math.sin(2*math.pi*i/n)*math.sin(math.pi*j/n)
            nodes.append((17+7*(j*(n+1)+i),x,y,0.))
    node=lambda i,j:17+7*(j*(n+1)+i)
    elements=[]
    def add(t,tag,connectivity):elements.append((101+11*len(elements),t,tag,connectivity))
    for j in range(n):add(1,1,[node(0,j+1),node(0,j)]);add(1,2,[node(n,j),node(n,j+1)])
    for i in range(n):add(1,3,[node(i,0),node(i+1,0)]);add(1,4,[node(i+1,n),node(i,n)])
    for j in range(n):
        for i in range(n):
            a,b,c,d=node(i,j),node(i+1,j),node(i+1,j+1),node(i,j+1)
            if topology=='tri' or (topology=='mixed' and i%2==0):add(2,10,[a,b,c]);add(2,10,[a,c,d])
            else:add(3,10,[a,b,c,d])
    if permuted:
        nodes.reverse();elements.reverse()
        elements=[(i,t,tag,[v[0]]+list(reversed(v[1:]))) for i,t,tag,v in elements]
    names=[(1,1,'left'),(1,2,'right'),(1,3,'bottom'),(1,4,'top'),(2,10,'domain'),(3,99,'unused_volume')]
    lines=['$MeshFormat',f'{version} 0 8','$EndMeshFormat','$PhysicalNames',str(len(names))]
    lines += [f'{d} {tag} "{name}"' for d,tag,name in names]+['$EndPhysicalNames']
    if version=='4.1':
        lines+=['$Entities','0 4 1 0']
        lines += [f'{i} 0 0 0 1 1 0 1 {i} 0' for i in range(1,5)]
        lines += ['1 0 0 0 1 1 0 1 10 4 1 2 3 4','$EndEntities','$Nodes',f'1 {len(nodes)} {min(x[0] for x in nodes)} {max(x[0] for x in nodes)}',f'2 1 0 {len(nodes)}']
        lines += [str(x[0]) for x in nodes]+[' '.join(format(v,'.17g') for v in x[1:]) for x in nodes]+['$EndNodes']
        blocks={}
        for e in elements:blocks.setdefault((e[1],e[2]),[]).append(e)
        lines+=['$Elements',f'{len(blocks)} {len(elements)} {min(e[0] for e in elements)} {max(e[0] for e in elements)}']
        for (t,tag),es in blocks.items():
            lines += [f'{1 if t==1 else 2} {tag if t==1 else 1} {t} {len(es)}']
            lines += [f'{e[0]} '+ ' '.join(map(str,e[3])) for e in es]
    else:
        lines+=['$Nodes',str(len(nodes))]+[' '.join(map(str,x)) for x in nodes]+['$EndNodes','$Elements',str(len(elements))]
        lines += [f'{i} {t} 2 {tag} {tag} '+ ' '.join(map(str,v)) for i,t,tag,v in elements]
    lines+=['$EndElements'];mesh=directory/'mesh.msh';mesh.write_text('\n'.join(lines)+'\n')
    case=dict(mesh='mesh.msh',output='solution.vtu',scalar2d=dict(mode='poisson',manufactured='affine',boundaries=[dict(region='left',type='dirichlet'),dict(region='right',type='robin',coefficient=2),dict(region='bottom',type='dirichlet'),dict(region='top',type='neumann')]),solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-12))
    path=directory/'case.json';path.write_text(json.dumps(case,indent=2)+'\n');return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--n',type=int,default=4);p.add_argument('--topology',choices=['tri','quad','mixed'],default='mixed');p.add_argument('--version',choices=['2.2','4.1'],default='4.1');p.add_argument('--distorted',action='store_true');p.add_argument('--permuted',action='store_true');a=p.parse_args()
    print(generate(a.directory,a.n,a.topology,a.version,a.distorted,a.permuted))
