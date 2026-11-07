"""Exact polynomial oracles for the independent tube-field audit."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_rigid_tube_fields import element_metrics, QUADRATURE, velocity_integrals


class FieldAuditTest(unittest.TestCase):
    def test_all_quartic_simplex_moments(self):
        from itertools import product
        for powers in product(range(5), repeat=4):
            degree = sum(powers)
            if degree > 4:
                continue
            exact = 6*math.prod(math.factorial(p) for p in powers)/math.factorial(3+degree)
            actual = sum(w*math.prod(x**p for x, p in zip(bary, powers)) for bary, w in QUADRATURE)
            self.assertAlmostEqual(actual, exact, places=14, msg=str(powers))

    def test_zero_velocity_has_unit_relative_error(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        error, reference = velocity_integrals(points, [(0, 0, 0, 0)]*4, 1/6)
        self.assertAlmostEqual(error/reference, 1)
        # 1/6 - 4/60 + 2/210 + 2/1260 = 1/9 on the unit simplex.
        self.assertAlmostEqual(reference/(.02/8)**2, 1/9, places=14)

    def test_affine_velocity_on_skew_tetrahedron(self):
        points = [(0, 0, 0), (2, 1, 0), (0, 3, 1), (1, 0, 4)]
        # Trace of the prescribed affine velocity gradient is 2 - 3 + 5.
        values = [(2*x+y+7, x-3*y+z, 2*x+5*z, .02*(1-x/2)) for x, y, z in points]
        volume, divergence, error, bias = element_metrics(points, values)
        self.assertAlmostEqual(volume, 25/6)
        self.assertAlmostEqual(divergence, 4)
        self.assertAlmostEqual(error, 0)
        self.assertAlmostEqual(bias, 0)

    def test_pressure_linear_and_constant_error(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        values = [(0, 0, 0, .02*(1-x/2)+x) for x, y, z in points]
        _, _, error, bias = element_metrics(points, values)
        self.assertAlmostEqual(error, 1/60)  # int x^2 on the unit simplex
        self.assertAlmostEqual(bias, 1/24)   # int x
        values = [(0, 0, 0, .02*(1-x/2)+2) for x, y, z in points]
        _, _, error, bias = element_metrics(points, values)
        self.assertAlmostEqual(error, 4/6)
        self.assertAlmostEqual(bias, 2/6)

    def test_signed_cancellation_does_not_remove_local_error(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        metrics = [element_metrics(points, [(sign*x, 0, 0, .02*(1-x/2))
                                            for x, y, z in points]) for sign in (-1, 1)]
        self.assertAlmostEqual(sum(v*d for v, d, _, _ in metrics), 0)
        self.assertAlmostEqual(sum(v*d*d for v, d, _, _ in metrics), 1/3)

    def test_invalid_geometry_and_nonfinite_field(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        values = [(0, 0, 0, 0)]*4
        with self.assertRaises(ValueError):
            element_metrics([points[1], points[0], *points[2:]], values)
        with self.assertRaises(ValueError):
            element_metrics(points, [*values[:3], (0, 0, math.nan, 0)])


if __name__ == '__main__':
    unittest.main()
