"""Independent mesh-volume, face-incidence and cross-domain interface checks."""
import math
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_tube import generate


def read(path):
    lines=path.read_text().splitlines();start=lines.index('$Nodes')+2;end=lines.index('$EndNodes')
    xyz={int(r[0]):tuple(map(float,r[1:])) for r in map(str.split,lines[start:end])}
    start=lines.index('$Elements')+2;end=lines.index('$EndElements');cells=[];boundary={}
    for row in lines[start:end]:
        r=list(map(int,row.split()));nodes=tuple(r[3+r[2]:])
        if r[1]==4:cells.append(nodes)
        else:boundary[tuple(sorted(nodes))]=r[3]
    return xyz,cells,boundary


def volume(x,t):
    a,b,c,d=[x[i] for i in t];u,v,w=[[p[j]-a[j] for j in range(3)] for p in (b,c,d)]
    return (u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0]))/6


class TubeMesh(unittest.TestCase):
    def test_domains_and_refinement(self):
        errors=[]
        with tempfile.TemporaryDirectory() as temporary:
            for sectors in (8,16,32):
                root=Path(temporary)/str(sectors);generate(root,sectors=sectors,axial=3,radial=2)
                interfaces=[]
                for name,tag,target in [('fluid',3,1.),('solid',13,1.2**2-1)]:
                    xyz,cells,boundary=read(root/(name+'.msh'))
                    volumes=[volume(xyz,t) for t in cells];self.assertGreater(min(volumes),0)
                    expected=sectors*math.sin(2*math.pi/sectors)/2*4*target
                    self.assertAlmostEqual(sum(volumes),expected,places=11)
                    faces=Counter(tuple(sorted(t[:k]+t[k+1:])) for t in cells for k in range(4))
                    self.assertEqual(set(boundary),{f for f,n in faces.items() if n==1})
                    self.assertTrue(all(n in (1,2) for n in faces.values()))
                    interfaces.append({tuple(sorted(xyz[i] for i in f)) for f,t in boundary.items() if t==tag})
                    if name=='fluid':errors.append(abs(sum(volumes)-4*math.pi))
                self.assertEqual(interfaces[0],interfaces[1]);self.assertTrue(interfaces[0])
        self.assertGreater(errors[0]/errors[1],3.8);self.assertGreater(errors[1]/errors[2],3.8)

    def test_invalid_geometry(self):
        with tempfile.TemporaryDirectory() as root:
            for change in (dict(radius=0),dict(thickness=-1),dict(length=float('nan')),dict(sectors=3),dict(axial=1)):
                with self.assertRaises(ValueError):generate(root,**change)


if __name__=='__main__':unittest.main()
