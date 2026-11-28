import tempfile
from pathlib import Path
import unittest

import numpy as np
from scipy.sparse import csr_matrix

from refine_system import FIELDS, WIDE, audit, finite, read_layout, refine, solve_factors


class SavedSystemTests(unittest.TestCase):
    def test_restore_original_variables_and_port(self):
        a = csr_matrix([[1., 0., 0.], [2.**12, 2.**16, -2.], [0., 2., 2.**-12]])
        x = np.array([1., -0.25, 4.])
        rhs = a @ x
        solve, _ = solve_factors(a, True)
        np.testing.assert_allclose(solve(rhs), x, rtol=1e-12)
        layout = (np.array([0, 3, FIELDS.index('RCR')]), np.array([0, 1, 1]),
                  np.array([False, True, False]))
        test = audit(a, a.astype(WIDE), rhs, x, layout)
        self.assertEqual(test['fields']['RCR']['rows'], 1)
        self.assertEqual(test['wide_norm'], 0.)
        self.assertEqual(test['eta_component'], 0.)
        self.assertTrue(test['worst_owner_rows'][0]['identity_equation'])

    def test_owner_coverage_allows_empty_shard_and_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'port.csv').write_text('rows,pressure_row\n2,1\n')
            header = 'row,field,interface\n'
            (root/'rows-0.csv').write_text(header+'0,mesh,0\n1,pressure,1\n')
            empty = root/'rows-1.csv'
            empty.write_text(header)
            fields, owners, _ = read_layout(root, 2)
            self.assertEqual(owners.tolist(), [0, 0])
            self.assertEqual(fields.tolist(), [0, FIELDS.index('RCR')])
            empty.write_text(header+'1,pressure,1\n')
            with self.assertRaises(ValueError):
                read_layout(root, 2)

    @unittest.skipUnless(np.finfo(WIDE).nmant > 52, 'requires extended arithmetic')
    def test_actual_returned_fp64_stagnation(self):
        # Solving 3*x=1 exactly requires a nonrepresentable x.  The extended update
        # improves the temporary value but rounds to the original stored x.
        a = csr_matrix([[3.]], dtype=WIDE)
        seed = np.array([1/3])
        x, rows, why = refine(a, np.ones(1), seed, lambda r: (r/3).astype(float), 5, 1e-23)
        self.assertEqual(x.dtype, np.float64)
        np.testing.assert_array_equal(x, seed)
        self.assertEqual(why, 'no representable update')
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]['stored_fp64_wide_norm'], 1e-23)
        self.assertLess(rows[0]['temporary_wide_norm'], rows[0]['stored_fp64_wide_norm'])

    def test_nonfinite_and_singular_scaling_fail(self):
        with self.assertRaises(ValueError):
            finite(np.array([np.nan]))
        with self.assertRaises(ValueError):
            solve_factors(csr_matrix([[1., 0.], [1., 0.]]), True)


if __name__ == '__main__':
    unittest.main()
