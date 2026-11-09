"""Nested affine patch, exact mass, topology rejection and manufactured I/O."""
import hashlib,importlib.util,json,math,shutil,sys,unittest
from pathlib import Path
import numpy as np

source=Path(__file__).with_name('compare-pressure-fields.py')
spec=importlib.util.spec_from_file_location('comparison',source)
comparison=importlib.util.module_from_spec(spec);spec.loader.exec_module(comparison)
sys.path.insert(0,str(comparison.ROOT/'cases/fsi'))
from generate_pressure_tube import generate
work=Path('/home/tfblab633/EONSim-prod48-20261107')
fixtures=work/'pressure-pipeline-check-2189a8c'
out=work/'pressure-field-comparison-check-7a344a9';out.mkdir()


class FieldComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generate(out/'coarse',sectors=12,radial=1,axial=2,level=0)
        generate(out/'fine',sectors=12,radial=1,axial=2,level=1)

    def test_nested_affine_patch_and_constant_vector_mass(self):
        for name in ('fluid.msh','solid.msh'):
            a=out/'coarse'/name;b=out/'fine'/name
            comparison.nested(a,b,1)
            coarse=comparison.Mesh(a);fine=comparison.Mesh(b)
            indices,weights=comparison.interpolation(coarse,fine)
            transform=np.array([[2.,-1.,3.],[1.,4.,0.],[-2.,0.,3.]])
            left=coarse.xyz@transform+np.array([.3,-.2,.1])
            exact=fine.xyz@transform+np.array([.3,-.2,.1])
            mapped=np.einsum('na,nad->nd',weights,left[indices])
            self.assertLess(float(np.max(abs(mapped-exact))),1e-12)
            constant=np.tile([.05,-.02,.01],(len(fine.ids),1))
            self.assertAlmostEqual(fine.squared(constant)/fine.volume,.003,places=15)

    def test_reject_wrong_refinement_and_boundary(self):
        with self.assertRaisesRegex(ValueError,'node set'):
            comparison.nested(out/'coarse/fluid.msh',out/'fine/fluid.msh',0)
        nodes,cells,faces=comparison.tube.read_mesh(out/'fine/fluid.msh')
        faces[0]=(99,faces[0][1]);path=out/'wrong-boundary.msh'
        comparison.tube.write_mesh(path,nodes,cells,faces)
        with self.assertRaisesRegex(ValueError,'boundary tags'):
            comparison.nested(out/'coarse/fluid.msh',path,1)

    def test_full_manufactured_dual_reader_comparison(self):
        case=fixtures/'input/case.json'
        left=comparison.Study(case,fixtures/'eonsim',fixtures/'eonsim-analysis.json')
        right=comparison.Study(case,fixtures/'reference',fixtures/'svfsi-analysis.json')
        result=comparison.compare(left,right)
        self.assertTrue(result['synthetic_input'])
        self.assertEqual(result['common_phases'],16)
        self.assertEqual(len(result['rms']),5)
        self.assertLess(max(result['relative_rms'].values()),1e-12)
        with self.assertRaisesRegex(ValueError,'common stored phases'):comparison.compare(left,right,phases=7)
        (out/'manufactured-field-comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


with (out/'checks.log').open('w') as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FieldComparison))
for path in (source,Path(__file__),source.with_name('compare-pressure-audits.py')):
    shutil.copy2(path,out/path.name)
record=dict(tests=result.testsRun,passed=result.wasSuccessful(),synthetic_only=True,
    helper_files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (source,Path(__file__),source.with_name('compare-pressure-audits.py'))})
(out/'report.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
if not result.wasSuccessful():raise SystemExit(1)
