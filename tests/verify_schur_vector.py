"""Velocity vector metadata/chord on an actual transient tube, versus direct."""
import argparse,json,math,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    tube.generate(a.work/'mesh',sectors=12,radial=2,axial=4,radius=1,length=2)
    cfg=tube.case_config();cfg['mesh']=str((a.work/'mesh/fluid.msh').resolve())
    cfg['fluid'].update(mode='transient',dt=.02,steps=3)
    cfg['fluid']['boundaries'][1].update(value=0,pressure_time=dict(amplitude=.02,period=2*math.pi/4))
    cfg['time']=dict(scheme='bdf2')
    case=a.work/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n')
    def run(label,cmd,success=True):
        (a.work/(label+'-command.json')).write_text(json.dumps(list(map(str,cmd)),indent=2)+'\n')
        r=subprocess.run(list(map(str,cmd)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
        (a.work/(label+'.log')).write_text(r.stdout)
        if success:
            assert r.returncode==0 and 'status=success' in r.stdout,r.stdout
        else:
            assert r.returncode!=0 and 'Schur velocity block3 requires -schur_pc' in r.stdout,r.stdout
        return r.stdout
    direct=a.work/'direct';direct.mkdir(exist_ok=True)
    run('direct',[a.executable,'-case',case,'-output',direct/'solution.vtu'])
    reference=tube.fields(direct,1);results=[]
    for ranks in (1,2,4):
        directory=a.work/f'vector{ranks}';directory.mkdir(exist_ok=True);parts=directory/'parts'
        run(f'prepare{ranks}',[a.executable,'-case',case,'-prepare',parts,'-parts',ranks])
        mpi=[a.mpiexec,'-n',ranks] if ranks>1 else []
        text=run(f'vector{ranks}',mpi+[a.executable,'-case',case,'-partition',parts,
            '-output',directory/'solution.vtu','-schur_pc','-schur_velocity_block3','-snes_lag_jacobian','-2','-solver_report'])
        actual=tube.fields(directory,ranks);assert reference.keys()==actual.keys()
        difference=max(abs(v-w) for n in reference for v,w in zip(reference[n],actual[n]))
        assert math.isfinite(difference) and difference<2e-9,difference
        rows=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('solver_report ')]
        assert len(rows)==3 and all(int(r['snes_reason'])>0 and int(r['ksp_reason'])>0 for r in rows)
        flows=re.findall(r'^net_outward_flow=([^\s]+)',text,re.M)
        assert flows and all(math.isfinite(float(v)) and abs(float(v))<1e-10 for v in flows)
        results.append(dict(ranks=ranks,maximum_field_difference=difference))
    run('requires-schur',[a.mpiexec,'-n','2',a.executable,'-case',case,'-partition',a.work/'vector2/parts',
        '-output',a.work/'rejected.vtu','-schur_velocity_block3'],success=False)
    (a.work/'summary.json').write_text(json.dumps(dict(passed=True,results=results,scope='Three transient steps; not long-cycle accuracy or performance qualification'),indent=2)+'\n')
    print(json.dumps(results))

if __name__=='__main__':main()
