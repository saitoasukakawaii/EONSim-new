"""Negative controls for reading the actual four-rank tube output (offline)."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from study_hydrostatic_fsi import recovered_state
from study_rigid_tube import read_mesh


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('folder',type=Path)
    args=cli.parse_args()
    stem='tube_step4'
    mesh=read_mesh(args.folder/'fluid.msh')
    expected=recovered_state(args.folder,stem,mesh,False,4)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        def piece(i):
            return root/f'{stem}_rank{i}.vtu'
        def rejected(label):
            try:
                recovered_state(root,stem,mesh,False,4)
            except (ValueError,FileNotFoundError) as error:
                print(label, type(error).__name__, str(error))
                return
            raise ValueError(f'Invalid input accepted: {label}')
        for i in range(3):
            shutil.copyfile(args.folder/piece(i).name,piece(i))
        rejected('missing rank 3')
        shutil.copyfile(args.folder/piece(3).name,piece(3))
        tree=ET.parse(piece(3))
        array=tree.find('.//Piece/PointData/DataArray[@Name="pressure"]')
        indices=tree.find('.//Piece/Cells/DataArray[@Name="connectivity"]').text.split()
        values=array.text.split()
        values[int(indices[0])]='nan'
        array.text=' '.join(values)
        tree.write(piece(3))
        rejected('nonfinite active pressure')
        array.text=' '.join(['1e12']*len(values))
        tree.write(piece(3))
        rejected('inconsistent finite shared pressure')
        shutil.copyfile(args.folder/piece(3).name,piece(3))
        tree=ET.parse(piece(0))
        unit=tree.find('.//Piece')
        unit.set('NumberOfPoints','0')
        unit.set('NumberOfCells','0')
        for array in unit.iter('DataArray'):
            array.text=None
        tree.write(piece(4))
        if recovered_state(root,stem,mesh,False,5)!=expected:
            raise ValueError('An empty piece changed the reconstructed field')
        shutil.copyfile(piece(4),piece(3))
        rejected('missing owned cells despite all filenames existing')
        print('additional empty piece preserves all nodes and cells')


if __name__=='__main__':
    main()
