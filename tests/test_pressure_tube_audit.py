"""Independent affine, integral and harmonic oracles for elastic-tube metrics."""
import copy
import json
import math
from pathlib import Path
import sys
import struct
import tempfile
import unittest
import weakref
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_pressure_tube import generate
from audit_pressure_tube import Domain,eonsim_frame,fluid_metrics,harmonic,analyze


class TubeAudit(unittest.TestCase):
    def test_length_pair_preserves_spacing_material_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            short=generate(root/'short',sectors=12,radial=1,axial=2)
            long=generate(root/'long',sectors=12,radial=1,axial=4,length=24)
            self.assertEqual(json.loads(short.read_text()),json.loads(long.read_text()))
            a=json.loads((short.parent/'geometry.json').read_text())
            b=json.loads((long.parent/'geometry.json').read_text())
            self.assertEqual(a['length']/a['axial'],b['length']/b['axial'])
            self.assertEqual(a['infinite_plane_strain_inner_wall_compliance'],b['infinite_plane_strain_inner_wall_compliance'])
            for name in ('fluid.msh','solid.msh'):
                left=Domain(short.parent/name);right=Domain(long.parent/name)
                self.assertAlmostEqual(right.volume,2*left.volume,places=10)
                self.assertEqual(sorted({x[0] for x in left.nodes.values()}),[0.,6.,12.])
                self.assertEqual(sorted({x[0] for x in right.nodes.values()}),[0.,6.,12.,18.,24.])

    def test_invalid_length_leaves_no_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'case'
            for value in (0,-1,float('nan'),float('inf')):
                with self.assertRaisesRegex(ValueError,'Length'):
                    generate(directory,length=value)
                self.assertFalse(directory.exists())

    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        case=generate(Path(cls.directory.name)/'case',sectors=12,radial=1,axial=2)
        cls.domain=Domain(case.parent/'fluid.msh')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def frame(self,dilation=0.,rate=0.):
        return {n:dict(reference_position=x,mesh_displacement=[dilation*v for v in x],
                       velocity=[rate*(1+dilation)*v for v in x],pressure=[3+2*x[0]])
                for n,x in self.domain.nodes.items()}

    def test_affine_geometry_and_divergence_theorem(self):
        dilation=.02;rate=.3
        value=fluid_metrics(self.domain,self.frame(dilation,rate))
        volume=36*(1+dilation)**3
        self.assertAlmostEqual(value['volume'],volume,places=11)
        self.assertAlmostEqual(value['minimum_fluid_jacobian'],(1+dilation)**3,places=12)
        self.assertAlmostEqual(value['divergence_rms'],3*rate,places=12)
        self.assertAlmostEqual(value['total_outward_flux'],3*rate*volume,places=11)
        self.assertLess(value['divergence_theorem_defect'],1e-11)
        self.assertAlmostEqual(value['mid_pressure'],15,places=12)
        self.assertAlmostEqual(value['pressure_left'],3,places=12)
        self.assertAlmostEqual(value['pressure_right'],27,places=12)
        self.assertAlmostEqual(value['mid_ring_projected_area'],3*(1+dilation)**2,places=12)
        # Exact mean radius along a regular polygon's straight edge.
        theta=math.pi/12
        mean_radius=.5+math.cos(theta)**2/(2*math.sin(theta))*math.asinh(math.tan(theta))
        self.assertAlmostEqual(value['mid_radial_displacement'],dilation*mean_radius,places=9)

    def test_consistent_mass_linear_field(self):
        left=self.frame();right=self.frame()
        for n,x in self.domain.nodes.items():right[n]['velocity']=[x[0],0.,0.]
        self.assertAlmostEqual(self.domain.rms_difference(left,right,'velocity'),12/math.sqrt(3),places=12)
        for value in right.values():value['pressure']=[value['pressure'][0]+4]
        self.assertAlmostEqual(self.domain.rms_difference(left,right,'pressure'),4,places=12)

    def test_dense_cycle_frames_are_released_without_changing_period_norms(self):
        # Track live reader results, not allocator-specific RSS. The old full
        # phase cache retained two nodal dictionaries for every sampled phase.
        class Frame(dict):
            pass
        with tempfile.TemporaryDirectory() as tmp:
            n=32
            case=generate(Path(tmp)/'case',sectors=12,radial=1,axial=2,
                          steps_per_cycle=n,cycles=4)
            cfg=json.loads(case.read_text());dt=cfg['fsi']['dt']
            refs=[];maximum_live=0
            def frame(path,domain,solid=False):
                nonlocal maximum_live
                step=int(Path(path).stem)
                pressure=1+.01*math.sin(2*math.pi*step/n)+.001*step/n
                values={node:dict(reference_position=x,velocity=[0.]*3,
                                  **({'displacement':[0.]*3} if solid else
                                     {'mesh_displacement':[0.]*3,'pressure':[pressure]}))
                        for node,x in domain.nodes.items()}
                result=Frame(values);refs.append(weakref.ref(result))
                maximum_live=max(maximum_live,sum(r() is not None for r in refs))
                return result
            entries=[(i*dt,Path(f'{i}.vtu')) for i in range(1,4*n+1)]
            with patch('audit_pressure_tube.series',return_value=entries), \
                    patch('audit_pressure_tube.eonsim_frame',side_effect=frame):
                result=analyze(case,Path(tmp))
            self.assertLessEqual(maximum_live,10)
            self.assertEqual(result['sampled_steps'],4*n)
            for cycle in (2,3,4):
                metrics=result['cycle_differences'][cycle]['fluid_pressure']
                self.assertAlmostEqual(metrics['relative_max'],.1,places=11)
                self.assertAlmostEqual(metrics['relative_rms'],.1,places=11)
            self.assertFalse(result['periodic'])
            self.assertAlmostEqual(result['harmonics']['mid_pressure']['mean'],
                                   1+.001*(3+(n+1)/(2*n)),places=12)

    def test_periodic_window_must_follow_the_startup_ramp(self):
        with tempfile.TemporaryDirectory() as tmp:
            case=generate(Path(tmp)/'case',sectors=12,radial=1,axial=2,cycles=3)
            cfg=json.loads(case.read_text());cfg['fsi']['pressure_time']['ramp_time']=.01
            case.write_text(json.dumps(cfg))
            for reference in (False,True):
                with self.assertRaisesRegex(ValueError,'three complete cycles after the startup ramp'):
                    analyze(case,Path(tmp)/'unread-output',reference)

    def test_reference_segment_cannot_stand_in_for_full_study_convergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            case=generate(root/'case',sectors=12,radial=1,axial=2,cycles=3)
            cfg=json.loads(case.read_text());work=root/'reference';work.mkdir()
            (work/'source-case.json').write_text(json.dumps(cfg))
            (work/'export.json').write_text(json.dumps(dict(
                mode='linear elastic pressure tube',load_evaluation='alpha_f stage',files={})))
            # A valid late segment must not be promoted to evidence for warmup
            # steps which its log never contains. This guard precedes field I/O.
            with patch('audit_svfsi_convergence.analyze',return_value=dict(
                    passed=True,first_step=401,last_step=cfg['fsi']['steps'])):
                with self.assertRaisesRegex(ValueError,'requires a complete chain'):
                    analyze(case,work,True,reference_log=root/'resumed.log')
            with self.assertRaisesRegex(ValueError,'Choose a reference log'):
                analyze(case,work,True,reference_log=root/'resumed.log',reference_chain=root/'chain.json')

    def test_float32_reference_serialization_is_exact_and_unambiguous(self):
        frame=self.frame(.02,.3)
        rounded=copy.deepcopy(frame)
        for value in rounded.values():
            value['reference_position']=struct.unpack('=3f',struct.pack('=3f',*value['reference_position']))
        self.assertGreater(max(abs(x-y) for n in frame for x,y in zip(
            frame[n]['reference_position'],rounded[n]['reference_position'])),1e-9)
        actual=self.domain.canonical(rounded,self.domain.cells,'Float32')
        self.assertEqual(actual,frame)
        with self.assertRaisesRegex(ValueError,'reference coordinates differ'):
            self.domain.canonical(rounded,self.domain.cells)
        # A one-ULP edit is not a valid serialization of the original mesh.
        changed=copy.deepcopy(rounded)
        n=next(n for n,x in self.domain.nodes.items() if x[1]==1.)
        x=list(changed[n]['reference_position']);x[1]+=2**-23
        changed[n]['reference_position']=x
        with self.assertRaisesRegex(ValueError,'reference coordinates differ'):
            self.domain.canonical(changed,self.domain.cells,'Float32')
        with self.assertRaisesRegex(ValueError,'tetrahedra'):
            self.domain.canonical(rounded,self.domain.cells[:-1],'Float32')
        ambiguous=copy.copy(self.domain);ambiguous.nodes=dict(self.domain.nodes)
        x=list(ambiguous.nodes[n]);x[1]+=2**-25
        ambiguous.nodes[max(ambiguous.nodes)+1]=tuple(x)
        with self.assertRaisesRegex(ValueError,'Ambiguous Float32'):
            ambiguous.canonical(rounded,self.domain.cells,'Float32')

    def test_reject_invalid_fields_and_topology(self):
        frame=self.frame();self.domain.canonical(frame,self.domain.cells)
        bad=copy.deepcopy(frame);bad[next(iter(bad))]['velocity'][0]=float('nan')
        with self.assertRaisesRegex(ValueError,'Nonfinite'):self.domain.canonical(bad,self.domain.cells)
        bad=copy.deepcopy(frame);bad[next(iter(bad))]['velocity']=[0.]
        with self.assertRaisesRegex(ValueError,'width'):self.domain.canonical(bad,self.domain.cells)
        with self.assertRaisesRegex(ValueError,'tetrahedra'):self.domain.canonical(frame,self.domain.cells[:-1])
        with self.assertRaisesRegex(ValueError,'Nonpositive'):fluid_metrics(self.domain,self.frame(-1.1))

    def test_phase_and_higher_harmonic(self):
        period=2.3;n=40
        rows=[]
        for i in range(1,n+1):
            t=(5+i/n)*period;phase=2*math.pi*t/period
            rows.append(dict(time=t,value=3+2*math.sin(phase)+.5*math.cos(phase)+.25*math.sin(2*phase)))
        result=harmonic(rows,'value',period)
        self.assertAlmostEqual(result['mean'],3,places=12)
        self.assertAlmostEqual(result['sine'],2,places=12)
        self.assertAlmostEqual(result['cosine'],.5,places=12)
        self.assertAlmostEqual(result['phase_degrees'],math.degrees(math.atan2(.5,2)),places=11)
        self.assertAlmostEqual(result['higher_harmonic_rms'],.25/math.sqrt(2),places=12)
        with self.assertRaisesRegex(ValueError,'equally'):harmonic(rows[:-1],'value',period)

    def test_eonsim_current_coordinates_and_unused_points(self):
        frame=self.frame(.02,.3);ids=list(reversed(self.domain.nodes));indices={n:i for i,n in enumerate(ids)}
        root=ET.Element('VTKFile');piece=ET.SubElement(ET.SubElement(root,'UnstructuredGrid'),'Piece')
        def array(parent,name,values,width=1):
            value=ET.SubElement(parent,'DataArray',Name=name,NumberOfComponents=str(width))
            value.text=' '.join(map(str,values))
        coordinates=[x+d for n in ids for x,d in zip(self.domain.nodes[n],frame[n]['mesh_displacement'])]+[99.,99.,99.]
        array(ET.SubElement(piece,'Points'),'Points',coordinates,3)
        array(ET.SubElement(piece,'Cells'),'connectivity',[indices[n] for c in self.domain.cells for n in c])
        data=ET.SubElement(piece,'PointData')
        array(data,'mesh_node_id',[9007199254740993+i for i in range(len(ids)+1)])
        for name,width in (('velocity',3),('pressure',1),('mesh_displacement',3)):
            # EONSim writes its common point table for both physical domains;
            # a point not used by this domain has no physical field meaning.
            array(data,name,[v for n in ids for v in frame[n][name]]+[float('nan')]*width,width)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'physical.vtu';ET.ElementTree(root).write(path)
            actual=eonsim_frame(path,self.domain)
        self.assertEqual(actual.keys(),frame.keys())
        self.assertLess(self.domain.rms_difference(actual,frame,'velocity'),1e-14)
        self.assertLess(self.domain.rms_difference(actual,frame,'mesh_displacement'),1e-14)


if __name__=='__main__':
    unittest.main()
