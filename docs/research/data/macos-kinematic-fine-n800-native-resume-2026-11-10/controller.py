"""Complete the interrupted reference from its immutable native step25500 seed."""
from pathlib import Path
import sys,os,json,shutil,hashlib,subprocess,time,signal
ROOT=Path(__file__).resolve().parents[2];b=ROOT/'build/recompute-20261109';source=b/'reference-kinematic-elastic-s24-l1-n800-nu0';w=b/'reference-kinematic-elastic-s24-l1-n800-nu0-native25500'
sys.path.insert(0,str(source/'audit-sources'))
from svfsi_restart_evidence import native_checkpoint,equivalent_input,analyze_chain

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
assert not w.exists() and (source/'failure.json').exists() and not (source/'completion.json').exists()
execution=json.loads((source/'execution.json').read_text());original=json.loads((source/'export.json').read_text());inp=(source/'svFSI.inp').read_text();seed=source/'results/stFile_25500.bin';record=native_checkpoint(seed)
assert record['step']==25500 and record['sha256']=='7ed3a3a1be8deb1584c90a636ec50b3c9c69204775d773836d6e63e4f3d488a2'
assert sha(source/'svFSI')==execution['binary_sha256']=='3eeacfeeb504ed1fe7f0223a23c004f7605078b7afabd21c2d6fa9f80f63c703'
for name,digest in original['files'].items():assert sha(source/name)==digest
assert shutil.disk_usage(b).free>20*2**30+256*2**20
assert time.time()-execution['start_unix']<execution['timeout_seconds']
w.mkdir()
for name in original['files']:
 target=w/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,target)
shutil.copy2(seed,w/'seed.bin');assert native_checkpoint(w/'seed.bin')==record
assert inp.count('Continue previous simulation: 0')==1
text=inp.replace('Continue previous simulation: 0','Continue previous simulation: 1\nSimulation initialization file path: seed.bin')
assert equivalent_input(text)==equivalent_input(inp)
(w/'svFSI.inp').write_text(text);report=json.loads(json.dumps(original));report['files']['svFSI.inp']=sha(w/'svFSI.inp');report['files']['seed.bin']=sha(w/'seed.bin');report['restart_provenance']=dict(record,layout='svFSI-7bdb74c-serial-linear-fsi-i32-f64');dump(w/'export.json',report)
command=[str(w/'svFSI'),'svFSI.inp'];dump(w/'execution.json',dict(source_execution=execution,command=command,seed=record,original_failure_sha256=sha(source/'failure.json'),start_unix=time.time(),scope='Same binary, physics, tolerances and remaining original wall-clock budget; native continuation25501..25600'))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');peak=0;start=time.monotonic();proc=None
try:
 with (w/'solve.log').open('w') as log:
  proc=subprocess.Popen(command,cwd=w,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);dump(w/'live.json',dict(pid=proc.pid,start_unix=time.time()))
  while proc.poll() is None:
   rss=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True,check=True)
   if rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
   free=shutil.disk_usage(w).free;elapsed=time.time()-execution['start_unix']
   if peak>execution['rss_limit_bytes'] or free<execution['disk_floor_bytes'] or elapsed>execution['timeout_seconds']:
    dump(w/'resource-trigger.json',dict(peak_rss_bytes=peak,free_bytes=free,elapsed_original_seconds=elapsed));raise RuntimeError('Resource limit')
   time.sleep(2)
 result=dict(exit_code=proc.returncode,seconds=time.monotonic()-start,peak_rss_bytes=peak);dump(w/'process-result.json',result);assert proc.returncode==0
 # Only immutable original outputs before the restart boundary enter the full history.
 links=[]
 for f in sorted((source/'results').glob('result_*.vtu')):
  step=int(f.stem.rsplit('_',1)[1])
  if step>25500:continue
  target=w/'results'/f.name
  if target.exists():assert sha(target)==sha(f)
  else:os.link(f,target)
  links.append(dict(step=step,source=str(f),path=str(target),sha256=sha(f)))
 dump(w/'inherited-output-manifest.json',links)
 chain=dict(schema='svfsi-native-restart-chain-v2',target_work=str(w),final_step=25600,segments=[dict(work=str(source),log=str(source/'solve.log'),first_step=1,last_step=25500,binary_sha256=execution['binary_sha256']),dict(work=str(w),log=str(w/'solve.log'),first_step=25501,last_step=25600,binary_sha256=execution['binary_sha256'])]);dump(w/'chain.json',chain)
 convergence=analyze_chain(w/'chain.json',expected_work=w,expected_steps=25600);dump(w/'convergence.json',convergence);assert convergence['passed']
 dump(w/'completion.json',dict(process=result,steps=25600,full_equation_convergence_passed=True,original_failure_preserved=True,scope='Native chain complete; physical audit, restart overlap review and budgets pending'));print('Native reference chain complete',flush=True)
except BaseException as error:
 if proc is not None and proc.poll() is None:
  os.killpg(proc.pid,signal.SIGTERM)
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
 dump(w/'failure.json',dict(error=repr(error),peak_rss_bytes=peak));raise
