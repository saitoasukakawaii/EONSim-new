"""Independent momentum, wall and cross-sectional integral checks."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from womersley_reference import velocity_amplitude as velocity, flow_amplitude as flow


class WomersleyReferenceTests(unittest.TestCase):
    def test_wall_and_zero_frequency(self):
        for alpha in (0,1,2,4):
            self.assertLess(abs(velocity(1,alpha)),1e-15)
        self.assertEqual(velocity(.5,0),.01*.75/4)
        self.assertAlmostEqual(flow(0),math.pi*.01/8)
        self.assertLess(abs(velocity(.5,.01)-velocity(.5,0))/abs(velocity(.5,0)),1e-4)

    def test_momentum_equation(self):
        h=1e-4
        for alpha in (1,2,4):
            for r in (.1,.4,.8):
                um,u,up=(velocity(x,alpha) for x in (r-h,r,r+h))
                laplacian=(up-2*u+um)/h**2+(up-um)/(2*h*r)
                self.assertLess(abs(1j*alpha**2*u-laplacian-.01),2e-9)

    def test_flow_integral(self):
        n=1000
        for alpha in (1,2,4):
            integrand=lambda k:2*math.pi*(k/n)*velocity(k/n,alpha)
            integral=(integrand(0)+integrand(n)+sum((4 if k%2 else 2)*integrand(k) for k in range(1,n)))/(3*n)
            self.assertLess(abs(integral-flow(alpha)),2e-14)


if __name__=='__main__':
    unittest.main()
