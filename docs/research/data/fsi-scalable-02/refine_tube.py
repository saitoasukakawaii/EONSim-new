"""Prepare two refined SI meshes for the same perfused quarter artery."""
import argparse
from pathlib import Path
import shutil
import tempfile
from paired_tube import MATERIAL, digest, read_mesh, save
from study_lame_wall import quarter_mesh
from generate_tube import generate


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--template',type=Path,required=True)
    cli.add_argument('--root',type=Path,required=True)
    cli.add_argument('--size',choices=('B','C'),required=True)
    args=cli.parse_args(); root=args.root.resolve(); root.mkdir(parents=True,exist_ok=False)
    sectors,radial,wall,axial={'B':(96,8,4,64),'C':(192,16,8,144)}[args.size]
    info=dict(size=args.size,sectors=sectors,radial=radial,axial=axial,wall=wall,regions={})
    with tempfile.TemporaryDirectory(dir=root) as full:
        generate(full,sectors=sectors,radial=radial,axial=axial,radius=MATERIAL.radius,
                 thickness=MATERIAL.outer_radius-MATERIAL.radius,length=MATERIAL.length,wall_layers=wall)
        for name,tags,region in [('fluid',(5,6),10),('solid',(15,16),20)]:
            path=root/(name+'.msh'); quarter_mesh(Path(full)/path.name,path,tags,region)
            nodes,cells,faces=read_mesh(path)
            info['regions'][name]=dict(nodes=len(nodes),tets=len(cells),boundary_faces=len(faces),sha256=digest(path))
    shutil.copyfile(args.template,root/'case.json'); save(root/'mesh.json',info)


if __name__=='__main__': main()
