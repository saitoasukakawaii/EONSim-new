"""FSI tests retain the observed solver output when a child fails or times out."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from verify_fsi_inlet import Runner
from verify_fsi_coo import check_batch_injection


class BatchInjectionLogTests(unittest.TestCase):
    marker = 'fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1'

    def test_valid_injection_modes(self):
        for mode in ('worker', 'insert', 'worker_fatal', 'insert_fatal'):
            with self.subTest(mode=mode):
                thread = 1 if mode.startswith('worker') else 0
                record = f'fsi_batch_failure mode={mode} thread={thread} team=2 batch=1\n'
                self.assertEqual(check_batch_injection(record, mode)['thread'], str(thread))

    def test_mpi_interleaved_error_prefix(self):
        # Exact interleaving from the preserved CI worker_fatal log: rank one's
        # partial error prefix reached the launcher before rank zero's marker.
        text = ('EONSim rank fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1\n'
                'EONSim rank 1: callback phase=jacobian origin_rank=0: Injected fatal FSI batch failure\n'
                'status=failed\n'
                '0: callback phase=jacobian origin_rank=0: Injected fatal FSI batch failure\n'
                'status=failed\n\x00')
        self.assertEqual(check_batch_injection(text, 'worker_fatal'),
                         dict(mode='worker_fatal', thread='1', team='2', batch='1'))

    def test_duplicate_markers_are_not_hidden(self):
        for text in (self.marker+'\n'+self.marker, self.marker+' '+self.marker,
                     self.marker+'\nfsi_batch_failure mode=worker_fatal'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')

    def test_missing_or_malformed_records(self):
        for text in ('', self.marker.replace(' thread=1', ''),
                     self.marker.replace(' batch=1', ''),
                     self.marker.replace('team=2', 'team=NaN'),
                     self.marker.replace('batch=1', 'batch=1.5')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')

    def test_wrong_team_or_thread(self):
        for text, mode in ((self.marker.replace('team=2', 'team=1'), 'worker_fatal'),
                           (self.marker.replace('thread=1', 'thread=0'), 'worker_fatal'),
                           (self.marker.replace('thread=1', 'thread=2'), 'worker_fatal'),
                           (self.marker.replace('worker_fatal', 'insert_fatal'), 'insert_fatal')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, mode)

    def test_wrong_mode_or_batch(self):
        for text in (self.marker.replace('worker_fatal', 'worker'),
                     self.marker.replace('batch=1', 'batch=0')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')


class RunnerLogTests(unittest.TestCase):
    def test_output_and_expected_failure(self):
        with tempfile.TemporaryDirectory() as path:
            work = Path(path)
            runner = Runner(sys.executable, None, work)
            out = runner.command([sys.executable, '-c', "print('accepted')"], 'accepted')
            self.assertEqual(out, 'accepted\n')
            self.assertEqual((work/'accepted.log').read_text(), out)
            command = [sys.executable, '-c', "import sys; sys.exit('known failure')"]
            self.assertIn('known failure', runner.command(command, 'rejected', fail='known failure'))

    def test_timeout_keeps_partial_output(self):
        with tempfile.TemporaryDirectory() as path:
            work = Path(path)
            runner = Runner(sys.executable, None, work, timeout=1)
            command = [sys.executable, '-c', "import time; print('step 1', flush=True); time.sleep(30)"]
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                runner.command(command, 'interrupted')
            self.assertEqual((work/'interrupted.log').read_bytes(), b'step 1\n')
            self.assertEqual(caught.exception.output, b'step 1\n')


if __name__ == '__main__':
    unittest.main()
