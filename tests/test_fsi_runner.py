"""FSI tests retain the observed solver output when a child fails or times out."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from verify_fsi_inlet import Runner


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
