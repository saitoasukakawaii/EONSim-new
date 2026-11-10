"""Bounded fresh Mac single-rank screen; original PDE and acceptance unchanged."""
from pathlib import Path
import os,sys,json,math,hashlib,shutil,subprocess,time,signal,re
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube
import h5py,numpy as np
from analyze_womersley import Mesh
WORK=ROOT/'build/recompute-20261109/alpha1-s96-l1-screen'
WORK.mkdir()  # no overwrite or duplicate execution

def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
exe=ROOT/'build/macos-release/eonsim';shutil.copy2(exe,WORK/'eonsim')
tube.generate(WORK/'seed',sectors=96,radial=8,axial=8,radius=1,length=2)
nodes,cells,faces=tube.refine(*tube.read_mesh(WORK/'seed/fluid.msh'))
tube.write_mesh(WORK/'fluid.msh',nodes,cells,faces)
mesh=Mesh(WORK/'fluid.msh')
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),binary_sha256=sha(exe),mesh_sha256=sha(WORK/'fluid.msh'),seed=[96,8,8],level=1,alpha=1,steps=32,steps_per_cycle=400,physical_final_steps=2400,ranks=1,threads=1,memory_rss_limit_bytes=6*1024**3,disk_floor_bytes=20*1024**3,timeout_seconds=1800,node_limit=2e-9,mass_relative_limit=1e-8,minimum_cost_reduction=.1,scope='Bounded startup only; no periodic or physical qualification',sources={p:sha(ROOT/p) for p in ['scripts/study_rigid_tube.py','scripts/analyze_womersley.py','cases/fsi/generate_tube.py']})
dump(WORK/'definition.json',definition)
base=tube.case_config();base.update(mesh='../fluid.msh',output='solution.vtu',time=dict(scheme='bdf2'))
base['fluid'].update(mode='transient',dt=2*math.pi/400,steps=2400,checkpoint_interval=1)
base['fluid']['boundaries'][1].update(value=0.,pressure_time=dict(amplitude=.02,period=2*math.pi))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
results={}
def generations(folder):
 result={}
 for p in folder.glob('generation_*/manifest'):
  m=p.read_text().split();assert m[0]=='EONSim_checkpoint_v4' and len(m)==6 and int(m[1])==1
  step=int(m[2]);assert step not in result;result[step]=p.parent
 return result

def run(name,window,restart=None):
 folder=WORK/name;folder.mkdir();dump(folder/'case.json',base)
 command=[str(WORK/'eonsim'),'-case','case.json','-checkpoint','checkpoint','-stop_after','32','-solver_report','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-log_view',':profile.txt']
 if window:command+=['-fluid_lu_pc_reuse_window',str(window)]
 if restart:command+=['-restart',str(restart)]
 dump(folder/'command.json',command);t=time.monotonic();peak=0
 with (folder/'solve.log').open('w') as log:
  process=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   while process.poll() is None:
    if time.monotonic()-t>1800:raise TimeoutError(name)
    rss=subprocess.run(['ps','-o','rss=','-p',str(process.pid)],text=True,capture_output=True)
    if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
    if peak>definition['memory_rss_limit_bytes']:raise MemoryError('RSS limit')
    if shutil.disk_usage(WORK).free<definition['disk_floor_bytes']:raise RuntimeError('Disk floor')
    time.sleep(1)
  except BaseException:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
   raise
 elapsed=time.monotonic()-t;text=(folder/'solve.log').read_text();assert process.returncode==0 and 'status=success' in text
 steps=[int(v) for v in re.findall(r'^fluid_step=(\d+)',text,re.M)]
 assert steps==list(range(17 if restart else 1,33)),steps
 factors=[r.split() for r in (folder/'profile.txt').read_text().splitlines() if r.lstrip().startswith('MatLUFactorNum ')]
 assert len(factors)==1;count=int(factors[0][1]);expected=1 if restart else {0:32,8:5,32:2}[window];assert count==expected,(count,expected)
 result=dict(seconds=elapsed,peak_rss_bytes=peak,factors=count,steps=steps,exit_code=process.returncode)
 results[name]=result;dump(folder/'receipt.json',result);dump(WORK/'progress.json',results)
 return folder
try:
 for label,window in [('direct-first',0),('window8',8),('window32',32),('direct-last',0)]:run(label,window)
 restart=generations(WORK/'window32/checkpoint')[16]
 run('replay16',32,restart)
 maps={k:generations(WORK/k/'checkpoint') for k in results}
 maximum=0.;massmax=0.;pairs=0;datasets=0
 for label in ['window8','window32','direct-last','replay16']:
  for step,path in maps[label].items():
   with h5py.File(maps['direct-first'][step]/'state_rank0.h5') as a,h5py.File(path/'state_rank0.h5') as b:
    assert set(a)==set(b)
    for key in a:
     x,y=a[key][()],b[key][()];assert x.shape==y.shape and np.all(np.isfinite(x)) and np.all(np.isfinite(y))
     if key in ['clock','metadata','time_metadata']:assert np.array_equal(x,y),(label,step,key)
     else:
      delta=np.max(np.abs(x-y),initial=0);maximum=max(maximum,float(delta));assert delta<2e-9,(label,step,key,delta)
      if key in ['fluid','time_previous'] and x.size:
       diff=(x-y).reshape(-1,4)
       for sl,scale in [(slice(0,3),.0025),(slice(3,4),.02)]:
        value=math.sqrt(mesh.squared(diff[:,sl])/mesh.volume)/scale;massmax=max(massmax,value);assert value<1e-8
     datasets+=1
   pairs+=1
 ratios={k:results['window32']['seconds']/results[k]['seconds'] for k in ['direct-first','direct-last','window8']}
 dump(WORK/'report.json',dict(definition=definition,runs=results,pairs=pairs,datasets=datasets,maximum_node_delta=maximum,maximum_relative_mass=massmax,clocks_exact=True,cost_ratios=ratios,eligible=all(v<=.9 for v in ratios.values()),scope='Startup execution validation only; final physics and budgets not evaluated'))
 print((WORK/'report.json').read_text(),flush=True)
except BaseException as e:
 dump(WORK/'failure.json',dict(error=repr(e),completed=results));raise
