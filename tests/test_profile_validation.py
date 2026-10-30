"""Validate archived profiling evidence and reject corrupted measurements; no MPI needed."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from profile_multistep_setup import parse as multistep
from profile_schur_mesh import parse as steady

DATA = ROOT / 'docs/research/data'


def replace_field(text, key, value):
    return re.sub(r'\b' + key + r'=\S+', lambda _: key + '=' + value, text, count=1)


class ProfileValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transient = (DATA / 'transient-assembly-2026-10-30/fluid-r1-n0.log').read_text()
        cls.steady = (DATA / 'assembly-phase-2026-10-30/n2-r2-schur0.log').read_text()

    def test_archived_transient(self):
        for case, marker in [('fluid', 'fluid_step'), ('elastic', 'fsi_step')]:
            for ranks in (1, 2, 4):
                for repeat in range(3):
                    with self.subTest(case=case, ranks=ranks, repeat=repeat):
                        text = (DATA / f'transient-assembly-2026-10-30/{case}-r{ranks}-n{repeat}.log').read_text()
                        self.assertEqual(len(multistep(text, marker)), 10)

    def test_archived_overhead(self):
        logs = sorted((DATA / 'fluid-element-overhead-2026-10-30').glob('r*-n*-on*.log'))
        self.assertEqual(len(logs), 36)
        for log in logs:
            with self.subTest(log=log.name):
                self.assertEqual(len(multistep(log.read_text(), 'fluid_step')), 10)

    def test_zero_iterations_remain_valid(self):
        text = replace_field(self.transient, 'linear_iterations', '0')
        text = replace_field(text, 'snes_iterations', '0')
        self.assertEqual(multistep(text, 'fluid_step')[0]['linear_iterations'], 0)

    def test_archived_steady(self):
        for n in (2, 4, 6):
            for ranks in (1, 2):
                for repeat in range(3):
                    with self.subTest(n=n, ranks=ranks, repeat=repeat):
                        text = (DATA / f'assembly-phase-2026-10-30/n{n}-r{ranks}-schur{repeat}.log').read_text()
                        self.assertTrue(steady(text, ranks)[1])

    def test_transient_invalid_numbers(self):
        for key in ('snes_reason', 'ksp_reason', 'linear_iterations', 'snes_iterations'):
            for value in ('nan', 'inf', '-1', '1.5'):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    multistep(replace_field(self.transient, key, value), 'fluid_step')
        for key, value in [('snes_reason', '0'), ('ksp_reason', '0'), ('domain_rejections', '1'),
                           ('solve_seconds', 'nan'), ('solve_seconds', '-1'),
                           ('residual', 'inf'), ('residual', '-1'), ('callback_seconds', '100')]:
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                multistep(replace_field(self.transient, key, value), 'fluid_step')

    def test_transient_missing_field(self):
        text = re.sub(r'\blinear_iterations=\S+ ', '', self.transient, count=1)
        with self.assertRaises(RuntimeError):
            multistep(text, 'fluid_step')

    def test_transient_pairing(self):
        lines = self.transient.splitlines()
        report = next(i for i, line in enumerate(lines) if line.startswith('solver_report '))
        step = next(i for i, line in enumerate(lines) if line.startswith('fluid_step='))
        lines[report], lines[step] = lines[step], lines[report]
        with self.assertRaises(RuntimeError):
            multistep('\n'.join(lines), 'fluid_step')
        with self.assertRaises(RuntimeError):
            multistep(replace_field(self.transient, 'fluid_step', '2'), 'fluid_step')
        with self.assertRaises(RuntimeError):
            multistep('\n'.join(line for line in self.transient.splitlines() if not line.startswith('fluid_step=10 ')), 'fluid_step')

    def test_steady_missing_or_duplicate_root(self):
        root = next(line for line in self.steady.splitlines() if line.startswith('solver_node rank=1 path=root '))
        for text in (self.steady.replace(root, ''), self.steady + '\n' + root):
            with self.subTest(text_length=len(text)), self.assertRaises(RuntimeError):
                steady(text, 2)

    def test_steady_rank_mismatch(self):
        with self.assertRaises(RuntimeError):
            steady(replace_field(self.steady, 'ranks', '1'), 2)

    def test_steady_missing_metric(self):
        with self.assertRaises(RuntimeError):
            steady(re.sub(r'\bsolve_seconds=\S+ ', '', self.steady, count=1), 2)

    def test_steady_invalid_numbers(self):
        for key in ('snes_reason', 'ksp_reason', 'linear_iterations'):
            for value in ('nan', 'inf', '-1', '1.5'):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    steady(replace_field(self.steady, key, value), 2)


if __name__ == '__main__':
    unittest.main()
