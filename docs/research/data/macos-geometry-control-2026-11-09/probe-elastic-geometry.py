from pathlib import Path
import os,sys,subprocess,time,signal,shutil,json,re,hashlib,math
b=Path(__file__).resolve().parent;root=b.parents[1];src=b/'elastic-geometry48-preparation';w=b/'elastic-geometry48-probe';w.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
prep=json.loads((src/'preparation.json').read_text())
for name,digest in prep['prepared_inputs'].items():assert sha(src/name)==digest;shutil.copy2(src/name,w/name)
cfg=json.loads((w/'case.json').read_text());cfg['fsi']['output_interval']=1;cfg['fsi']['checkpoint_interval']=1;dump(w/'case.json',cfg)
exe=root/'build/macos-release/eonsim';cmd=[str(exe),'-case','case.json','-checkpoint',str(w/'checkpoint'),'-stop_after','8','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32']
dump(w/'definition.json',dict(command=cmd,source_preparation_sha256=sha(src/'preparation.json'),binary_sha256=sha(exe),inputs={name:sha(w/name) for name in prep['prepared_inputs']},scope='Eight-step fresh input/solver smoke only; no periodic or geometry-response qualification'))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None);t=time.monotonic();peak=0
with (w/'solve.log').open('w') as log:
 proc=subprocess.Popen(cmd,cwd=w,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  while proc.poll() is None:
   rss=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True)
   if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
   if peak>3*1024**3 or shutil.disk_usage(w).free<20*1024**3 or time.monotonic()-t>120:raise RuntimeError('Probe resource limit')
   time.sleep(.2)
 except BaseException:
  if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)
  raise
text=(w/'solve.log').read_text();assert proc.returncode==0 and text.rstrip().endswith('status=success')
steps=list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)));assert steps==list(range(1,9))
mins={}
for name in ['endpoint_min_fluid_j','endpoint_min_solid_j']:
 values=list(map(float,re.findall(name+r'=(\S+)',text)));assert len(values)==8 and all(math.isfinite(x) and x>0 for x in values);mins[name]=min(values)
r=dict(exit_code=0,steps=steps,seconds=time.monotonic()-t,peak_rss_bytes=peak,minimum_jacobians=mins,log_sha256=sha(w/'solve.log'),scope='Input/solver smoke passed only; geometry-response full32cycle comparison not yet run');dump(w/'receipt.json',r);print(r)
