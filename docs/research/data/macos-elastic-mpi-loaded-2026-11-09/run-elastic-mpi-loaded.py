"""Fresh two-rank transient and fully loaded restart proof, explicit local MUMPS workaround."""
from pathlib import Path
import os,sys,json,hashlib,shutil,subprocess,time,signal,re
ROOT=Path(__file__).resolve().parents[2]
w=ROOT/'build/recompute-20261109/elastic-mpi-loaded';w.mkdir()
src=ROOT/'build/recompute-20261109/elastic-s24-l0-n800'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
for name in ('eonsim','fluid.msh','solid.msh','case.json'):shutil.copy2(src/name,w/name)
cfg=json.loads((w/'case.json').read_text());assert cfg['fsi']['steps']==25600 and cfg['fsi']['checkpoint_interval']==800
serial=ROOT/'build/recompute-20261109/elastic-loaded-screen'
assert json.loads((serial/'definition.json').read_text())['start_step']==19200
assert sha(w/'eonsim')==sha(serial/'eonsim')
for name in ('fluid.msh','solid.msh'):assert sha(w/name)==sha(serial/name)
opts=['-pc_factor_mat_solver_type','mumps','-mat_mumps_icntl_20','0','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32','-solver_report']
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),controller_sha256=sha(Path(__file__)),inputs={name:sha(w/name) for name in ('case.json','fluid.msh','solid.msh','eonsim')},ranks=2,threads_per_rank=1,solver_options=opts,start_step=19200,loaded_steps=32,replay_steps=16,rss_limit_bytes=3*1024**3,disk_floor_bytes=20*1024**3,scope='Fresh 24-cycle transient, then 32 fully loaded steps and same-partition 16-step replay; numerical proof only, not 32-cycle physical qualification. Explicit local MUMPS ICNTL(20)=0 required.')
dump(w/'definition.json',definition)
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
receipts={}
def run(label,cmd,cwd,expected=None):
 dump(cwd/(label+'-command.json'),cmd);start=time.monotonic();peak=0
 with (cwd/(label+'.log')).open('w') as log:
  proc=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  dump(w/'live.json',dict(pid=proc.pid,label=label,start_unix=time.time()))
  try:
   while proc.poll() is None:
    rows=subprocess.check_output(['ps','-axo','pid=,ppid=,pgid=,rss='],text=True)
    table=[list(map(int,s.split())) for s in rows.splitlines() if s.strip()]
    own={proc.pid};changed=True
    while changed:
     old=set(own);own.update(pid for pid,ppid,pgid,rss in table if ppid in own or pgid==proc.pid);changed=old!=own
    rss=sum(rss*1024 for pid,ppid,pgid,rss in table if pid in own);peak=max(peak,rss)
    if peak>definition['rss_limit_bytes'] or shutil.disk_usage(w).free<definition['disk_floor_bytes'] or time.monotonic()-start>86400:raise RuntimeError('Resource/time bound exceeded')
    time.sleep(2)
  except BaseException:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   raise
 text=(cwd/(label+'.log')).read_text();assert proc.returncode==0,(label,proc.returncode)
 if expected is not None:
  assert 'status=success' in text
  actual=list(map(int,re.findall(r'^fsi_step=(\d+) time=',text,re.M)));assert actual==list(range(*expected)),(label,len(actual))
  reports=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('solver_report ')]
  assert len(reports)==len(actual) and all(int(r['snes_reason'])>0 and int(r['ksp_reason'])>0 for r in reports)
 receipt=dict(exit_code=proc.returncode,seconds=time.monotonic()-start,peak_process_tree_rss_bytes=peak,log_sha256=sha(cwd/(label+'.log')),accepted_range=expected)
 receipts[label]=receipt;dump(cwd/(label+'-receipt.json'),receipt);dump(w/'progress.json',receipts)
def checkpoint(folder,step):
 found=[p.parent for p in folder.glob('generation_*/manifest') if int(p.read_text().split()[2])==step];assert len(found)==1
 assert (found[0]/'manifest').read_text().split()[:2]==['EONSim_checkpoint_v4','2']
 return found[0]
try:
 run('prepare',[str(w/'eonsim'),'-case','case.json','-prepare',str(w/'parts'),'-parts','2'],w)
 definition['partition_sha256']={str(p.relative_to(w/'parts')):sha(p) for p in (w/'parts').rglob('*') if p.is_file()};dump(w/'definition.json',definition)
 for label,first,last,cadence in [('early',1,19200,800),('loaded',19201,19232,1),('replay16',19217,19232,1)]:
  d=w/label;d.mkdir();local=json.loads(json.dumps(cfg));local['mesh']='../fluid.msh';local['fsi']['domains']['solid_mesh']='../solid.msh';local['fsi'].update(output_interval=cadence,checkpoint_interval=cadence);dump(d/'case.json',local)
  cmd=['/opt/homebrew/bin/mpiexec','-n','2',str(w/'eonsim'),'-case','case.json','-partition',str(w/'parts'),'-checkpoint',str(d/'checkpoint'),'-stop_after',str(last),*opts]
  if label!='early':cmd+=['-restart',str(checkpoint(w/('early' if label=='loaded' else 'loaded')/'checkpoint',first-1))]
  run(label,cmd,d,(first,last+1))
 dump(w/'completion.json',dict(receipts=receipts,scope='Numerics complete; global fields and full native history comparisons pending'))
 print((w/'completion.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'failure.json',dict(error=repr(e),receipts=receipts));raise
