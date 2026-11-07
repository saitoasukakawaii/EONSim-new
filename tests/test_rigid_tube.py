"""Independent mesh topology/geometry checks for polygon-preserving refinement."""
from collections import Counter
import json
import math
from pathlib import Path
import sys
import tempfile
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


if __name__ == '__main__':
    unittest.main()
