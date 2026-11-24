"""Independent harmonic and accepted-history oracles. Python standard library only."""
import base64
import cmath
import json
import math
from pathlib import Path
import sys
import struct
import tempfile
import unittest
from itertools import product
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import compare_svfsi_womersley as sv
from compare_womersley_runs import bdf2_stabilization, phasor_refinement
import study_rigid_tube as tube
import study_womersley as study
from audit_womersley_fields import axial_sections, axial_velocity, quadrature, verified_endpoint_flux


# 60-digit radial integration of r*(1-J0(z*r)/J0(z)) for alpha=2, R=1.
# This evaluates the velocity profile directly, independently of the J1 flow formula.
Q = complex(.00270880299509330365184, -.00177675152987314366278)


class WomersleyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        (self.directory/'mesh').mkdir()
        self.config = study.case_config(16, 3, 'bdf2')
        (self.directory/'case.json').write_text(json.dumps(self.config))
        geometry = dict(sectors=12, radial=2, axial=2, radius=1., length=2.)
        (self.directory/'mesh/geometry.json').write_text(json.dumps(geometry))

    def history(self, q=Q):
        lines = []
        for step in range(1, 49):
            t = step*self.config['fluid']['dt']
            flow = (q*cmath.exp(1j*study.OMEGA*t)).imag
            for tag, area, flux in ((1,3.,-flow), (2,3.,flow), (3,48*math.sin(math.pi/12),0.)):
                lines.append(f'fluid_boundary_step={step} time={t} tag={tag} area={area} '
                             f'outward_flow={flux} mean_pressure=0')
        return lines+['status=success']

    def analyze(self, lines):
        (self.directory/'solve.log').write_text('\n'.join(lines)+'\n')
        return study.analyze(self.directory)

    def test_reference_and_harmonic_convention(self):
        self.assertLess(abs(study.reference_flow()-Q), 1e-17)
        phases = [2*math.pi*i/16 for i in range(1,17)]
        samples = [3+2*math.sin(t)-.3*math.cos(t)+.5*math.cos(2*t) for t in phases]
        self.assertLess(abs(study.harmonic(samples, phases)-(2-.3j)), 1e-14)
        result = self.analyze(self.history())
        self.assertTrue(result['passed'])
        self.assertLess(result['waveform_relative_rms_error'], 1e-14)

    def test_radial_profile_and_disk_integral(self):
        self.assertEqual(axial_velocity(1.),0j)
        self.assertLess(abs(axial_velocity(.25)-(.001273620685606640-.000873595677611650j)),1e-17)
        n=256
        integral=0j
        for i in range(n+1):
            r=i/n
            weight=1 if i in (0,n) else (4 if i%2 else 2)
            integral+=weight*r*axial_velocity(r*r)
        self.assertLess(abs(2*math.pi*integral/(3*n)-Q),2e-12)

    def test_positive_quadrature_moments(self):
        for order in (3,4):
            rule=quadrature(order)
            self.assertTrue(all(w>0 for _,w in rule))
            degree=2*order-3
            for powers in product(range(degree+1),repeat=4):
                if sum(powers)>degree:
                    continue
                exact=6*math.prod(math.factorial(p) for p in powers)/math.factorial(sum(powers)+3)
                actual=sum(w*math.prod(x**p for x,p in zip(bary,powers)) for bary,w in rule)
                self.assertAlmostEqual(actual,exact,places=14)

    def test_detects_amplitude_phase_and_transient(self):
        for q, metric in ((1.05*Q,'amplitude_relative_error'),
                          (Q*cmath.exp(-.1j),'phase_error_degrees')):
            result = self.analyze(self.history(q))
            self.assertFalse(result['passed'])
            self.assertGreater(result[metric],study.LIMITS[metric])
        lines = self.history()
        lines[48:96] = self.history(1.05*Q)[48:96]
        result = self.analyze(lines)
        self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['amplitude_relative_error'], 0., places=14)
        self.assertGreater(result['cycle_max_change_relative'], .04)

    def test_rejects_incomplete_or_inconsistent_samples(self):
        lines = self.history()
        for bad in (lines[:-1], lines[3:], lines[1:], [*lines[:1], *lines],
                    [lines[0].replace('time=', 'time=2'), *lines[1:]],
                    [lines[0].replace('area=3.0','area=1'), *lines[1:]],
                    [lines[0].replace('mean_pressure=0','mean_pressure=nan'), *lines[1:]]):
            with self.subTest(row=bad[0]), self.assertRaises(ValueError):
                self.analyze(bad)

    def test_replay_rejects_changed_load(self):
        for b in self.config['fluid']['boundaries']:
            if 'pressure_time' in b:
                b['pressure_time']['amplitude'] *= 2
        (self.directory/'case.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'declared Womersley'):
            self.analyze(self.history())

    def test_external_mesh_preserves_cells_coordinates_and_oriented_faces(self):
        mesh = self.directory/'generated'
        tube.generate(mesh, sectors=8, radial=2, axial=2, radius=1., length=2.)
        nodes, tets, faces = tube.read_mesh(mesh/'fluid.msh')
        sv.export_mesh(mesh/'fluid.msh',self.directory,'fluid',sv.FACE_NAMES)

        def arrays(path):
            root = ET.parse(path)
            encoded = root.find('AppendedData').text.strip()[1:]
            arrays = root.findall('.//DataArray')
            bounds = [int(a.attrib['offset']) for a in arrays]+[len(encoded)]
            result = {}
            for field,first,last in zip(arrays,bounds,bounds[1:]):
                block = base64.b64decode(encoded[first:last],validate=True)
                self.assertEqual(struct.unpack('<I',block[:4])[0],len(block)-4)
                dtype = {'Float64':'d','Int32':'i','UInt8':'B'}[field.attrib['type']]
                name = field.attrib['Name']
                self.assertEqual(field.get('NumberOfComponents','1'),'3' if name=='Points' else '1')
                result[name] = [v for v, in struct.iter_unpack('<'+dtype,block[4:])]
            return result

        volume = arrays(self.directory/'fluid.vtu')
        node_ids = sorted(nodes)
        self.assertEqual(volume['Points'],[x for n in node_ids for x in nodes[n]])
        self.assertEqual(volume['GlobalNodeID'],list(range(1,len(nodes)+1)))
        self.assertEqual(volume['GlobalElementID'],list(range(1,len(tets)+1)))
        self.assertEqual(volume['types'],[10]*len(tets))
        self.assertEqual(volume['offsets'],list(range(4,4*len(tets)+1,4)))
        self.assertEqual([node_ids[i] for i in volume['connectivity']],[n for t in tets for n in t])
        recovered = []
        for tag,name in sv.FACE_NAMES.items():
            surface = arrays(self.directory/(name+'.vtp'))
            ids = [node_ids[i-1] for i in surface['GlobalNodeID']]
            self.assertEqual(surface['Points'],[x for n in ids for x in nodes[n]])
            owners = surface['GlobalElementID']
            self.assertEqual(surface['offsets'],list(range(3,3*len(owners)+1,3)))
            for i,owner in enumerate(owners):
                face = [ids[j] for j in surface['connectivity'][3*i:3*i+3]]
                tet = tets[owner-1]
                self.assertTrue(set(face).issubset(tet))
                a,b,c = (nodes[n] for n in face)
                opposite, = set(tet)-set(face)
                normal = tube.cross(tube.sub(b,a),tube.sub(c,a))
                self.assertLess(sum(x*y for x,y in zip(normal,tube.sub(nodes[opposite],a))),0.)
                recovered.append((tag,tuple(sorted(face))))
        self.assertCountEqual(recovered,[(tag,tuple(sorted(f))) for tag,f in faces])

    def test_external_iteration_acceptance(self):
        first = ' NS 1-1 0.3 [ 0 1.0 1.0 1e-10] [ 24 -30 82]'
        second = ' NS 1-2 0.4 [-120 2e-9 3e-9 1.0] ! 0 -20 0]'
        self.assertEqual(sv.check_convergence(first+'\n'+second,1),(2e-9,1))
        growth = ' NS 1-2 0.3 ! 24 1.752E1 4.317E3 8.0E-11! [ 78 -232 58]'
        recovered = second.replace('1-2','1-3')
        self.assertEqual(sv.check_convergence('\n'.join((first,growth,recovered)),1),(2e-9,1))
        for history,steps in [(first,1),(second,1),(first+'\n'+second,2),
                              ('\n'.join((first,growth)),1),
                              ('\n'.join((first,growth.replace('8.0E-11!','8.0E-11]'),recovered)),1),
                              ('\n'.join((first,growth.replace('[ 78','! 78'),recovered)),1),
                              (first+'\n'+second+'\n'+second,1),
                              (first+'\n'+second.replace('! 0','! 7'),1),
                              (first+'\n'+second.replace('2e-9','NaN'),1),
                              (first+'\n'+second+'\nSingular matrix detected',1)]:
            with self.subTest(history=history,steps=steps), self.assertRaises(ValueError):
                sv.check_convergence(history,steps)

    def test_axial_sections_integrate_oriented_p1_fields(self):
        mesh = self.directory/'section-mesh'
        tube.generate(mesh,sectors=8,radial=2,axial=3,radius=1.,length=2.)
        nodes,cells,faces = tube.read_mesh(mesh/'fluid.msh')
        state = {n:(2+x+3*y,0.,0.,.02*(1-x/2)+z) for n,(x,y,z) in nodes.items()}
        flow,areas,pressure = tube.surface_integrals(nodes,faces,state)
        end = {tag:study.BoundarySample(2.,a,flow[tag],pressure[tag]/a) for tag,a in areas.items()}
        self.assertEqual(verified_endpoint_flux(nodes,faces,state,end,2.),flow)
        end[2] = end[2]._replace(flow=end[2].flow+.001)
        with self.assertRaisesRegex(ValueError,'boundary history'):
            verified_endpoint_flux(nodes,faces,state,end,2.)
        geometry = json.loads((mesh/'geometry.json').read_text())
        rows = axial_sections(nodes,cells,state,geometry,.02)
        self.assertEqual(len(rows),4)
        area = 4*math.sin(math.pi/4)
        for row in rows:
            self.assertAlmostEqual(row['axial_flow'],area*(2+row['x']),places=12)
            self.assertAlmostEqual(row['mean_pressure'],row['reference_pressure'],places=13)
        with self.assertRaisesRegex(ValueError,'axial'):
            axial_sections(nodes,cells[:-1],state,geometry,.02)

    def test_external_integral_table(self):
        table = self.directory/'flux.txt'
        areas = dict(inlet=3.,outlet=3.,wall=12.)
        rows = ['wall outlet inlet','12 3 3','0 .001 -.001']
        table.write_text('\n'.join(rows))
        self.assertEqual(sv.read_table(table,areas,1),[dict(wall=0.,outlet=.001,inlet=-.001)])
        for bad in [rows[:-1],['wall inlet inlet',*rows[1:]],
                    [rows[0],'12 3.1 3',rows[2]],[*rows[:2],'0 inf 0']]:
            table.write_text('\n'.join(bad))
            with self.subTest(rows=bad), self.assertRaises(ValueError):
                sv.read_table(table,areas,1)

    def test_bdf2_endpoint_stabilization(self):
        nodes = {0:(0,0,0),1:(1,0,0),2:(0,1,0),3:(0,0,1)}
        tet = (0,1,2,3)
        # The accepted mean velocity is (0,2,0). Opposite x components cancel.
        field = {i:((-1)**i,2,0,0) for i in nodes}
        measured = bdf2_stabilization(nodes,[tet],field,.5,1,2)
        expected = 1/math.sqrt(6**2+4**2+8**2)
        for key in ('minimum','maximum','volume_weighted_mean'):
            self.assertAlmostEqual(measured[key],expected)
        self.assertAlmostEqual(measured['max_advective_fraction_of_default_inverse_tau_squared'],16/116)
        self.assertEqual(bdf2_stabilization(nodes,[tet],field,.5,1,2,.003)['maximum'],.003)

    def test_temporal_phasor_and_stabilization_controls(self):
        rows = []
        for n in (16,32,64,128):
            q = Q + (.02-.01j)/n**2
            rows.append(dict(flow_amplitude=abs(q),flow_phase_degrees=math.degrees(cmath.phase(q)),
                             scheme='bdf2',cycles=4,samples_per_cycle=n,stabilization_tau=.003,
                             cycle_max_change_relative=1e-9))
        result = phasor_refinement(rows)
        for order in result['observed_orders']:
            self.assertAlmostEqual(order,2.,places=11)
        for change in (dict(stabilization_tau=None),dict(cycles=3),dict(samples_per_cycle=48)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                phasor_refinement([rows[0],{**rows[1],**change},*rows[2:]])
        for tau in (0.,-1.,math.inf,math.nan):
            with self.subTest(tau=tau), self.assertRaises(ValueError):
                study.case_config(16,4,'bdf2',stabilization_tau=tau)


if __name__ == '__main__':
    unittest.main()
