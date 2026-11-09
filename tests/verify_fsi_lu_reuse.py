"""Explicit FSI LU reuse: actual factors, all output fields, events and restart."""
import argparse,copy,json,math,re,subprocess,sys,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cases/fsi'));sys.path.insert(0,str(ROOT/'scripts'))
from generate_pressure_tube import generate
import study_rigid_tube as tube


def fields(path,solid):
    tree=ET.parse(path)
    pieces=tree.findall('.//Piece[@Source]')
    if pieces:
        result={}
        for piece in pieces:
            for key,value in fields(path.parent/piece.attrib['Source'],solid).items():
                if key in result:assert max(abs(x-y) for x,y in zip(result[key],value))<2e-9
                result[key]=value
        return result
    arrays={a.attrib['Name']:(int(a.attrib.get('NumberOfComponents',1)),list(map(float,a.text.split())))
            for a in tree.findall('.//PointData/DataArray')}
    used=set(map(int,tree.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
    wanted=('velocity','displacement') if solid else ('velocity','pressure','mesh_displacement')
    result={}
    for i in used:
        node=int(arrays['mesh_node_id'][1][i])
        for name in wanted:
            width,data=arrays[name];assert width==(1 if name=='pressure' else 3)
            value=tuple(data[width*i:width*(i+1)]);assert all(map(math.isfinite,value))
            result[(solid,node,name)]=value
    return result


def frames(directory):
    result={}
    for path in directory.glob('solution*.pvd'):
        solid='_solid' in path.stem
        for entry in ET.parse(path).findall('.//DataSet'):
            time=float(entry.attrib['timestep']);assert math.isfinite(time)
            key=(solid,time);assert key not in result
            result[key]=fields(path.parent/entry.attrib['file'],solid)
    assert result
    return result


def compare(a,b):
    assert a.keys()==b.keys();maximum=0.
    for phase,values in a.items():
        assert values.keys()==b[phase].keys()
        for key,u in values.items():
            maximum=max(maximum,max(abs(x-y) for x,y in zip(u,b[phase][key])))
    assert maximum<2e-9,maximum
    return maximum


def rows(text,prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith(prefix)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    a.work=a.work.resolve();a.work.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=a.work))
    (a.work/'current.json').write_text(json.dumps(dict(run_directory=work.name))+'\n')
    cfg=json.loads(generate(work/'mesh',sectors=6,radial=1,axial=2).read_text())
    cfg['mesh']=str(work/'mesh/fluid.msh');cfg['fsi']['domains']['solid_mesh']=str(work/'mesh/solid.msh')
    cfg['fsi'].update(dt=1/64,steps=10,output_interval=1,checkpoint_interval=1)
    cfg['fsi']['pressure_time'].update(period=.5,ramp_time=1/32)
    case=work/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n')
    def run(label,command,failure=None):
        command=list(map(str,command));(work/(label+'-command.json')).write_text(json.dumps(command,indent=2)+'\n')
        with (work/(label+'.log')).open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=sys.platform.startswith('linux'))
            try:code=child.wait(timeout=120)
            except BaseException:
                if sys.platform.startswith('linux'):
                    (work/(label+'-cleanup.json')).write_text(json.dumps(tube._stop_session(child),indent=2)+'\n')
                else:child.kill();child.wait()
                raise
        text=(work/(label+'.log')).read_text()
        if failure:assert code!=0 and failure in text,text[-4000:]
        else:assert code==0 and 'status=success' in text,text[-4000:]
        return text
    def solve(label,base,window=0,extra=()):
        directory=work/label;directory.mkdir(exist_ok=True)
        command=base+['-output',directory/'solution.vtu','-checkpoint',directory/'checkpoint']
        if window:command+=['-fsi_lu_pc_reuse_window',window]
        command+=['-log_view',':'+str(directory/'profile.txt')]+list(extra)
        return run(label+('-resume' if extra and '-restart' in extra else ''),command)
    def count(directory,expected):
        events=[s.split() for s in (work/directory/'profile.txt').read_text().splitlines() if s.lstrip().startswith('MatLUFactorNum ')]
        assert len(events)==1 and int(events[0][1])==expected and float(events[0][2])==1,events
    def accepted(text,steps,uses=None):
        reports=rows(text,'solver_report ');step_rows=rows(text,'fsi_step=')
        assert len(reports)==len(step_rows)==steps
        assert all(int(x['snes_reason'])>0 and int(x['ksp_reason'])>0 for x in reports)
        assert all(float(x['endpoint_min_fluid_j'])>0 and float(x['endpoint_min_solid_j'])>0 for x in step_rows)
        if uses is not None:
            assert all(x['ksp']=='fgmres' and x['pc']=='lu' for x in reports)
            cached=rows(text,'lu_preconditioner ')
            assert [int(x['uses']) for x in cached]==uses,cached
            assert [int(x['reused']) for x in cached]==[int(n>1) for n in uses]
        return step_rows
    result=[];serial=None
    for ranks in (1,2,4):
        part=work/f'parts{ranks}';run(f'prepare{ranks}',[a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        mpi=[a.mpiexec,'-n',ranks] if ranks>1 else []
        base=mpi+[a.executable,'-case',case,'-partition',part,'-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-solver_report']
        direct=f'r{ranks}-direct';cached=f'r{ranks}-cached';restart=f'r{ranks}-restart'
        direct_rows=accepted(solve(direct,base),10);count(direct,10)
        cached_rows=accepted(solve(cached,base,32),10,[1]+list(range(1,10)));count(cached,2)
        d,c=frames(work/direct),frames(work/cached);assert len(d)==20
        if serial is None:serial=d
        row=dict(ranks=ranks,cached_vs_direct=compare(d,c),direct_vs_serial=compare(serial,d),actual_factors=2)
        accepted(solve(restart,base,32,['-stop_after',4]),4,[1,1,2,3])
        resumed=accepted(solve(restart,base,32,['-restart',work/restart/'checkpoint']),6,list(range(1,7)));count(restart,1)
        row['restart_vs_cached']=compare(c,frames(work/restart))
        for left,right in zip(direct_rows,cached_rows):
            for name in ('time','accepted_dt','evaluation_time'):assert left[name]==right[name]
        for left,right in zip(cached_rows[4:],resumed):
            for name in ('time','accepted_dt','evaluation_time'):assert left[name]==right[name]
        if ranks==2:
            extras={}
            for label,control,steps,uses,factors in (
                ('window4',None,10,[1,1,2,3,4,1,2,3,4,1],4),
                ('event',dict(events=[5/64]),10,[1,1,2,3,4,1,1,2,3,4],4),
                ('variable',dict(step_sizes=[1/64,1/64,1/32,1/32]+[5/128]*4),8,[1,1,1,2,1,2,3,4],4)):
                variant=copy.deepcopy(cfg)
                if control:variant['time_control']=control
                if label=='variable':variant['fsi'].update(dt=1/32,steps=8)
                path=work/(label+'-case.json');path.write_text(json.dumps(variant,indent=2)+'\n')
                commands=base.copy();commands[commands.index('-case')+1]=path
                left=f'r2-{label}-direct';right=f'r2-{label}-cached'
                accepted(solve(left,commands),steps)
                accepted(solve(right,commands,4 if label=='window4' else 32),steps,uses);count(right,factors)
                extras[label]=dict(cached_vs_direct=compare(frames(work/left),frames(work/right)),actual_factors=factors)
            row['extra_checks']=extras
        result.append(row)
    run('invalid-window',[a.executable,'-case',case,'-fsi_lu_pc_reuse_window',-1],failure='Invalid -fsi_lu_pc_reuse_window')
    run('unsupported-physics',[a.executable,'-case',ROOT/'cases/poisson/case.yaml','-fsi_lu_pc_reuse_window',32],failure='requires linear elastic periodic-pressure')
    changed=copy.deepcopy(cfg);changed['time']['scheme']='bdf2';changed['time'].pop('rho_infinity')
    unsupported=work/'unsupported-case.json';unsupported.write_text(json.dumps(changed)+'\n')
    run('unsupported-scheme',[a.executable,'-case',unsupported,'-fsi_lu_pc_reuse_window',32],failure='requires linear elastic periodic-pressure')
    run('unsupported-pc',[a.executable,'-case',case,'-fsi_lu_pc_reuse_window',32,'-pc_type','jacobi'],failure='LU preconditioner reuse requires')
    run('missing-mumps',[a.executable,'-case',case,'-fsi_lu_pc_reuse_window',32],failure='LU preconditioner reuse requires')
    (work/'summary.json').write_text(json.dumps(dict(passed=True,results=result,
        scope='All stored output fields and actual LU counts at1/2/4ranks, coefficient transitions, restart and unchanged logged v4 clocks. Complete HDF histories retained for a separate audit; no cost or long-run qualification.'),indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
