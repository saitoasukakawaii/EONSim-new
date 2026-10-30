"""Synthetic evidence checks; no compiler, solver, CTest or MPI is launched."""
import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'cloud_validate', Path(__file__).resolve().parents[1]/'scripts/cloud/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class EvidenceTests(unittest.TestCase):
    def read(self, cases, names=('a', 'b')):
        inventory = [dict(name=name, properties=[dict(name='LABELS', value=['rank-2'])])
                     for name in names]
        return validator.read_test_results(io.StringIO('<testsuite>'+cases+'</testsuite>'), inventory)

    def test_complete_results(self):
        results = self.read('<testcase name="b" time="1.5"/><testcase name="a"/>')
        self.assertEqual({r['name'] for r in results}, {'a', 'b'})
        self.assertTrue(all(r['status'] == 'passed' and r['ranks'] == [2] for r in results))

    def test_duplicate_cannot_replace_missing(self):
        with self.assertRaisesRegex(RuntimeError, 'duplicate test result'):
            self.read('<testcase name="a"/><testcase name="a"/>')

    def test_missing_or_unknown_results(self):
        for cases in ('', '<testcase name="a"/>', '<testcase name="c"/>'):
            with self.subTest(cases=cases), self.assertRaises(RuntimeError):
                self.read(cases)

    def test_invalid_inventory(self):
        for names in ((), ('a', 'a')):
            with self.subTest(names=names), self.assertRaises(RuntimeError):
                self.read('', names)

    def test_failure_error_and_skip(self):
        for child, expected in (('<failure/>', 'failed'), ('<error/>', 'failed'),
                                ('<skipped/>', 'skipped')):
            with self.subTest(child=child):
                self.assertEqual(self.read('<testcase name="a">'+child+'</testcase>', ('a',))[0]['status'], expected)
        for status in ('disabled', 'notrun'):
            self.assertEqual(self.read(f'<testcase name="a" status="{status}"/>', ('a',))[0]['status'], 'skipped')

    def test_invalid_duration(self):
        for seconds in ('NaN', 'inf', '-1'):
            with self.subTest(seconds=seconds), self.assertRaises(RuntimeError):
                self.read(f'<testcase name="a" time="{seconds}"/>', ('a',))


if __name__ == '__main__':
    unittest.main()
