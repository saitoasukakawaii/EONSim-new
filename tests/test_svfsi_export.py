"""Physical geometry invariants and boundary-waveform identity after VTK export."""
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'cases/fsi')]
from export_svfsi_tube import export
from generate_pressure_tube import generate
from study_rigid_tube import cross,sub


def data(tree,name,cast=float):
    return list(map(cast,tree.find(f'.//DataArray[@Name="{name}"]').text.split()))


def read_vtk(path):
    raw=path.read_bytes()
    header,payload=raw.split(b'<AppendedData encoding="raw">',1)
    tree=ET.ElementTree(ET.fromstring(header+b'</VTKFile>'))
    payload=payload[payload.index(b'_')+1:]
    kinds=dict(Float64=('d',8),Int32=('i',4),UInt8=('B',1))
    for node in tree.iter('DataArray'):
        offset=int(node.attrib['offset'])
        n,size,last=struct.unpack_from('<3I',payload,offset)
        lengths=struct.unpack_from('<'+str(n)+'I',payload,offset+12)
        cursor=offset+12+4*n;chunks=[]
        for length in lengths:
            chunks.append(zlib.decompress(payload[cursor:cursor+length]));cursor+=length
        decoded=b''.join(chunks)
        assert len(decoded)==size*(n-1)+last
        code,size=kinds[node.attrib['type']]
        assert len(decoded)%size==0
        values=struct.unpack('<'+str(len(decoded)//size)+code,decoded)
        node.text=' '.join(map(str,values))
    return tree


class ExportTests(unittest.TestCase):
    def test_mesh_motion_variant_does_not_change_physical_solid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',axial=2)
            before=case.read_bytes()
            original=export(case,tmp/'original',stage_pressure=True)
            zero=export(case,tmp/'zero',stage_pressure=True,mesh_poisson=0.)
            self.assertEqual(case.read_bytes(),before)
            a=(tmp/'original/svFSI.inp').read_text()
            b=(tmp/'zero/svFSI.inp').read_text()
            physics,mesh=a.split('Add equation: mesh {')
            changed_physics,changed_mesh=b.split('Add equation: mesh {')
            self.assertEqual(physics,changed_physics)
            self.assertIn('Poisson ratio: 0.29999999999999999',physics)
            self.assertEqual(changed_mesh,mesh.replace('Poisson ratio: 0.3','Poisson ratio: 0'))
            for name in original['files']:
                if name!='svFSI.inp':self.assertEqual(original['files'][name],zero['files'][name])
            self.assertNotIn('mesh_motion_poisson_ratio',original)
            self.assertEqual(zero['mesh_motion_poisson_ratio'],0.)
            for value in (float('nan'),float('inf'),.5,-1.,.2):
                with self.assertRaisesRegex(ValueError,'Mesh Poisson'):
                    export(case,tmp/'bad',mesh_poisson=value)
                self.assertFalse((tmp/'bad').exists())
            with self.assertRaisesRegex(ValueError,'Mesh Poisson'):
                export(case,tmp/'bad',hydrostatic=True,mesh_poisson=0.)

    def test_divergence_geometry_and_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',sectors=12,axial=2,level=1)
            cfg=json.loads(case.read_text())
            for domain in ('fluid','solid'):
                lines=(case.parent/f'{domain}.msh').read_text().splitlines()
                elements=[list(map(int,line.split())) for line in lines[lines.index('$Elements')+2:lines.index('$EndElements')]]
                volume_tags={element[3] for element in elements if element[1]==4}
                self.assertEqual(volume_tags,{cfg['fsi']['domains'][domain+'_region']})
            report=export(case,tmp/'reference')
            triangles={}
            for domain,inner_tag in (('fluid',3),('solid',13)):
                tree=read_vtk(tmp/'reference'/domain/'volume.vtu')
                coords=list(map(float,tree.find('.//Points/DataArray').text.split()))
                xyz=[tuple(coords[i:i+3]) for i in range(0,len(coords),3)]
                cells=data(tree,'connectivity',int);cells=[cells[i:i+4] for i in range(0,len(cells),4)]
                normal=[0.,0.,0.];moment=0.
                for tag in report['meshes'][domain]['tags']:
                    face=read_vtk(tmp/'reference'/domain/f'face-{tag}.vtp')
                    ids=data(face,'GlobalNodeID',int)
                    parents=data(face,'GlobalElementID',int)
                    local=data(face,'connectivity',int)
                    for i,parent in enumerate(parents):
                        nodes=[ids[n]-1 for n in local[3*i:3*i+3]]
                        self.assertTrue(set(nodes)<=set(cells[parent-1]))
                        a,b,c=[xyz[n] for n in nodes]
                        av=[v/2 for v in cross(sub(b,a),sub(c,a))]
                        centroid=[sum(xyz[n][d] for n in cells[parent-1])/4 for d in range(3)]
                        self.assertGreater(sum(v*(a[d]-centroid[d]) for d,v in enumerate(av)),0)
                        moment+=sum(v*a[d] for d,v in enumerate(av))
                        normal=[x+y for x,y in zip(normal,av)]
                        if tag==inner_tag:
                            triangles.setdefault(domain,{})[tuple(sorted((a,b,c)))]=av
                self.assertLess(max(map(abs,normal)),1e-12)
                area=12*math.sin(2*math.pi/12)/2*(1 if domain=='fluid' else 1.2**2-1)
                self.assertAlmostEqual(moment,3*area*12,places=10)
            self.assertEqual(triangles['fluid'].keys(),triangles['solid'].keys())
            for key,value in triangles['fluid'].items():
                self.assertLess(max(abs(a+b) for a,b in zip(value,triangles['solid'][key])),1e-14)

    def test_fourier_sign_and_linear_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',axial=2)
            export(case,tmp/'reference')
            rows=(tmp/'reference/pressure.fcs').read_text().splitlines()
            ti,period,qi,qs=map(float,rows[:4]);n=int(rows[4])
            coefficients=[tuple(map(float,line.split())) for line in rows[5:]]
            self.assertEqual(n,len(coefficients))
            for fraction,value in ((0,.02),(.25,.03),(.5,.02),(.75,.01),(1,.02)):
                t=fraction*period-ti
                evaluated=qi+t*qs+sum(r*math.cos(2*math.pi*k*t/period)-j*math.sin(2*math.pi*k*t/period) for k,(r,j) in enumerate(coefficients))
                self.assertAlmostEqual(evaluated,value,places=15)
            self.assertIn('Equation: lElas',(tmp/'reference/svFSI.inp').read_text())
            inputs=(tmp/'reference/svFSI.inp').read_text()
            self.assertIn('Displacement: Solid_displacement',inputs)
            self.assertIn('Displacement: Mesh_displacement',inputs)
            report=export(case,tmp/'stage',stage_pressure=True)
            self.assertAlmostEqual(report['pressure_time_offset'],2*math.pi/300,places=15)
            shifted=(tmp/'stage/pressure.fcs').read_text().splitlines()
            self.assertEqual(shifted[1:],rows[1:])
            self.assertAlmostEqual(float(shifted[0]),2*math.pi/300,places=15)

    def test_reject_different_material_and_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',axial=2)
            cfg=json.loads(case.read_text())
            cfg['fsi']['material']='neo_hookean';case.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'linear elastic'):
                export(case,tmp/'bad-material')
            cfg['fsi']['material']='linear';cfg['fsi']['pressure_time']['ramp_time']=1
            case.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'startup ramp'):
                export(case,tmp/'bad-ramp')

    def test_output_window_preserves_the_physical_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',axial=2)
            full=export(case,tmp/'full',stage_pressure=True)
            tail=export(case,tmp/'tail',stage_pressure=True,output_start_step=300)
            self.assertEqual(tail['output_start_step'],300)
            for name in full['files']:
                if name!='svFSI.inp':self.assertEqual(full['files'][name],tail['files'][name])
            expected=(tmp/'full/svFSI.inp').read_text().replace('Start saving after time step: 1\n',
                'Start saving after time step: 300\n')
            self.assertEqual((tmp/'tail/svFSI.inp').read_text(),expected)
            for value in (0,601,1.5):
                with self.assertRaisesRegex(ValueError,'output start'):
                    export(case,tmp/'bad-window',output_start_step=value)

    def test_general_pressure_sign_stage_clock_and_no_final_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'eonsim',axial=2,steps_per_cycle=16,cycles=4)
            cfg=json.loads(case.read_text());f=cfg['fsi'];period=f['pressure_time']['period']
            f['pressure_time']['ramp_time']=1.5*period;case.write_text(json.dumps(cfg))
            for stage in (False,True):
                output=tmp/str(stage);report=export(case,output,stage_pressure=stage,general_pressure=True)
                self.assertFalse((output/'pressure.fcs').exists())
                self.assertEqual((output/'svFSI.inp').read_text().count('Time dependence: General'),2)
                for tag in (1,2):
                    words=iter((output/f'pressure-{tag}.txt').read_text().split())
                    dof,count,nodes=(int(next(words)) for _ in range(3));self.assertEqual(dof,1)
                    times=[float(next(words)) for _ in range(count)]
                    self.assertEqual(times[0],0);self.assertGreater(times[-1],f['steps']*f['dt'])
                    face_ids=data(read_vtk(output/'fluid'/f'face-{tag}.vtp'),'GlobalNodeID',int)
                    self.assertEqual(nodes,len(face_ids));actual_ids=[]
                    for _ in range(nodes):
                        actual_ids.append(int(next(words)))
                        values=[float(next(words)) for _ in range(count)]
                        for step in range(f['steps']+1):
                            # Independently evaluate the physical law at its requested
                            # assembly clock, then account for the General-BC sign.
                            t=step*f['dt']-(f['dt']/3 if stage else 0)
                            x=min(1.,max(0.,t/(1.5*period)))
                            expected=(6*x**5-15*x**4+10*x**3)*(.02+.01*math.sin(t))
                            self.assertAlmostEqual(-values[step],expected,places=15)
                            self.assertEqual(times[step],step*f['dt'])
                    self.assertEqual(actual_ids,face_ids);self.assertEqual(list(words),[])
                self.assertEqual(report['general_pressure']['traction_sign'],-1)
            smoke=export(case,tmp/'smoke',hydrostatic=True,stage_pressure=True,general_pressure=True)
            self.assertEqual(smoke['general_pressure']['time_knots'],18)
            self.assertGreater(smoke['general_pressure']['table_end_time'],period)

    def test_explicit_tighter_linear_floor_changes_no_physical_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);case=generate(tmp/'case',axial=2)
            ordinary=export(case,tmp/'ordinary',general_pressure=True)
            tightened=export(case,tmp/'tightened',general_pressure=True,tight_linear_atol=1e-22)
            self.assertEqual(tightened['tight_linear_absolute_tolerance'],1e-22)
            for name in ordinary['files']:
                if name!='svFSI.inp':self.assertEqual(ordinary['files'][name],tightened['files'][name])
            before=(tmp/'ordinary/svFSI.inp').read_text();after=(tmp/'tightened/svFSI.inp').read_text()
            self.assertEqual(before.count('Absolute tolerance: 1e-14'),2)
            self.assertEqual(before.replace('Absolute tolerance: 1e-14','Absolute tolerance: '+format(1e-22,'.17g')),after)
            for invalid in (0,-1e-20,1e-14,1e-8,float('nan')):
                with self.assertRaisesRegex(ValueError,'tight linear absolute tolerance'):
                    export(case,tmp/'invalid',tight_linear_atol=invalid)


if __name__=='__main__':
    unittest.main()
