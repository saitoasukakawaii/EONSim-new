"""Real Newton nonconvergence -> rollback/cutback; compare to a direct small-step trajectory."""
import argparse,copy,json,math,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_domains import generate
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--recipe',choices=['physics','quantity','hybrid','added_mass']);p.add_argument('--velocity-solver',choices=['split','coupled','twolevel','gamg']);p.add_argument('--velocity-coarse-space',choices=['constants','rigid']);p.add_argument('--structure-approx',choices=['a11','nodal']);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
if a.velocity_solver and not a.recipe: p.error('--velocity-solver requires --recipe')
if a.velocity_coarse_space and a.velocity_solver not in ('twolevel','gamg'): p.error('--velocity-coarse-space requires --velocity-solver twolevel or gamg')
if a.velocity_coarse_space=='rigid' and a.velocity_solver!='twolevel': p.error('rigid coarse space requires --velocity-solver twolevel')
if a.structure_approx and a.recipe!='added_mass': p.error('--structure-approx requires --recipe added_mass')
case=generate(a.work);config=json.loads(case.read_text());config['fsi'].update(material='neo_hookean',pressure=20,dt=.04,steps=1);config['time_control']=dict(max_retries=6,minimum_dt=.0005,reduction=.5);
if a.recipe: config.setdefault('solver',{})['pc_recipe']=a.recipe
case.write_text(json.dumps(config))
def run(args,ok=True):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=100)
 if (r.returncode==0)!=ok:raise RuntimeError(r.stdout)
 return r.stdout
def compare(first,second,ranks):
    for solid in ('','_solid'):
        for rank in range(ranks):
            suffix=solid+(f'_rank{rank}' if ranks>1 else '')+'.vtu'
            x=ET.parse(first.with_name(first.stem+suffix))
            y=ET.parse(second.with_name(second.stem+suffix))
            left,right=x.findall('.//DataArray'),y.findall('.//DataArray')
            assert left and len(left)==len(right), ('Missing or extra VTU arrays',suffix)
            for u,v in zip(left,right):
                signature=lambda item:(item.attrib.get('Name'),item.attrib.get('type'),
                                       item.attrib.get('NumberOfComponents','1'))
                assert signature(u)==signature(v), ('Different VTU field metadata',suffix,signature(u),signature(v))
                first_values,second_values=(u.text or '').split(),(v.text or '').split()
                assert len(first_values)==len(second_values), ('Different VTU field lengths',suffix,signature(u))
                if u.attrib.get('type')=='Float64':
                    first_values,second_values=list(map(float,first_values)),list(map(float,second_values))
                    assert all(math.isfinite(value) for values in (first_values,second_values) for value in values), \
                        ('Nonfinite VTU field',suffix,signature(u))
                    assert max((abs(i-j) for i,j in zip(first_values,second_values)),default=0)<2e-8
def check_structure_option(log):
    if not a.structure_approx: return
    blocks=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in log.splitlines()
            if line.startswith('pc_block ')]
    assert any(row['name']=='dynamics' and row['structure_approx']==a.structure_approx
               for row in blocks), 'requested structural approximation was not configured'
    nodes=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in log.splitlines()
           if line.startswith('solver_node ')]
    structure=[row for row in nodes if row['prefix']=='fieldsplit_dynamics_fieldsplit_structure_']
    expected='preonly' if a.structure_approx=='nodal' else 'fgmres'
    assert structure and all(row['ksp']==expected for row in structure), 'unexpected structural action'
for ranks in (1,2):
 part=a.work/f'parts{ranks}';run([a.executable,'-case',case,'-prepare',part,'-parts',ranks]);launcher=[a.mpiexec,'-n',ranks] if ranks>1 else []
 # With only two Newton iterations, keep linear error below the scaled
 # mesh acceptance floor so this fixture exercises nonlinear cutback.
 prefix=launcher+[a.executable,'-case',case,'-partition',part,'-snes_max_it',2,
                  '-ksp_rtol','1e-11','-ksp_atol','1e-15']
 if a.velocity_solver: prefix+=['-pc_plan_velocity_solver',a.velocity_solver]
 if a.velocity_coarse_space: prefix+=['-pc_plan_velocity_coarse_space',a.velocity_coarse_space]
 if a.structure_approx: prefix+=['-pc_plan_structure_approx',a.structure_approx,'-pc_plan_report','-solver_report']
 full=a.work/f'full{ranks}.vtu';text=run(prefix+['-output',full]);retries=re.findall(r'step_retry=\d+ time=(\S+) next_dt=(\S+)',text)
 check_structure_option(text)
 assert retries and all(float(time)==0 for time,dt in retries)
 dt=float(retries[-1][1]);steps=round(.04/dt);assert abs(steps*dt-.04)<1e-12
 reference=copy.deepcopy(config);reference['fsi'].update(dt=dt,steps=steps);reference['time_control']['max_retries']=0
 if a.recipe: reference['solver'].pop('pc_recipe',None)
 fixed=a.work/'fixed.yaml';fixed.write_text(json.dumps(reference));ref=a.work/f'reference{ranks}.vtu'
 run(launcher+[a.executable,'-case',fixed,'-partition',part,'-snes_max_it',2,'-output',ref]);compare(full,ref,ranks)
 checkpoint=a.work/f'checkpoint{ranks}';run(prefix+['-checkpoint',checkpoint,'-stop_after',3,'-output',a.work/'partial.vtu'])
 resumed=a.work/f'resumed{ranks}.vtu';tail=run(prefix+['-restart',checkpoint,'-output',resumed]);compare(full,resumed,ranks)
 check_structure_option(tail)
 assert float(re.findall(r'fsi_step=\d+ time=(\S+)',tail)[0])>3*dt
 failure=run(prefix+['-snes_max_it',0],False);assert 'retries exhausted' in failure
 invalid=run(prefix+['-pc_type','eonsim_invalid_pc'],False)
 assert 'Unknown type' in invalid and 'step_retry=' not in invalid and 'status=success' not in invalid
 print('retry rollback/restart',ranks,'accepted dt',dt,'steps',steps)
print('time retry verification passed')
