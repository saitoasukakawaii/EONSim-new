"""Independent tests of reference-volume weighting and phase coverage rejection."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fsi_field_cycles import read_snapshot,difference,compare_series,pressure_drop


class Fields(unittest.TestCase):
    def test_reference_volume_constant_field(self):
        with tempfile.TemporaryDirectory() as work:
            p=Path(work)/'one.vtu'
            p.write_text('''<VTKFile><UnstructuredGrid><Piece><Points><DataArray>0 0 0 2 0 0 0 3 0 0 0 4</DataArray></Points><Cells><DataArray Name="connectivity">0 1 2 3</DataArray></Cells><PointData><DataArray Name="mesh_node_id">0 1 2 3</DataArray><DataArray Name="velocity" NumberOfComponents="3">1 2 3 1 2 3 1 2 3 1 2 3</DataArray><DataArray Name="pressure">0 0 0 0</DataArray><DataArray Name="mesh_displacement" NumberOfComponents="3">0 0 0 1 0 0 0 2 0 0 0 3</DataArray></PointData></Piece></UnstructuredGrid></VTKFile>''')
            a=read_snapshot(p);self.assertAlmostEqual(sum(a[1].values()),1/6)
            zero=({k:{**v,'velocity':[0,0,0]} for k,v in a[0].items()},a[1])
            self.assertAlmostEqual(difference(a,zero,{'velocity':1})['velocity'],14**.5)
            self.assertEqual(difference(a,a,{'pressure':.1})['pressure'],0)

    def test_missing_phase_rejected(self):
        with self.assertRaisesRegex(ValueError,'matching phase'):
            compare_series([(1.1,Path('absent')),(1.2,Path('absent'))],1,2,{'velocity':1})

    def test_sparse_cycle_rejected(self):
        with self.assertRaisesRegex(ValueError,'16 phases'):
            compare_series([],1,2,{'velocity':1})

    def test_irregular_times_use_physical_phase(self):
        from unittest.mock import patch
        times=[i/40+.001*(i%3) for i in range(81)]
        times[-1]=2.
        entries=[(t,Path(str(t))) for t in times]
        def fake(path,solid):
            t=float(str(path))
            return ({0:{'velocity':[3*t,0,0],'reference_position':[0,0,0]}},{0:1.})
        with patch('fsi_field_cycles.read_snapshot',side_effect=fake):
            result=compare_series(entries,1.,2.,{'velocity':3.})
        self.assertAlmostEqual(result['velocity'],1.)

    def test_pressure_drop_affine_cube(self):
        import itertools
        nodes={i+2*j+4*k:dict(reference_position=[i,j,k],pressure=[10-3*i+2*j]) for i,j,k in itertools.product((0,1),repeat=3)}
        cells=[]
        for permutation in itertools.permutations(range(3)):
            x=[0,0,0];cell=[0]
            for axis in permutation:
                x[axis]=1;cell.append(x[0]+2*x[1]+4*x[2])
            cells.append(tuple(sorted(cell)))
        result=pressure_drop((nodes,{},cells))
        self.assertAlmostEqual(result['pressure_drop'],3.)
        self.assertAlmostEqual(result['inlet_pressure'],11.)


if __name__=='__main__':unittest.main()
