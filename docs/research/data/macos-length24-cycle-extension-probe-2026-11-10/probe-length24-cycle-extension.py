"""Eight accepted steps past the actual32-cycle checkpoint; original study preserved."""
from pathlib import Path
import json,hashlib,os,subprocess,time,signal,shutil,re
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';out=w/'extension-probe';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
d=json.loads((w/'definition.json').read_text());assert sha(w/'eonsim')==d['binary_sha256']
for name,digest in d['inputs'].items():assert sha(w/name)==digest
assert json.loads((w/'dense/receipt.json').read_text())['exit_code']==0
marker,generation=(w/'checkpoint/current').read_text().split();seed=w/'checkpoint'/generation;assert marker=='EONSim_checkpoint_v4' and (seed/'manifest').read_text().split()[:3]==[marker,'1','25600']
seed_hashes={p.name:sha(p) for p in seed.iterdir()};assert set(seed_hashes)=={'manifest','state_rank0.h5'}
original=json.loads((w/'dense/case.json').read_text());assert original['fsi']['steps']==25600
cfg=json.loads(json.dumps(original));cfg['fsi']['steps']=28800
assert shutil.disk_usage(w).free>20.5*2**30
out.mkdir();dump(out/'case.json',cfg)
command=json.loads((w/'dense/command.json').read_text());command[command.index('-checkpoint')+1]=str(out/'checkpoint');command[command.index('-stop_after')+1]='25608';command[command.index('-restart')+1]=str(seed)
dump(out/'command.json',command);dump(out/'definition.json',dict(binary_sha256=sha(w/'eonsim'),original_case_sha256=sha(w/'dense/case.json'),probe_case_sha256=sha(out/'case.json'),seed=str(seed),seed_sha256=seed_hashes,controller_sha256=sha(Path(__file__)),scope='Only configured horizon25600→28800 changed; stop after25608. Same physical model, timestep, mesh, tolerances and actual v4 history; no full extension or periodicity claim.'))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None);start=time.time();peak=0;proc=None
try:
 with (out/'solve.log').open('w') as log:
  proc=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while proc.poll() is None:
   rss=subprocess.run(['ps','-p',str(proc.pid),'-o','rss='],capture_output=True,text=True)
   if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
   assert peak<3*2**30 and time.time()-start<600 and shutil.disk_usage(w).free>20*2**30
   time.sleep(1)
 text=(out/'solve.log').read_text();assert proc.returncode==0 and 'status=success' in text
 steps=list(map(int,re.findall(r'^fsi_step=(\d+) ',text,re.M)));assert steps==list(range(25601,25609))
 m,g=(out/'checkpoint/current').read_text().split();assert m==marker and (out/'checkpoint'/g/'manifest').read_text().split()[:3]==[marker,'1','25608']
 assert all(sha(seed/name)==digest for name,digest in seed_hashes.items())
 fields=[]
 for step in steps:
  for suffix in ['', '_solid']:
   p=out/f'solution_restart25600_step{step}{suffix}.vtu';assert p.is_file();fields.append(dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)))
 dump(out/'receipt.json',dict(exit_code=0,accepted_steps=steps,original_seed_unchanged=True,seconds=time.time()-start,peak_rss_bytes=peak,body_fields=fields,scope='Eight actual continuation steps succeed; full36-cycle production, matched-window comparison and periodicity gate still pending.'))
 print('Actual32-cycle checkpoint continued eight accepted steps; original seed unchanged',flush=True)
except BaseException as error:
 if proc is not None and proc.poll() is None:
  os.killpg(proc.pid,signal.SIGTERM)
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
 dump(out/'failure.json',dict(error=repr(error),seconds=time.time()-start));raise
