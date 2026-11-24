"""Circular FSI inlet, curved conforming wall, MPI and restart acceptance."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from verify_fsi_inlet import Runner, error
from generate_tube import generate


def verify_wall_support(run, base):
    free = copy.deepcopy(base)
    free['fsi']['steps'] = 6
    free['time'] = dict(scheme='generalized_alpha', rho_infinity=0.5)
    baseline, _, _ = run.solve('support-free', free, 2)
    zero = copy.deepcopy(free)
    zero['fsi']['domains']['wall_supports'] = [dict(tag=14, stiffness=0, damping=0)]
    same, zero_rows, _ = run.solve('support-zero', zero, 2)
    assert error(baseline, same) < 1e-14
    assert all(row['step_support_work'] == 0 for row in zero_rows)
    free_checkpoint = run.work/'support-free-checkpoint'
    run.solve('support-free-part', free, 2, ['-checkpoint', free_checkpoint, '-stop_after', 3])
    zero_resumed, _, _ = run.solve('support-zero-resume', zero, 2, ['-restart', free_checkpoint])
    assert error(baseline, zero_resumed) < 2e-9

    results = {}
    for scheme in ('be', 'bdf2', 'generalized_alpha'):
        cfg = copy.deepcopy(free)
        cfg['time'] = dict(scheme=scheme)
        cfg['fsi']['domains']['wall_supports'] = [dict(tag=14, stiffness=200, damping=15)]
        one, rows, _ = run.solve('support-'+scheme+'-one', cfg)
        two, parallel_rows, _ = run.solve('support-'+scheme+'-two', cfg, 2)
        assert error(one, two) < 2e-9
        peak = max(r['endpoint_support_spring_energy'] for r in rows)
        assert peak > 1e-12 and max(r['stage_support_dissipation'] for r in rows) > 1e-9
        previous = 0.
        for row, pair in zip(rows, parallel_rows):
            assert min(row['stage_support_spring_energy'], row['stage_support_dissipation']) >= 0
            energy = row['endpoint_support_spring_energy']
            assert abs(row['step_support_work'] + energy - previous
                       + row['accepted_dt']*row['stage_support_dissipation']) < 1e-12*peak
            for key in ('stage_support_spring_energy','stage_support_power','stage_support_dissipation',
                        'endpoint_support_spring_energy','step_support_work'):
                assert math.isclose(row[key],pair[key],rel_tol=1e-7,abs_tol=1e-14)
            previous = energy
        results[scheme] = dict(peak_energy=peak, mpi_error=error(one, two))
    assert error(baseline, two) > 1e-8
    checkpoint = run.work/'support-checkpoint'
    run.solve('support-part', cfg, 2, ['-checkpoint', checkpoint, '-stop_after', 3])
    resumed, tail, _ = run.solve('support-resume', cfg, 2, ['-restart', checkpoint])
    assert error(resumed, two) < 2e-9 and len(tail) == 3
    for row, full in zip(tail, parallel_rows[3:]):
        assert math.isclose(row['step_support_work'], full['step_support_work'], rel_tol=1e-7, abs_tol=1e-14)
    four, _, log = run.solve('support-four', cfg, 4, ['-snes_test_jacobian'])
    ratios = [float(v) for v in re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)', log)]
    assert ratios and max(ratios) < 1e-6 and error(four, two) < 2e-9
    cfg['fsi']['domains']['wall_supports'][0]['damping'] = 16
    run.solve('support-restart-change', cfg, 2, ['-restart', checkpoint], fail='Checkpoint mesh/partition/physics mismatch')
    cfg['fsi']['domains']['wall_supports'] = [dict(tag=14, damping=15)]
    _, damped, _ = run.solve('support-pure-damper', cfg, 2)
    assert all(row['endpoint_support_spring_energy']==0 and
               math.isclose(row['stage_support_power'], -row['stage_support_dissipation'], rel_tol=2e-13)
               for row in damped)
    for label, supports, message in (
        ('tag', [dict(tag=2, stiffness=5)], 'solid exterior tag'),
        ('interface', [dict(tag=13, stiffness=5)], 'Invalid FSI wall support'),
        ('negative', [dict(tag=14, damping=-1)], 'finite and nonnegative'),
        ('nonfinite', [dict(tag=14, stiffness='.inf')], 'finite and nonnegative'),
        ('duplicate', [dict(tag=14, damping=1),dict(tag=14, stiffness=1)], 'Duplicate FSI wall support')):
        cfg['fsi']['domains']['wall_supports'] = supports
        run.solve('invalid-wall-support-'+label, cfg, 2, fail=message)
    return results


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    a=p.parse_args();work=Path(a.work).resolve()
    base=json.loads(generate(work).read_text());geometry=json.loads((work/'geometry.json').read_text())
    base['fsi']['pressure_face_history']=True
    run=Runner(a.executable,a.mpiexec,work,interface_area=geometry['interface_area'])
    report={'wall_support':verify_wall_support(run,base)}
    for scheme in ('be','bdf2','generalized_alpha'):
        cfg=copy.deepcopy(base);cfg['time']=dict(scheme=scheme)
        one,rows,_=run.solve(scheme+'-one',cfg)
        two,_,_=run.solve(scheme+'-two',cfg,2)
        assert error(one,two)<2e-9
        maximum_radial=0
        for row in rows:
            t=row['time'];x=min(1,t/.01)
            target=x**3*(10-15*x+6*x*x)*(.01+.005*math.sin(2*math.pi*t/.04))
            assert abs(row['endpoint_inlet_flow']-target)<1e-12
            assert abs(row['stage_mass_residual'])<1e-9
            assert abs(row['stage_mass_residual']+row['stage_divergence'])<1e-12
            tree=ET.parse(work/f'{scheme}-one_step{int(row["step"])}.vtu')
            xyz=list(map(float,tree.find('.//Points/DataArray').text.split()))
            arrays={n.attrib['Name']:list(map(float,n.text.split())) for n in tree.findall('.//PointData/DataArray')}
            solid=ET.parse(work/f'{scheme}-one_step{int(row["step"])}_solid.vtu')
            sv=list(map(float,solid.find('.//PointData/DataArray[@Name="velocity"]').text.split()))
            sd=list(map(float,solid.find('.//PointData/DataArray[@Name="displacement"]').text.split()))
            used=set(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
            for i in used:
                displacement=arrays['mesh_displacement'][3*i:3*i+3]
                ref=[xyz[3*i+c]-displacement[c] for c in range(3)]
                if abs(math.hypot(ref[1],ref[2])-1)<1e-12:
                    assert max(abs(arrays['velocity'][3*i+c]-sv[3*i+c]) for c in range(3))<1e-12
                    assert max(abs(displacement[c]-sd[3*i+c]) for c in range(3))<1e-12
                    maximum_radial=max(maximum_radial,abs(displacement[1]*ref[1]+displacement[2]*ref[2]))
                if abs(ref[0])<1e-12:
                    assert max(abs(v) for v in displacement)<1e-12
                    assert max(abs(v) for v in arrays['velocity'][3*i+1:3*i+3])<1e-12
        assert maximum_radial>1e-8,maximum_radial
        checkpoint=work/(scheme+'-checkpoint')
        run.solve(scheme+'-part',cfg,2,['-checkpoint',checkpoint,'-stop_after',7])
        resumed,tail,_=run.solve(scheme+'-resume',cfg,2,['-restart',checkpoint])
        assert len(tail)==13 and error(two,resumed)<2e-9
        report[scheme]=dict(mpi_error=error(one,two),restart_error=error(two,resumed),
            maximum_radial_displacement=maximum_radial,maximum_mass_residual=max(abs(r['stage_mass_residual']) for r in rows))
    profile=work/'alpha-four-events.csv'
    four,four_rows,_=run.solve('alpha-four',cfg,4,['-log_view',f':{profile}:ascii_csv'])
    wanted={'FSIFluidRes','FSIFluidAleJac','FSISolidRes','FSISolidJac','FSIInsert','FSIForceReplay'}
    with profile.open() as stream:
        observed=[r for r in csv.DictReader(stream) if r['Stage Name']=='Main Stage' and r['Event Name'] in wanted]
    assert {(r['Event Name'],int(r['Rank'])) for r in observed}=={(e,i) for e in wanted for i in range(4)}
    for name in wanted:
        entries=[r for r in observed if r['Event Name']==name]
        assert len(entries)==4 and sum(int(r['Count']) for r in entries)>0
        assert all(math.isfinite(float(r['Time'])) and float(r['Time'])>=0 for r in entries)
        if name=='FSIForceReplay':
            assert all(int(r['Count'])==len(four_rows) for r in entries)
    assert error(one,four)<2e-9
    report['four_rank_error']=error(one,four)
    with (work/'alpha-four_pressure_faces.csv').open() as stream:
        faces=list(csv.DictReader(stream))
    assert len(faces)==len(four_rows)
    for face,row in zip(faces,four_rows):
        assert int(face['tag'])==cfg['fsi']['domains']['pressure_tags'][0]
        for sample in ('stage','endpoint'):
            assert abs(float(face[sample+'_outward_flow'])-row[sample+'_outlet_flow'])<1e-12
    _,_,log=run.solve('jacobian',cfg,2,['-stop_after',3,'-snes_test_jacobian'])
    ratios=list(map(float,re.findall(r'\|\|J - Jfd\|\|_F/\|\|J\|\|_F\s*=\s*([\deE.+-]+)',log)))
    assert ratios and max(ratios)<1e-6,ratios
    report['jacobian_relative_error']=max(ratios)
    changed=copy.deepcopy(cfg);changed['fsi']['inlet']['flow_rate']['mean']=.02
    run.solve('changed-waveform',changed,2,['-restart',checkpoint],fail='Checkpoint mesh/partition/physics mismatch')
    for label,change,message in (
        ('radius',dict(radius=0),'Invalid FSI flow_rate radius'),
        ('oversize',dict(radius=1.1),'conflicts with homogeneous/interface'),
        ('outside',dict(radius=.9),'outside circle'),
        ('plane',dict(center=[.1,0,0]),'outside circle plane'),
        ('mixed',dict(lower=[0,-1,-1]),'excludes rectangle bounds'),
        ('profile',dict(profile='unknown'),'Invalid FSI flow_rate profile')):
        bad=copy.deepcopy(base);bad['fsi']['inlet']['flow_rate'].update(change)
        run.solve('invalid-'+label,bad,2,fail=message)
    (work/'metrics.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
