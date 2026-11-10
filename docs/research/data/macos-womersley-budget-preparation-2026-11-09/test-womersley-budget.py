"""Independent affine/sinusoidal sampling oracles and incomplete-family guards."""
from pathlib import Path
import importlib.util,math,unittest,tempfile,copy,types
import numpy as np
spec=importlib.util.spec_from_file_location('budget',Path(__file__).with_name('audit-womersley-budget.py'));budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)
from analyze_womersley import Mesh
class Wave:
 def __init__(self,n,phase=0.,linear=False,boundary=0.):
  self.definition={'steps_per_cycle':n};self.mesh=Mesh.__new__(Mesh);self.mesh.cells=np.array([[0,1,2,3]]);self.mesh.volumes=np.array([1/6]);self.mesh.volume=1/6;self.seen=[];self.phase=phase;self.linear=linear;self.boundary=boundary
 def state(self,step):
  n=self.definition['steps_per_cycle'];assert 5*n<=step<=6*n;self.seen.append(step)
  value=step if self.linear else math.sin(2*math.pi*(step-5*n)/n+self.phase)
  if step==5*n:value+=self.boundary
  x=np.array([0.,1.,0.,0.]);result=np.zeros((4,4));result[:,0]=x*value;result[:,3]=(1+2*x)*value;return result
class Tests(unittest.TestCase):
 def test_sinusoidal_error_and_exact_affine_space_integrals(self):
  # On a unit tetrahedron E[x²]=1/10 and E[(1+2x)²]=12/5.
  for n in (8,16,400):
   for phase in (0.,.3):
    s=Wave(n,phase);r=budget.sampling(s,dict(velocity=1.,pressure=1.));factor=(1-math.cos(2*math.pi/n))/2
    self.assertAlmostEqual(r['relative_rms']['velocity'],factor/math.sqrt(10),places=14)
    self.assertAlmostEqual(r['relative_rms']['pressure'],factor*math.sqrt(12/5),places=14)
    self.assertEqual(set(s.seen),set(range(5*n,6*n+1)));self.assertEqual(len(s.seen),n+1)
 def test_actual_preceding_endpoint_is_used(self):
  s=Wave(16,boundary=.2);r=budget.sampling(s,dict(velocity=1.,pressure=1.));base=budget.sampling(Wave(16),dict(velocity=1.,pressure=1.))
  self.assertIn(80,s.seen);self.assertNotAlmostEqual(r['relative_rms']['pressure'],base['relative_rms']['pressure'],places=6)
 def test_affine_time_is_reconstructed_exactly(self):
  r=budget.sampling(Wave(16,linear=True),dict(velocity=1.,pressure=1.));self.assertEqual(r['relative_rms'],dict(velocity=0.,pressure=0.))
 def test_incomplete_or_mismatched_family_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);studies=[]
   for i,(level,n) in enumerate(((0,16),(1,16),(1,32))):
    work=root/str(i);work.mkdir();(work/'fluid.msh').write_bytes(b'same fine mesh')
    studies.append(types.SimpleNamespace(work=work,definition=dict(level=level,steps_per_cycle=n,phases=n,warmup=2,alpha=1,executable_sha256='frozen'),receipt=dict(step=6*n)))
   self.assertEqual(budget.family(studies),16)
   bad=copy.deepcopy(studies);bad[2].receipt['step']-=32
   with self.assertRaisesRegex(ValueError,'six cycles'):budget.family(bad)
   bad=copy.deepcopy(studies);bad[1].definition['alpha']=2
   with self.assertRaisesRegex(ValueError,'definitions differ'):budget.family(bad)
   bad=copy.deepcopy(studies);bad[0].definition['phases']=8
   with self.assertRaisesRegex(ValueError,'every accepted phase'):budget.family(bad)
if __name__=='__main__':unittest.main()
