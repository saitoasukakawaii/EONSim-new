"""Small deterministic checks of the FSI-SCALABLE-05 audit without PETSc or VTK."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from resource_accounting import formal_resources, resource_hours
from scale_c import read_bindings, reference_area_budget

from tube_protocol import (BLOCKS, HERE, audit_corrections, audit_row, budget, compare_face_history,
                           full_field_differences, output_manifest, select, solver_options)


def correction(policy, step=1, newton=1, eta=None, rhs=1., norm=0.):
    eta = policy['rtol'] if eta is None else eta
    row = dict(protocol_hash=policy['hash'],step=step,newton=newton,attempt=1,pc_attempt=1,solve=newton,
               base_rtol=policy['rtol'], requested_rtol=eta, requested_atol=policy['atol'],
               forcing=int(policy['mode']=='inexact'), ksp_reason=2,ksp_iterations=1,
               nonzero_guess=0,roundoff_slack=0,linear_seconds=.01,rhs_norm=rhs,norm=norm,
               limit=max(policy['atol'],eta*rhs))
    if row['forcing']:
        row.update({'eta_'+k:policy['document']['forcing'][k] for k in ('initial','max','gamma','alpha')})
    return row


def synthetic_log(policy, counts, start_step=0):
    def line(marker, data):
        return marker + ' '.join(f'{k}={v}' for k,v in data.items())
    lines = []
    for step,count in enumerate(counts,start_step+1):
        for i in range(1,count+1):
            row=correction(policy,step,i,eta=.1 if i==1 else .5,norm=.01)
            row.update(wide_norm=.01,backward_error=.001)
            lines.append(line('linear_residual ',row))
            identity={k:row[k] for k in ('protocol_hash','step','newton','attempt','pc_attempt','solve')}
            for name in sorted(BLOCKS):
                lines.append(line('linear_field_residual ',dict(**identity,name=name,rms=0,constraint_max=0,
                                      residual_scale=1,constraint_scale=1,equation_rows=10,constraint_rows=0)))
        for name in sorted(BLOCKS):
            lines.append(line('field_residual ',dict(name=name,rms=0,constraint_max=0,limit=1e-12,
                              initial_rms=0,constraint_limit=1e-12,residual_scale=1,constraint_scale=1,accepted=1)))
        lines.append(line('solver_report ',dict(ranks=1,step=step,attempt=1,protocol_hash=policy['hash'],
                          dofs=40, ksp='fgmres',pc='asm', ksp_reason=2,snes_reason=3,snes_stol=0,
                          linesearch='bt',final_lambda=1,matrix_free=0,pc_rebuild_retries=0,inexact_linear_solves=count,
                          snes_atol=1e-12,snes_rtol=1e-10,snes_max_it=1000,
                          linear_started=count,linear_completed=count,linear_iterations=count)))
        lines.append(line('',dict(fsi_step=step,snes_iterations=count,residual=1e-13)))
    command=['example','-case','case.json','-pc_type','asm',*solver_options(policy)]
    options=[]
    for token in command[1:]:
        if token.startswith('-'):
            options.append(token)
        else:
            options[-1]+=' '+token
    lines += ['status=success','#PETSc Option Table entries:']
    lines += [entry+' # (source: command line)' for entry in options]
    lines.append('#End of PETSc Option Table entries')
    return '\n'.join(lines),command


class ProtocolChecks(unittest.TestCase):
    def test_cross_partition_reference_geometry(self):
        nodes={1:(0,0,0),2:(1,0,0),3:(1,1,0),4:(0,1,0)}
        mesh=nodes,[],[(3,(1,2,3)),(3,(1,3,4)),(2,(1,2,4))]
        bound=reference_area_budget(mesh,3,(32,64),1e-6)
        self.assertEqual((bound['triangles'],bound['area']),(2,1.))
        self.assertGreater(bound['absolute_limit'],sys.float_info.epsilon)
        self.assertLess(bound['absolute_limit'],1e-12)
        with self.assertRaises(ValueError):
            reference_area_budget(mesh,13,(32,64),1e-6)

    def test_physical_core_bindings(self):
        log='[node:123] MCW rank 0 bound to socket 0[core 0[hwt 0]]: [B]\n'
        other='[node:123] MCW rank 1 bound to socket 1[core 0[hwt 0]]: [B]\n'
        self.assertEqual(read_bindings(log+other,2)['1'],[1,0,0])
        for invalid in (log,log+log,log+other.replace('socket 1','socket 0'),
                        log+other.replace(']]:',']], socket 1[core 1[hwt 0]]:')):
            with self.assertRaises(ValueError):
                read_bindings(invalid,2)

    def test_exclusive_allocation_and_diagnostic_separation(self):
        hours = resource_hours(4,'128(x1)',900.)
        self.assertEqual((hours['active_rank_hours'],hours['allocated_core_hours']),(1.,32.))
        with self.assertRaises(ValueError):
            resource_hours(4,'2',900.)
        opts={'-linear_componentwise_error':'false','-linear_report':'','-solver_report':''}
        row=dict(formal=True,job='466',ranks=2,allocation='128',T_job=1.,affinity=[0,1],
                 command=['mpiexec','-n','2','--map-by','core','--bind-to','core'],
                 linear={'effective_options':opts})
        self.assertEqual(formal_resources(row)[:3],('466',128,2))
        opts['-fieldsplit_solid_ksp_monitor']=''
        with self.assertRaises(ValueError):
            formal_resources(row)

    def test_zero_rhs_nonzero_guess_and_max(self):
        p=select()
        row=correction(p,rhs=0,norm=p['atol'])
        row['nonzero_guess']=1
        self.assertEqual(audit_row(row,p),1)
        # Equal relative/absolute terms: sum rule would incorrectly pass this residual.
        with self.assertRaises(ValueError):
            audit_row(correction(p,rhs=p['atol']/p['rtol'],norm=1.5*p['atol']),p)

    def test_fixed_and_actual_forcing(self):
        fixed=select()
        adaptive=select(profile='inexact-1e-8')
        with self.assertRaises(ValueError):
            audit_row(correction(fixed,eta=.1,norm=.05),fixed)
        row=correction(adaptive,eta=.1,norm=.05)
        self.assertEqual(audit_row(row,adaptive),.5)
        for key,value in [('requested_rtol',.2),('base_rtol',.01),('eta_gamma',.1),('protocol_hash','bad'),
                          ('norm',float('nan')),('ksp_reason',-3),('ksp_reason',4),('limit',1e10)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit_row(dict(row,**{key:value}),adaptive)

    def test_lu_explicit_threshold_and_physical_budget(self):
        lu=select(profile='lu')
        opts=solver_options(lu)
        self.assertEqual(float(opts[opts.index('-linear_lu_refinement_rtol')+1]),1e-8)
        self.assertNotIn('-ksp_rtol',opts)
        self.assertEqual(budget(lu,'pressure'),.16)
        self.assertEqual(budget(lu,'flow'),2.5e-10)

    def test_steps_reset_and_missing_records(self):
        p=select(profile='inexact-1e-8')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'case.json').write_text(json.dumps({'solver':{}}))
            log=folder/'solve.log'
            good,command=synthetic_log(p,[2,1])
            def write_log(text):
                log.write_text(text)
                meta=dict(command=command,exit_code=0,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
                (folder/'run.json').write_text(json.dumps(meta))
            write_log(good)
            self.assertEqual(audit_corrections(folder,2,1,p)['corrections'],3)
            already_solved,_=synthetic_log(p,[0,0])
            write_log(already_solved)
            empty=audit_corrections(folder,2,1,p)
            self.assertEqual(empty['corrections'],0)
            self.assertIsNone(empty['max_ratio'])
            tail,_=synthetic_log(p,[2,1],4)
            write_log(tail)
            self.assertEqual(audit_corrections(folder,6,1,p,4)['corrections'],3)
            with self.assertRaises(ValueError):
                audit_corrections(folder,6,1,p)
            for bad in (good.replace('linear_started=2','linear_started=1'),
                        good.replace('ksp_reason=2','ksp_reason=-2',1),
                        good.replace('accepted=1','accepted=0',1),
                        good.replace('requested_rtol=0.1','requested_rtol=0.5'),
                        good.replace('snes_atol=1e-12','snes_atol=1e-3'),
                        good.replace('(source: command line)','(source: file)',1),
                        good.replace('pc=asm','pc=lu'),
                        good.replace('step=2','step=1'),
                        good.replace('linear_field_residual','omitted_field',1)):
                write_log(bad)
                with self.assertRaises(ValueError):
                    audit_corrections(folder,2,1,p)

    def test_face_history_budget_and_missing_step(self):
        p=select()
        with tempfile.TemporaryDirectory() as tmp:
            ref,can=(Path(tmp)/n for n in ('ref','can'))
            ref.mkdir()
            can.mkdir()
            (can/'case.json').write_text(json.dumps({'fsi':{'pressure_face_history':True,'domains':{'pressure_tags':[2]}}}))
            h=dict(step=1,time=1/32,accepted_dt=1/32,evaluation_time=.02)
            row=dict(**h,tag=2)
            for phase in ('endpoint','stage'):
                for q in ('area','mean_pressure','mean_normal_traction','outward_flow','prescribed_pressure','pressure_power'):
                    row[phase+'_'+q]=0.
            def write(d, rows):
                with (d/'tube_pressure_faces.csv').open('w',newline='') as stream:
                    w=csv.DictWriter(stream,fieldnames=row)
                    w.writeheader()
                    w.writerows(rows)
            write(ref,[row])
            write(can,[dict(row,stage_mean_pressure=.15)])
            self.assertEqual(compare_face_history(can,ref,([h],[h]),p)['stage_mean_pressure'],.15)
            for bad in ([],[dict(row,stage_mean_pressure=.161)],[dict(row,stage_area=float('nan'))]):
                write(can,bad)
                with self.assertRaises(ValueError):
                    compare_face_history(can,ref,([h],[h]),p)

    def test_complete_output_manifest(self):
        fake=SimpleNamespace(digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules,{'paired_tube':fake}):
            d=Path(tmp)
            (d/'case.json').write_text(json.dumps({'fsi':dict(steps=4,dt=1/32,output_interval=4)}))
            (d/'tube.csv').write_text('history')
            for suffix in ('','_solid'):
                step='tube_step4'+suffix
                (d/('tube'+suffix+'.pvd')).write_text(
                    f'<VTKFile><Collection><DataSet timestep="0.125" file="{step}.vtu"/></Collection></VTKFile>')
                for stem in (step,'tube'+suffix):
                    (d/(stem+'.vtu')).write_bytes(b'saved')
            self.assertEqual(len(output_manifest(d,4,1)['phase_hashes']),2)
            (d/'tube_solid.vtu').write_bytes(b'stale')
            with self.assertRaises(ValueError):
                output_manifest(d,4,1)

    def test_supplemental_derivative_and_field_coverage(self):
        spec=json.loads((HERE/'output-fields-v2.1.json').read_text())
        zero={(suffix,1,name):[0.]*(1 if name=='pressure' else 3)
              for suffix,region in (('','fluid'),('_solid','solid')) for name in spec['regions'][region]}
        values=dict(zero)
        fake=SimpleNamespace(physical_fields=lambda p,n: values if p.parent.name=='candidate' else zero)
        args=(Path('candidate'),Path('reference'),4,(1,1),select())
        with patch.dict(sys.modules,{'benchmark_fsi_assembly':fake}):
            phases,_=full_field_differences(*args)
            self.assertIn('solid/algorithmic_acceleration',phases[0])
            k=('_solid',1,'algorithmic_acceleration')
            values[k]=[1.,0.,0.]
            with self.assertRaises(ValueError):
                full_field_differences(*args)
            del values[k]
            with self.assertRaises(ValueError):
                full_field_differences(*args)


if __name__=='__main__':
    unittest.main()
