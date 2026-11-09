"""Independent known-signal and invalid-input checks, with no PDE execution."""
import copy,hashlib,importlib.util,json,math,shutil,unittest
from pathlib import Path

source=Path(__file__).with_name('compare-pressure-audits.py')
spec=importlib.util.spec_from_file_location('comparison',source)
comparison=importlib.util.module_from_spec(spec);spec.loader.exec_module(comparison)
work=Path('/home/tfblab633/EONSim-prod48-20261107')
fixtures=work/'pressure-pipeline-check-2189a8c'
out=work/'pressure-comparison-check-7a344a9';out.mkdir()
left=json.loads((fixtures/'eonsim-analysis.json').read_text())
right=json.loads((fixtures/'svfsi-analysis.json').read_text())


class Comparison(unittest.TestCase):
    def test_known_signal_amplitude_and_phase(self):
        period=2*math.pi
        a=[dict(time=period*j/32,value=3+1.04*math.sin(period*j/32+.01)) for j in range(1,33)]
        b=[dict(time=period*j/32,value=2+math.sin(period*j/32)) for j in range(1,33)]
        result=comparison.difference(comparison.harmonic(a,'value',period),comparison.harmonic(b,'value',period),1.,.05,1.)
        self.assertAlmostEqual(result['relative_amplitude_difference'],.04,places=13)
        self.assertAlmostEqual(result['phase_difference_degrees'],.01*180/math.pi,places=12)
        self.assertAlmostEqual(result['mean_difference'],1.,places=13)
        self.assertTrue(result['passed'])

    def test_phase_wrap_and_unresolved_amplitude(self):
        a=dict(amplitude=1.,phase_degrees=179.5,mean=0.)
        b=dict(amplitude=1.,phase_degrees=-179.5,mean=0.)
        result=comparison.difference(a,b,1.,.05,2.)
        self.assertEqual(result['phase_difference_degrees'],-1.)
        self.assertTrue(result['passed'])
        a['amplitude']=b['amplitude']=0.
        result=comparison.difference(a,b,1.,.05,2.)
        self.assertIsNone(result['relative_amplitude_difference'])
        self.assertIsNone(result['phase_difference_degrees'])
        self.assertFalse(result['passed'])

    def test_real_reader_manufactured_pipeline(self):
        result=comparison.compare(left,right)
        self.assertTrue(result['synthetic_input'])
        self.assertFalse(result['comparison_eligible'])
        self.assertFalse(result['observable_gates_passed'])
        self.assertAlmostEqual(result['observables']['mid_pressure']['relative_amplitude_difference'],0.,places=15)
        (out/'manufactured-comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

    def test_changed_case_and_nonfinite_rejection(self):
        bad=copy.deepcopy(right);bad['case_sha256']='different'
        with self.assertRaisesRegex(ValueError,'Different comparison input'):comparison.compare(left,bad)
        bad=copy.deepcopy(right);bad['minimum_fluid_jacobian']=math.nan
        with self.assertRaisesRegex(ValueError,'Nonfinite'):comparison.compare(left,bad)

    def test_false_acceptance_and_stale_harmonic_rejection(self):
        bad=copy.deepcopy(right);bad['quality_gates']['stage_mass']['maximum']=1.
        with self.assertRaisesRegex(ValueError,'quality gate'):comparison.compare(left,bad)
        bad=copy.deepcopy(right);bad['cycle_differences']['3']['fluid_pressure']['relative_max']=1.
        with self.assertRaisesRegex(ValueError,'periodic acceptance'):comparison.compare(left,bad)
        bad=copy.deepcopy(right);bad['harmonics']['mid_pressure']['amplitude']*=1.01
        with self.assertRaisesRegex(ValueError,'Stored harmonic'):comparison.compare(left,bad)


with (out/'checks.log').open('w') as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Comparison))
for path in (source,Path(__file__)):
    shutil.copy2(path,out/path.name)
record=dict(tests=result.testsRun,passed=result.wasSuccessful(),synthetic_only=True,
    input_files={name:hashlib.sha256((fixtures/name).read_bytes()).hexdigest() for name in ('eonsim-analysis.json','svfsi-analysis.json')},
    helper_files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (source,Path(__file__))})
(out/'report.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
if not result.wasSuccessful():raise SystemExit(1)
