"""Lamé equations, polygonal bore areas and mesh compatibility."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import study_lame_wall as wall
import study_rigid_tube as tube


class LameWallTest(unittest.TestCase):
    def test_stress_equilibrium_and_plane_strain_law(self):
        for pi,po in [(.02,0.),(.02,.02),(.03,.05)]:
            self.assertAlmostEqual(wall.lame(wall.INNER,pi,po)[1],-pi)
            self.assertAlmostEqual(wall.lame(wall.OUTER,pi,po)[1],-po)
            r,h = 1.1,1e-5
            u,sr,st = wall.lame(r,pi,po)
            low,high = wall.lame(r-h,pi,po),wall.lame(r+h,pi,po)
            epsr = (high[0]-low[0])/(2*h)
            self.assertAlmostEqual((high[1]-low[1])/(2*h)+(sr-st)/r,0.,places=9)
            sx = wall.POISSON*(sr+st)
            self.assertAlmostEqual(epsr,(sr-wall.POISSON*(st+sx))/wall.YOUNG,places=11)
            self.assertAlmostEqual(u/r,(st-wall.POISSON*(sr+sx))/wall.YOUNG,places=12)
        self.assertAlmostEqual(wall.lame(1.,.02)[0],.0010872727272727273)

    def test_bore_area_linearization(self):
        n,scale = 5,.03
        nodes = {i:(0.,math.cos(i*math.pi/(2*n)),math.sin(i*math.pi/(2*n))) for i in range(n+1)}
        state = {i:(0.,scale*y,scale*z) for i,(_,y,z) in nodes.items()}
        result = wall.bore_section(nodes,state,reversed(nodes))
        self.assertAlmostEqual(result['area'],n*math.sin(math.pi/(2*n))/2)
        self.assertAlmostEqual(result['radial_displacement'],scale)
        self.assertAlmostEqual(result['linear_area_strain'],2*scale)
        self.assertAlmostEqual(result['deformed_area_strain'],(1+scale)**2-1)

    def test_solid_layers_and_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a,b,c = (root/name for name in ('default','one','four'))
            for path,opts in [(a,{}),(b,dict(wall_layers=1)),(c,dict(wall_layers=4))]:
                tube.generate(path,sectors=16,axial=3,radial=2,**opts)
            for name in ('fluid.msh','solid.msh','case.json','geometry.json'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            self.assertEqual((a/'fluid.msh').read_bytes(),(c/'fluid.msh').read_bytes())
            self.assertEqual(json.loads((c/'geometry.json').read_text())['wall_layers'],4)
            interfaces = []
            for name,tag in [('fluid',3),('solid',13)]:
                nodes,cells,faces = tube.read_mesh(c/(name+'.msh'))
                interfaces.append({tuple(sorted(nodes[n] for n in f)) for t,f in faces if t==tag})
                self.assertTrue(all(tube.determinant(nodes,t)>0 for t in cells))
            self.assertEqual(*interfaces)
            self.assertEqual(len(interfaces[0]),2*16*3)
            self.assertEqual(len(cells),6*16*4*3)
            for bad in (0,-1,1.5):
                with self.assertRaises(ValueError):
                    tube.generate(root/'bad',wall_layers=bad)


if __name__=='__main__':
    unittest.main()
