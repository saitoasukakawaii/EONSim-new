"""Independent mesh topology/geometry checks for polygon-preserving refinement."""
from collections import Counter
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import study_rigid_tube as study


class RefinementTest(unittest.TestCase):
    def test_tube_refinement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for level in (0,1,2):
                study.make_case(root/str(level),12,level)
                nodes,cells,faces = study.read_mesh(root/str(level)/'fluid.msh')
                self.assertEqual(len(cells),216*8**level)
                incidence = Counter(tuple(sorted(t[:i]+t[i+1:])) for t in cells for i in range(4))
                self.assertEqual(set(incidence.values()),{1,2})
                self.assertEqual({f for f,n in incidence.items() if n==1},{tuple(sorted(f)) for _,f in faces})
                self.assertEqual(len(faces),len({tuple(sorted(f)) for _,f in faces}))
                volume = sum(study.determinant(nodes,t)/6 for t in cells)
                self.assertAlmostEqual(volume,6.,places=10)
                self.assertGreater(min(study.determinant(nodes,t) for t in cells),0)
                areas = Counter()
                for tag,face in faces:
                    a,b,c = [nodes[n] for n in face]
                    vector = study.cross(study.sub(b,a),study.sub(c,a))
                    areas[tag] += math.sqrt(sum(v*v for v in vector))/2
                self.assertAlmostEqual(areas[1],3.,places=11)
                self.assertAlmostEqual(areas[2],3.,places=11)
                self.assertAlmostEqual(areas[3],48*math.sin(math.pi/12),places=10)
                if level:
                    # Facet midpoints stay inside the circle; projecting them
                    # onto the circle would silently change the study geometry.
                    radii = [math.hypot(*nodes[n][1:]) for tag,f in faces if tag==3 for n in f]
                    self.assertAlmostEqual(min(radii),math.cos(math.pi/12),places=12)

    def test_reference_scaling_and_geometry_bound(self):
        self.assertAlmostEqual(study.Q_EXACT,math.pi/800,places=15)
        lower = [math.cos(math.pi/s)**4 for s in (12,24,48)]
        self.assertTrue(0<lower[0]<lower[1]<lower[2]<1)

    def test_replay_rejects_changed_reference_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = study.case_config()
            config['fluid']['viscosity'] = 2.
            (root/'case.json').write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,'Case parameters differ'):
                study.analyze(root,12,0)


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux solver-session contract')
class SolverSessionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.outside = subprocess.Popen([sys.executable,'-c','import time;time.sleep(90)'],start_new_session=True)

    def tearDown(self):
        try:
            self.assertIsNone(self.outside.poll(),'Cleanup affected a different solver session')
        finally:
            if self.outside.poll() is None:
                self.outside.terminate()
            self.outside.wait(timeout=5)
            self.temporary.cleanup()

    def fixture(self,exit_launcher=False):
        child = self.root/'child.py'
        child.write_text('import os,signal,time\n'
                         'signal.signal(signal.SIGINT,signal.SIG_IGN)\n'
                         'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                         'open("child-id","w").write(f"{os.getpid()} {os.getsid(0)} {os.getpgrp()}")\n'
                         'time.sleep(60)\n')
        launcher = self.root/'launcher.py'
        launcher.write_text('import os,subprocess,sys,time\nfrom pathlib import Path\n'
                            'subprocess.Popen([sys.executable,"child.py"],preexec_fn=lambda:os.setpgid(0,0))\n'
                            'while not Path("child-id").exists():time.sleep(.01)\n'
                            'print("status=success",flush=True)\n'+
                            ('' if exit_launcher else 'time.sleep(60)\n'))
        return [sys.executable,launcher]

    def check_cleaned(self,name):
        pid,session,group = map(int,(self.root/'child-id').read_text().split())
        self.assertNotEqual(group,session)
        self.assertEqual(study._session_members(session),{})
        record = json.loads((self.root/(name+'.cleanup.json')).read_text())
        self.assertEqual(record['session'],session)
        self.assertEqual(record['after'],{})
        self.assertTrue(any(row.get('pid')==pid and row['signal']=='SIGKILL' for row in record['signals']))

    def test_success_and_failure_keep_logs(self):
        study.run([sys.executable,'-c','print("status=success")'],self.root,'success.log',5)
        self.assertIn('status=success',(self.root/'success.log').read_text())
        self.assertFalse((self.root/'success.log.cleanup.json').exists())
        with self.assertRaisesRegex(RuntimeError,r'solver failed \(7\)'):
            study.run([sys.executable,'-c','print("original failure");raise SystemExit(7)'],self.root,'failure.log',5)
        self.assertIn('original failure',(self.root/'failure.log').read_text())

    def test_timeout_cleans_separate_process_group(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            study.run(self.fixture(),self.root,'timeout.log',1)
        self.check_cleaned('timeout.log')
        self.assertIn('status=success',(self.root/'timeout.log').read_text())

    def test_launcher_success_does_not_hide_running_ranks(self):
        with self.assertRaisesRegex(RuntimeError,'left running child processes'):
            study.run(self.fixture(exit_launcher=True),self.root,'orphan.log',5)
        self.check_cleaned('orphan.log')

    def test_keyboard_interrupt_cleans_owned_session(self):
        command = self.fixture()
        code = ('import sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(Path(study.__file__).parent))+')\n'
                'from study_rigid_tube import run\nrun('+repr(list(map(str,command)))+',Path('+repr(str(self.root))+'),"interrupt.log",60)\n')
        with (self.root/'harness.log').open('w') as log:
            harness = subprocess.Popen([sys.executable,'-c',code],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                deadline = time.monotonic()+10
                while not (self.root/'child-id').exists():
                    self.assertIsNone(harness.poll())
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(.02)
                os.kill(harness.pid,signal.SIGINT)
                self.assertNotEqual(harness.wait(timeout=15),0)
            finally:
                if harness.poll() is None:
                    harness.kill();harness.wait(timeout=5)
                    child = self.root/'child-id'
                    if child.exists():
                        pid = int(child.read_text().split()[0])
                        try:os.kill(pid,signal.SIGKILL)
                        except ProcessLookupError:pass
        self.check_cleaned('interrupt.log')


if __name__ == '__main__':
    unittest.main()
