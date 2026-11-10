"""Local loaded coarse FSI cache/restart proof from a frozen fresh checkpoint."""
from pathlib import Path
import sys,os,json,shutil,hashlib,time,subprocess,signal,re
import numpy as np,h5py
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from audit_pressure_tube import Domain,eonsim_frame
from fsi_field_cycles import series
src=ROOT/'build/recompute-20261109/elastic-s24-l0-n800'
w=ROOT/'build/recompute-20261109/elastic-loaded-screen';w.mkdir()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
generation=(src/'checkpoint/current').read_text().split()[1]
shutil.copytree(src/'checkpoint'/generation,w/'source')
m=(w/'source/manifest').read_text().split();assert m[0]=='EONSim_checkpoint_v4' and int(m[1])==1
start=int(m[2]);assert start>=16*800
for name in ['eonsim','fluid.msh','solid.msh']:shutil.copy2(src/name,w/name)
cfg=json.loads((src/'case.json').read_text());cfg['mesh']='../fluid.msh';cfg['fsi']['domains']['solid_mesh']='../solid.msh';cfg['fsi'].update(output_interval=1,checkpoint_interval=1)
assert start+32<cfg['fsi']['steps']
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_generation=generation,start_step=start,source_sha256={p.name:sha(p) for p in (w/'source').iterdir()},binary_sha256=sha(w/'eonsim'),steps=32,ranks=1,threads=1,node_limit=2e-9,mass_relative_limit=1e-8,scope='Fully ramped loaded local window; not periodic or full physical qualification')
dump(w/'definition.json',definition);env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
results={}
def maps(folder):
 out={}
 for p in folder.glob('generation_*/manifest'):
  parts=p.read_text().split();step=int(parts[2]);assert step not in out;out[step]=p.parent
 return out
try:
 for name,window in [('direct-first',0),('window8',8),('window32',32),('direct-last',0),('replay16',32)]:
  d=w/name;d.mkdir();dump(d/'case.json',cfg)
  source=w/'source' if name!='replay16' else maps(w/'window32/checkpoint')[start+16]
  cmd=[str(w/'eonsim'),'-case','case.json','-checkpoint','checkpoint','-restart',str(source),'-stop_after',str(start+32),'-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-solver_report','-log_view',':profile.txt']
  if window:cmd+=['-fsi_lu_pc_reuse_window',str(window)]
  dump(d/'command.json',cmd);t=time.monotonic();peak=0
  with (d/'solve.log').open('w') as log:
   proc=subprocess.Popen(cmd,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:
    while proc.poll() is None:
     rss=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True)
     if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
     if peak>3*1024**3 or shutil.disk_usage(w).free<20*1024**3 or time.monotonic()-t>1800:raise RuntimeError('Resource bound exceeded')
     time.sleep(1)
   except BaseException:
    if proc.poll() is None:
     os.killpg(proc.pid,signal.SIGTERM)
     try:proc.wait(timeout=10)
     except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  assert proc.returncode==0,(name,proc.returncode)
  text=(d/'solve.log').read_text();assert 'status=success' in text
  steps=list(map(int,re.findall(r'^fsi_step=(\d+) time=',text,re.M)));assert steps==list(range(start+(17 if name=='replay16' else 1),start+33))
  count=[int(x.split()[1]) for x in (d/'profile.txt').read_text().splitlines() if x.lstrip().startswith('MatLUFactorNum ')]
  assert count==[1 if name=='replay16' else {0:32,8:4,32:1}[window]],(name,count)
  result=dict(exit_code=0,steps=steps,factors=count[0],seconds=time.monotonic()-t,peak_rss_bytes=peak);results[name]=result;dump(d/'receipt.json',result)
 domains=[Domain(w/'fluid.msh'),Domain(w/'solid.msh')]
 compliance=(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));ds=.01*compliance
 scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
 baseline=maps(w/'direct-first/checkpoint');maximum=0.;massmax=0.;pairs=0;datasets=0;fieldpairs=0
 for name in ('window8','window32','direct-last','replay16'):
  for step,path in maps(w/name/'checkpoint').items():
   with h5py.File(baseline[step]/'state_rank0.h5') as a,h5py.File(path/'state_rank0.h5') as b:
    assert set(a)==set(b)
    for key in a:
     x,y=a[key][()],b[key][()];assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
     if key in ('metadata','clock','time_metadata'):assert np.array_equal(x,y),(name,step,key)
     else:
      delta=float(np.max(np.abs(x-y),initial=0));maximum=max(maximum,delta);assert delta<2e-9,(name,step,key,delta)
     datasets+=1
   pairs+=1
  for i,suffix in enumerate(('', '_solid')):
   left=dict(series(w/'direct-first'/('solution'+suffix+'.pvd')))
   for timevalue,path in series(w/name/('solution'+suffix+'.pvd')):
    assert timevalue in left
    a=eonsim_frame(left[timevalue],domains[i],bool(i));b=eonsim_frame(path,domains[i],bool(i))
    for field,scale in scales[i].items():
     delta=domains[i].rms_difference(a,b,field)/scale;massmax=max(massmax,delta);assert delta<1e-8,(name,timevalue,field,delta)
    fieldpairs+=1
 assert pairs==112 and fieldpairs==224
 assert definition['source_sha256']=={p.name:sha(p) for p in (w/'source').iterdir()}
 ratios={name:results['window32']['seconds']/results[name]['seconds'] for name in ('direct-first','direct-last','window8')}
 dump(w/'report.json',dict(definition=definition,runs=results,checkpoint_pairs=pairs,hdf_datasets=datasets,domain_frame_pairs=fieldpairs,maximum_history_node_delta=maximum,maximum_field_relative_mass=massmax,clock_metadata_exact=True,cost_ratios=ratios,correctness_passed=True,local_cost_reduction_passed=all(v<.9 for v in ratios.values()),scope=definition['scope']))
 print((w/'report.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'failure.json',dict(error=repr(e),completed=results));raise
