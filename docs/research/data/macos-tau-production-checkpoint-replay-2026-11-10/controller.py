"""Bounded replay of the actual failed production dense branch; no state synthesis."""
from pathlib import Path
import hashlib,json,os,re,shutil,signal,subprocess,time
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-tautime-n400';out=w/'dense-replay-probe'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
definition=json.loads((w/'definition.json').read_text());live=json.loads((w/'live.json').read_text())
old=subprocess.run(['ps','-p',str(live['pid']),'-o','pid=,command='],capture_output=True,text=True)
assert old.returncode==1 and not old.stdout.strip(), 'Original solver still exists or process inspection failed'
assert json.loads((w/'failure.json').read_text())['error']=="RuntimeError('Disk floor')"
assert sha(w/'eonsim')==definition['binary_sha256']
for name,digest in definition['inputs'].items():assert sha(w/name)==digest
marker,generation=(w/'checkpoint/current').read_text().split();seed=w/'checkpoint'/generation
assert marker=='EONSim_checkpoint_v4'
parts=(seed/'manifest').read_text().split();assert parts[:3]==['EONSim_checkpoint_v4','1','23200']
assert set(p.name for p in seed.iterdir())=={'manifest','state_rank0.h5'}
seed_hashes={p.name:sha(p) for p in seed.iterdir()}
cfg=json.loads((w/'dense/case.json').read_text());base=json.loads((w/'case.json').read_text());base['mesh']='../fluid.msh';base['fsi']['domains']['solid_mesh']='../solid.msh';base['fsi']['output_interval']=1
assert cfg==base and cfg['fsi']['steps']==25600
original=json.loads((w/'dense/command.json').read_text());assert original[-2:]==['-restart',str(seed)]
assert shutil.disk_usage(w).free>20*2**30+128*2**20
assert not out.exists();out.mkdir();shutil.copy2(w/'dense/case.json',out/'case.json')
command=original.copy();command[command.index('-checkpoint')+1]=str(out/'checkpoint');command[command.index('-stop_after')+1]='23208'
dump(out/'definition.json',dict(command=command,original_command=original,seed=str(seed),seed_sha256=seed_hashes,binary_sha256=sha(w/'eonsim'),case_sha256=sha(out/'case.json'),controller_sha256=sha(Path(__file__)),scope='Eight production overlap steps23201..23208; same binary, input and exact v4 checkpoint. Not full trajectory completion.'))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None);start=time.time();peak=0
try:
 with (out/'solve.log').open('w') as log:
  p=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   while p.poll() is None:
    rss=subprocess.run(['ps','-p',str(p.pid),'-o','rss='],capture_output=True,text=True)
    if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
    assert peak<3*2**30 and time.time()-start<600 and shutil.disk_usage(w).free>20*2**30
    time.sleep(1)
  except BaseException:
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
 text=(out/'solve.log').read_text();assert p.returncode==0 and 'status=success' in text
 steps=list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)));assert steps==list(range(23201,23209))
 pairs=[]
 for step in steps:
  for suffix in ['','_solid']:
   name=f'solution_restart23200_step{step}{suffix}.vtu';a=w/'dense'/name;c=out/name
   assert a.is_file() and c.is_file();assert sha(a)==sha(c),name
   pairs.append(dict(step=step,original=str(a),replay=str(c),sha256=sha(c),bytes=c.stat().st_size))
 assert all(sha(seed/name)==digest for name,digest in seed_hashes.items())
 dump(out/'comparison.json',dict(passed=True,process_exit_code=p.returncode,seconds=time.time()-start,peak_rss_bytes=peak,steps=steps,full_volume_pairs=pairs,seed_unchanged=True,scope='16 complete fluid/solid VTU pairs byte-identical over first8 dense restart steps; boundaries and later trajectory not compared.'))
 print('Eight production checkpoint replay steps and16 complete body fields byte-identical',flush=True)
except BaseException as error:
 dump(out/'failure.json',dict(error=repr(error),seconds=time.time()-start));raise
