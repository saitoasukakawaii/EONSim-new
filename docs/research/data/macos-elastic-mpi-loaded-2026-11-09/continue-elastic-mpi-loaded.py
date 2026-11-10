from pathlib import Path
import os,sys,json,hashlib,shutil,subprocess,time,signal,re
ROOT=Path(__file__).resolve().parents[2];w=ROOT/'build/recompute-20261109/elastic-mpi-loaded'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
definition=json.loads((w/'definition.json').read_text());cfg=json.loads((w/'case.json').read_text());opts=definition['solver_options']
assert definition['inputs']=={name:sha(w/name) for name in definition['inputs']}
assert not (w/'loaded').exists() and not (w/'completion.json').exists()
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
receipts=json.loads((w/'progress.json').read_text())
t=(w/'early/early.log').read_text();assert t.rstrip().endswith('status=success')
rows=lambda prefix:[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in t.splitlines() if s.startswith(prefix)]
reports=rows('solver_report ');steps=rows('fsi_step=')
assert len(reports)==len(steps)==19200
assert [int(s['fsi_step']) for s in steps]==list(range(1,19201))
zero=[]
for r,s in zip(reports,steps):
 assert int(r['snes_reason'])>0 and float(s['endpoint_min_fluid_j'])>0 and float(s['endpoint_min_solid_j'])>0
 if int(r['ksp_reason'])==0:
  assert all(int(r[k])==0 for k in ('linear_started','linear_completed','linear_iterations'))
  assert int(s['snes_iterations'])==0 and float(s['residual'])<cfg['solver']['absolute_tolerance']
  zero.append(int(s['fsi_step']))
 else:assert int(r['ksp_reason'])>0
assert zero==[1]
receipts['early']=dict(accepted_range=[1,19201],log_sha256=sha(w/'early/early.log'),status='solver success, original controller postflight assertion failed',zero_linear_solve_steps=zero,postflight_source_sha256=sha(Path(__file__)),scope='Positive SNES convergence; step1 needs no linear solve and actual residual5.5403e-14 satisfies unchanged absolute tolerance1e-13. Original failure preserved; no transient recomputation.')
dump(w/'early/postflight-receipt.json',receipts['early']);dump(w/'progress.json',receipts)
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
 for label,first,last,cadence in [('loaded',19201,19232,1),('replay16',19217,19232,1)]:
  d=w/label;d.mkdir();local=json.loads(json.dumps(cfg));local['mesh']='../fluid.msh';local['fsi']['domains']['solid_mesh']='../solid.msh';local['fsi'].update(output_interval=cadence,checkpoint_interval=cadence);dump(d/'case.json',local)
  cmd=['/opt/homebrew/bin/mpiexec','-n','2',str(w/'eonsim'),'-case','case.json','-partition',str(w/'parts'),'-checkpoint',str(d/'checkpoint'),'-stop_after',str(last),*opts]
  if label!='early':cmd+=['-restart',str(checkpoint(w/('early' if label=='loaded' else 'loaded')/'checkpoint',first-1))]
  run(label,cmd,d,(first,last+1))
 dump(w/'completion.json',dict(receipts=receipts,scope='Numerics complete; global fields and full native history comparisons pending'))
 print((w/'completion.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'continuation-failure.json',dict(error=repr(e),receipts=receipts));raise
