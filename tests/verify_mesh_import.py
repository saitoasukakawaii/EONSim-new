"""Gmsh normalization negative cases and a real 4.1 Tet4 regression."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/scalar2d'))
from generate import generate
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh


def convert41(path):
    lines=path.read_text().splitlines()
    start=lines.index('$Nodes');n=int(lines[start+1]);nodes=[r.split() for r in lines[start+2:start+2+n]]
    start=lines.index('$Elements');ne=int(lines[start+1]);groups={}
    for r in lines[start+2:start+2+ne]:
        row=list(map(int,r.split()));dim={1:1,2:2,3:2,4:3,15:0}[row[1]]
        groups.setdefault((dim,row[3],row[1]),[]).append([row[0],*row[3+row[2]:]])
    entities=sorted({(d,t) for d,t,_ in groups});out=['$MeshFormat','4.1 0 8','$EndMeshFormat']
    if '$PhysicalNames' in lines:out+=lines[lines.index('$PhysicalNames'):lines.index('$EndPhysicalNames')+1]
    out+=['$Entities',' '.join(str(sum(d==i for d,_ in entities)) for i in range(4))]
    for d,t in entities:out+=[f'{t} '+('0 0 0' if d==0 else '0 0 0 1 1 1')+f' 1 {t}'+('' if d==0 else ' 0')]
    dim,entity=max(entities)
    ids=[int(r[0]) for r in nodes]
    out+=['$EndEntities','$Nodes',f'1 {n} {min(ids)} {max(ids)}',f'{dim} {entity} 0 {n}']
    out += [r[0] for r in reversed(nodes)]+[' '.join(r[1:]) for r in reversed(nodes)]+['$EndNodes']
    ids=[row[0] for g in groups.values() for row in g]
    out+=['$Elements',f'{len(groups)} {ne} {min(ids)} {max(ids)}']
    for (d,t,kind),rows in reversed(list(groups.items())):out+=[f'{d} {t} {kind} {len(rows)}']+[' '.join(map(str,r)) for r in reversed(rows)]
    out+=['$EndElements'];path.write_text('\n'.join(out)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True,type=Path);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    def run(args,error=None):
        r=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
        assert (r.returncode!=0)==bool(error),r.stdout
        if error:assert error in r.stdout,r.stdout
        return r.stdout
    def negative(name,modify,error,version='2.2'):
        case=generate(a.work/name,n=1,topology='quad',version=version);mesh=case.parent/'mesh.msh';mesh.write_text(modify(mesh.read_text()))
        text=run([a.executable,'-case',case,'-prepare',case.parent/'part','-parts',1],error);(case.parent/'run.log').write_text(text)
        assert not (case.parent/'part'/'manifest.yaml').exists()
    negative('binary',lambda s:s.replace('2.2 0 8','2.2 1 8'),'Supported Gmsh formats')
    negative('version',lambda s:s.replace('2.2 0 8','4.0 0 8'),'Supported Gmsh formats')
    negative('higher',lambda s:s.replace(' 3 2 10 10 ',' 10 2 10 10 '),'Unsupported Gmsh topology/order')
    negative('partitioned',lambda s:s.replace(' 1 2 1 1 ',' 1 3 1 1 1 '),'partition/extra element tags')
    negative('unknown-node',lambda s:s.replace('145 3 2 10 10 17 24 38 31','145 3 2 10 10 17 24 9999 31'),'Unknown Gmsh node reference')
    negative('folded',lambda s:s.replace('38 1.0 1.0 0.0','38 0.2 0.2 0.0'),'Inverted or degenerate 2D element')
    negative('embedded',lambda s:s.replace('38 1.0 1.0 0.0','38 1.0 1.0 1.0'),'constant-z XY plane')
    negative('periodic',lambda s:s+'$Periodic\n0\n$EndPeriodic\n','Unsupported Gmsh section')
    negative('parametric',lambda s:s.replace('2 1 0 4','2 1 1 4'),'Unsupported parametric nodes',version='4.1')
    negative('multiple-groups',lambda s:s.replace('1 0 0 0 1 1 0 1 10 4','1 0 0 0 1 1 0 2 10 20 4'),'exactly one physical group',version='4.1')
    def field(path,ranks):
        values={}
        for rank in range(ranks):
            tree=ET.parse(path.with_name(path.stem+(f'_rank{rank}' if ranks>1 else '')+'.vtu'))
            f={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
            for i,node in enumerate(f['mesh_node_id']):
                if int(f['owner'][i])==rank:values[int(node)]=f['u'][i]
        return values
    baseline=None
    for version in ('2.2','4.1'):
        folder=a.work/f'tet-{version}';folder.mkdir(exist_ok=True);mesh=folder/'mesh.msh';write_mesh(mesh,2,warp=True)
        if version=='4.1':convert41(mesh)
        cfg=dict(mesh='mesh.msh',output='solution.vtu',poisson=dict(diffusivity=1,exact_solution='quadratic',dirichlet_tags=[1,2,3,4,5,6]))
        case=folder/'case.json';case.write_text(json.dumps(cfg))
        for ranks in (1,2,4):
            part=folder/f'part{ranks}';run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
            run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part]);values=field(folder/'solution.vtu',ranks)
            if baseline:assert max(abs(values[k]-baseline[k]) for k in values)<2e-10
            baseline=values
    print('Gmsh rejection checks and Tet4 2.2/4.1 1/2/4 rank equivalence passed')


if __name__=='__main__':main()
