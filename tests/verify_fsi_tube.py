"""Circular FSI inlet, curved conforming wall, MPI and restart acceptance."""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from verify_fsi_inlet import Runner, error
from generate_tube import generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    a=p.parse_args();work=Path(a.work).resolve()
    base=json.loads(generate(work).read_text());geometry=json.loads((work/'geometry.json').read_text())
    run=Runner(a.executable,a.mpiexec,work,interface_area=geometry['interface_area'])
    report={}
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
    four,_,_=run.solve('alpha-four',cfg,4)
    assert error(one,four)<2e-9
    report['four_rank_error']=error(one,four)
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
