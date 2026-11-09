"""Independent printed-residual and iteration-cap acceptance examples."""
import hashlib,json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_svfsi_convergence import analyze,PIN


class Convergence(unittest.TestCase):
    def setup_case(self,path,rows):
        inputs='Number of time steps: 1\nContinue previous simulation: 0\n'
        for name in ('FSI','mesh'):
            inputs+=f'Add equation: {name} {{\n  Min iterations: 1\n  Max iterations: 2\n  Tolerance: 1e-10\n}}\n'
        (path/'svFSI.inp').write_text(inputs)
        report=dict(svfsi_commit=PIN,mode='linear elastic pressure tube',files={'svFSI.inp':hashlib.sha256(inputs.encode()).hexdigest()})
        (path/'export.json').write_text(json.dumps(report))
        log=path/'solve.log';log.write_text(rows);return log

    @staticmethod
    def rows(local='2e-11',initial='3e-11'):
        return ('\x1b[29m FS 1-1 0.1 [ 0 1.0 1.0 1e-12] [ 5 0 0]\x1b[0m\n'
            ' MS 1-1 0.2 [ 0 1.0 1.0 1e-12] [ 5 0 0]\n'
            ' FS 1-2 0.3 [ -200 2e-11 2e-11 1.0] ! 0 0 0!\n'
            f' MS 1-2s 0.4 [ -200 {local} {initial} 1.0] [ 0 0 0]\n')

    def test_cap_is_not_convergence_and_either_relative_criterion_suffices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            good=analyze(path,self.setup_case(path,self.rows('2e-9','3e-12')))
            self.assertTrue(good['passed']);self.assertEqual(good['iteration_limit_rows'],2)
            bad=analyze(path,self.setup_case(path,self.rows('2e-9','3e-8')))
            self.assertFalse(bad['passed']);self.assertEqual(len(bad['failed_equation_steps']),1)
            self.assertEqual(bad['failed_equation_steps'][0]['equation'],'MS')

    def test_rounded_threshold_is_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);report=analyze(path,self.setup_case(path,self.rows('1.0e-10','2e-9')))
            self.assertFalse(report['passed'])

    def test_whitespace_does_not_drop_valid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);rows=self.rows().replace('1.0]','1.0  ]').replace('1e-12]','1e-12  ]')
            report=analyze(path,self.setup_case(path,rows))
            self.assertTrue(report['passed']);self.assertEqual(report['iteration_rows'],4)

    def test_incomplete_duplicate_nonfinite_and_error_logs_are_rejected(self):
        variants=[(self.rows().replace(' MS 1-1 0.2 [ 0 1.0 1.0 1e-12] [ 5 0 0]\n',''),'iteration'),
            (self.rows().replace(' MS 1-2s',' MS 1-1s'),'iteration'),
            (self.rows('nan','1e-12'),'Invalid'),
            (self.rows()+' MS 1-3 0.5 [ incomplete\n','Unreadable'),
            (self.rows()+'ERROR: failed\n','error'),
            ('','Missing or unexpected')]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            for rows,message in variants:
                with self.assertRaisesRegex(ValueError,message):analyze(path,self.setup_case(path,rows))


if __name__=='__main__':unittest.main()
