from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fsi_space_metrics import interpolation,distance


class Space(unittest.TestCase):
    def test_affine_reproduction_and_offset(self):
        def value(x):return dict(reference_position=x,pressure=[x[0]+2*x[1]+3*x[2]])
        nodes={i:value(x) for i,x in enumerate([(0,0,0),(1,0,0),(0,1,0),(0,0,1)])}
        coarse=(nodes,{i:1/24 for i in nodes},[(0,1,2,3)])
        fine=({10:value((.1,.2,.3)),11:value((.3,.1,.2))},{10:.1,11:.2})
        stencil=interpolation(coarse,fine,1)
        self.assertLess(distance(coarse,fine,stencil,['pressure'])['pressure'],1e-14)
        fine[0][10]['pressure'][0]+=2;fine[0][11]['pressure'][0]+=2
        self.assertAlmostEqual(distance(coarse,fine,stencil,['pressure'])['pressure'],2)

    def test_no_extrapolation(self):
        nodes={i:dict(reference_position=x) for i,x in enumerate([(0,0,0),(1,0,0),(0,1,0),(0,0,1)])}
        with self.assertRaisesRegex(ValueError,'outside'):
            interpolation((nodes,{},[(0,1,2,3)]),({4:dict(reference_position=(.5,.5,.5))},{4:1}),1)


if __name__=='__main__':unittest.main()
