"""Independent harmonic and accepted-history oracles. Python standard library only."""
import cmath
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import study_womersley as study
from audit_womersley_fields import axial_velocity, quadrature


# 60-digit radial integration of r*(1-J0(z*r)/J0(z)) for alpha=2, R=1.
# This evaluates the velocity profile directly, independently of the J1 flow formula.
Q = complex(.00270880299509330365184, -.00177675152987314366278)


class WomersleyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        (self.directory/'mesh').mkdir()
        self.config = study.case_config(16, 3, 'bdf2')
        (self.directory/'case.json').write_text(json.dumps(self.config))
        geometry = dict(sectors=12, radial=2, axial=2, radius=1., length=2.)
        (self.directory/'mesh/geometry.json').write_text(json.dumps(geometry))

    def history(self, q=Q):
        lines = []
        for step in range(1, 49):
            t = step*self.config['fluid']['dt']
            flow = (q*cmath.exp(1j*study.OMEGA*t)).imag
            for tag, area, flux in ((1,3.,-flow), (2,3.,flow), (3,48*math.sin(math.pi/12),0.)):
                lines.append(f'fluid_boundary_step={step} time={t} tag={tag} area={area} '
                             f'outward_flow={flux} mean_pressure=0')
        return lines+['status=success']

    def analyze(self, lines):
        (self.directory/'solve.log').write_text('\n'.join(lines)+'\n')
        return study.analyze(self.directory)

    def test_reference_and_harmonic_convention(self):
        self.assertLess(abs(study.reference_flow()-Q), 1e-17)
        phases = [2*math.pi*i/16 for i in range(1,17)]
        samples = [3+2*math.sin(t)-.3*math.cos(t)+.5*math.cos(2*t) for t in phases]
        self.assertLess(abs(study.harmonic(samples, phases)-(2-.3j)), 1e-14)
        result = self.analyze(self.history())
        self.assertTrue(result['passed'])
        self.assertLess(result['waveform_relative_rms_error'], 1e-14)

    def test_radial_profile_and_disk_integral(self):
        self.assertEqual(axial_velocity(1.),0j)
        self.assertLess(abs(axial_velocity(.25)-(.001273620685606640-.000873595677611650j)),1e-17)
        n=256
        integral=0j
        for i in range(n+1):
            r=i/n
            weight=1 if i in (0,n) else (4 if i%2 else 2)
            integral+=weight*r*axial_velocity(r*r)
        self.assertLess(abs(2*math.pi*integral/(3*n)-Q),2e-12)

    def test_positive_quadrature_moments(self):
        for order in (3,4):
            rule=quadrature(order)
            self.assertTrue(all(w>0 for _,w in rule))
            degree=2*order-3
            for powers in product(range(degree+1),repeat=4):
                if sum(powers)>degree:
                    continue
                exact=6*math.prod(math.factorial(p) for p in powers)/math.factorial(sum(powers)+3)
                actual=sum(w*math.prod(x**p for x,p in zip(bary,powers)) for bary,w in rule)
                self.assertAlmostEqual(actual,exact,places=14)

    def test_detects_amplitude_phase_and_transient(self):
        for q, metric in ((1.05*Q,'amplitude_relative_error'),
                          (Q*cmath.exp(-.1j),'phase_error_degrees')):
            result = self.analyze(self.history(q))
            self.assertFalse(result['passed'])
            self.assertGreater(result[metric],study.LIMITS[metric])
        lines = self.history()
        lines[48:96] = self.history(1.05*Q)[48:96]
        result = self.analyze(lines)
        self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['amplitude_relative_error'], 0., places=14)
        self.assertGreater(result['cycle_max_change_relative'], .04)

    def test_rejects_incomplete_or_inconsistent_samples(self):
        lines = self.history()
        for bad in (lines[:-1], lines[3:], lines[1:], [*lines[:1], *lines],
                    [lines[0].replace('time=', 'time=2'), *lines[1:]],
                    [lines[0].replace('area=3.0','area=1'), *lines[1:]],
                    [lines[0].replace('mean_pressure=0','mean_pressure=nan'), *lines[1:]]):
            with self.subTest(row=bad[0]), self.assertRaises(ValueError):
                self.analyze(bad)

    def test_replay_rejects_changed_load(self):
        for b in self.config['fluid']['boundaries']:
            if 'pressure_time' in b:
                b['pressure_time']['amplitude'] *= 2
        (self.directory/'case.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'declared Womersley'):
            self.analyze(self.history())


if __name__ == '__main__':
    unittest.main()
