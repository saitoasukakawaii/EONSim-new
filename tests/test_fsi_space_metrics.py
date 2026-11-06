from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fsi_space_metrics import interpolation,distance


class Space(unittest.TestCase):
    def test_affine_reproduction_and_offset(self):
        def value(x):return dict(reference_position=x,pressure=[x[0]+2*x[1]+3*x[2]])
        nodes={i:value(x) for i,x in enumerate([(0,0,0),(1,0,0),(0,1,0),(0,0,1)])}
        coarse=(nodes,{i:1/24 for i in nodes},[(0,1,2,3)])
        fine=({10:value((.1,.2,.3)),11:value((.3,.1,.2))},{10:.1,11:.2})
        stencil=interpolation(coarse,fine,1)
        self.assertLess(distance(coarse,fine,stencil,['pressure'])['pressure'],1e-14)
        fine[0][10]['pressure'][0]+=2;fine[0][11]['pressure'][0]+=2
        self.assertAlmostEqual(distance(coarse,fine,stencil,['pressure'])['pressure'],2)

    def test_no_extrapolation(self):
        nodes={i:dict(reference_position=x) for i,x in enumerate([(0,0,0),(1,0,0),(0,1,0),(0,0,1)])}
        with self.assertRaisesRegex(ValueError,'outside'):
            interpolation((nodes,{},[(0,1,2,3)]),({4:dict(reference_position=(.5,.5,.5))},{4:1}),1)

    def test_spatial_case_policy_rejects_mixed_tau(self):
        import json
        import tempfile
        from analyze_fsi_space import validate_cases
        with tempfile.TemporaryDirectory() as root:
            workdirs=[]
            for n in (2,4,8):
                work=Path(root)/str(n);work.mkdir();workdirs.append(work)
                (work/'study-definition.json').write_text(json.dumps(dict(n=n)))
                cfg=dict(mesh='fluid.msh',output='flow.vtu',fsi=dict(dt=.001,steps=100,output_interval=5,domains=dict(solid_mesh='solid.msh')))
                (work/'periodic-result.json').write_text(json.dumps(dict(config=cfg)))
            validate_cases(workdirs,'automatic')
            data=json.loads((workdirs[0]/'periodic-result.json').read_text())
            data['config']['fsi']['stabilization_tau']=.05
            (workdirs[0]/'periodic-result.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Mixed stabilization'):validate_cases(workdirs,'automatic')
            with self.assertRaisesRegex(ValueError,'Expected fixed'):validate_cases(workdirs,'fixed')
            for work in workdirs:
                data=json.loads((work/'periodic-result.json').read_text())
                data['config']['fsi']['stabilization_tau']=.05
                (work/'periodic-result.json').write_text(json.dumps(data))
            validate_cases(workdirs,'fixed')
            data['config']['fsi']['stabilization_tau']=.025
            (workdirs[-1]/'periodic-result.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'differ beyond'):validate_cases(workdirs,'fixed')

    def test_error_budget_requires_all_fields_and_strict_ten_percent(self):
        from analyze_fsi_space import error_budget
        spatial={'fluid_velocity':2.,'solid_displacement':.01}
        low={'fluid_velocity':.1,'solid_displacement':.0005}
        self.assertTrue(error_budget(spatial,low,low,low)['passed'])
        at_limit={'fluid_velocity':.2,'solid_displacement':.001}
        self.assertFalse(error_budget(spatial,at_limit,low,low)['passed'])
        with self.assertRaisesRegex(ValueError,'Incomplete'):error_budget(spatial,{},low,low)
        with self.assertRaisesRegex(ValueError,'Invalid contamination'):error_budget(spatial,dict(low,fluid_velocity=float('nan')),low,low)

    def test_transient_tail_uses_block_decay_and_rejects_nondecay(self):
        from study_fsi_transient_tail import tail_estimate
        result=tail_estimate([{'u':1.},{'u':.5},{'u':.25}])
        self.assertAlmostEqual(result['u']['remaining_at_source'],2.)
        self.assertAlmostEqual(result['u']['contraction'],.5)
        with self.assertRaisesRegex(ValueError,'not resolved'):tail_estimate([{'u':1.},{'u':.9},{'u':.8}])

    def test_error_estimate_survives_relocation_but_not_changed_source(self):
        import hashlib
        import json
        import tempfile
        from analyze_fsi_error_budget import attached_estimate
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'restored';source.mkdir()
            checkpoint=source/'checkpoint'/'generation_1';checkpoint.mkdir(parents=True)
            (checkpoint/'manifest').write_text('physical checkpoint')
            (checkpoint/'state_rank0.h5').write_bytes(b'accepted state and algorithm history')
            for name in ('fluid.msh','solid.msh'):(source/name).write_text(name)
            study=dict(n=2,dt=.001,tau=.05,ranks=1)
            (source/'study-definition.json').write_text(json.dumps(study))
            (source/'periodic-result.json').write_text(json.dumps(dict(checkpoint_generation='generation_1')))
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            definition=dict(source='/former/machine/study',source_checkpoint='generation_1',source_definition=study,
                source_files_sha256={p.name:digest(p) for p in checkpoint.iterdir()},
                mesh_sha256={name:digest(source/name) for name in ('fluid.msh','solid.msh')})
            estimate=root/'tail.json'
            estimate.write_text(json.dumps(dict(definition=definition,estimate={'u':dict(remaining_at_source=.01)})))
            self.assertEqual(attached_estimate(estimate,source,'transient'),{'u':.01})
            for changed in (checkpoint/'state_rank0.h5',checkpoint/'manifest',source/'fluid.msh',source/'solid.msh'):
                original=changed.read_bytes()
                changed.write_bytes(original+b' changed')
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):attached_estimate(estimate,source,'transient')
                changed.write_bytes(original)
            extra=checkpoint/'state_rank1.h5';extra.write_bytes(b'unexpected rank')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):attached_estimate(estimate,source,'transient')
            extra.unlink()
            (source/'study-definition.json').write_text(json.dumps(dict(study,tau=.025)))
            with self.assertRaisesRegex(ValueError,'different periodic state'):attached_estimate(estimate,source,'transient')


if __name__=='__main__':unittest.main()
