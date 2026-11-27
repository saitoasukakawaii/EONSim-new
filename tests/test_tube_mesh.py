"""Independent mesh-volume, face-incidence and cross-domain interface checks."""
import json
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

    def test_explicit_single_clamped_slab(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            generate(root,sectors=8,axial=1,clamped_slab=True)
            xyz,cells,boundary=read(root/'solid.msh')
            clamped={node for face,tag in boundary.items() if tag in (11,12) for node in face}
            self.assertEqual(clamped,set(xyz))
            self.assertTrue(all(volume(xyz,t)>0 for t in cells))

    def test_bent_tube_volume_cap_normals_and_interface(self):
        from generate_curved import generate as curved
        direction=(1.,2.,-3.)
        exact_volume=12*.25**2*math.sin(2*math.pi/12)*1.5/2
        errors=[]
        with tempfile.TemporaryDirectory() as temp:
            for axial in (4,8,16):
                path=curved(Path(temp)/str(axial),axial=axial,direction=direction,origin=(1.25,-2.5,.6))
                shape=json.loads((path.parent/'geometry.json').read_text())
                interfaces=[]
                for domain,tag in [('fluid',3),('solid',13)]:
                    xyz,cells,faces=read(path.parent/(domain+'.msh'))
                    self.assertTrue(all(volume(xyz,t)>0 for t in cells))
                    interfaces.append({tuple(sorted(xyz[n] for n in face)) for face,t in faces.items() if t==tag})
                    if domain=='fluid':
                        errors.append(abs(math.fsum(volume(xyz,t) for t in cells)-exact_volume))
                        for cap,origin,normal in [(1,shape['inlet_center'],shape['inward_direction']),
                                                  (2,shape['outlet_center'],shape['outlet_direction'])]:
                            nodes={n for face,t in faces.items() if t==cap for n in face}
                            self.assertTrue(nodes)
                            for n in nodes:
                                self.assertLess(abs(sum((x-y)*v for x,y,v in zip(xyz[n],origin,normal))),2e-14)
                self.assertEqual(interfaces[0],interfaces[1])
            self.assertGreater(min(errors[0]/errors[1],errors[1]/errors[2]),3.8)
            for kwargs in [dict(direction=(0,0,0)),dict(bend_degrees=360),dict(length=.25,bend_degrees=170)]:
                with self.assertRaises(ValueError):curved(Path(temp)/'invalid',**kwargs)

    def test_decimal_outlet_station(self):
        with tempfile.TemporaryDirectory() as root:
            generate(root,sectors=6,axial=9,length=.12,radial=1)
            for domain,tag in [('fluid',2),('solid',12)]:
                xyz,_,boundary=read(Path(root)/(domain+'.msh'))
                cap={face for face in boundary if all(xyz[n][0]==.12 for n in face)}
                self.assertTrue(cap)
                self.assertEqual(cap,{face for face,value in boundary.items() if value==tag})

    def test_invalid_geometry(self):
        with tempfile.TemporaryDirectory() as root:
            for change in (dict(radius=0),dict(thickness=-1),dict(length=float('nan')),dict(sectors=3),dict(axial=1)):
                with self.assertRaises(ValueError):generate(root,**change)


if __name__=='__main__':unittest.main()
