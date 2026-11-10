"""Recover the terminated dense branch from its unchanged production checkpoint."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,signal,subprocess,time
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-tautime-n400';out=w/'dense-recovery'
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):
 tmp=p.with_suffix(p.suffix+'.pending');tmp.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');tmp.replace(p)
d=json.loads((w/'definition.json').read_text());oldlive=json.loads((w/'live.json').read_text());deadline=oldlive['start_unix']+86400
old=subprocess.run(['ps','-p',str(oldlive['pid']),'-o','pid=,command='],capture_output=True,text=True)
assert old.returncode==1 and not old.stdout.strip()
assert json.loads((w/'failure.json').read_text())['error']=="RuntimeError('Disk floor')"
assert sha(w/'eonsim')==d['binary_sha256']
for name,digest in d['inputs'].items():assert sha(w/name)==digest
marker,generation=(w/'checkpoint/current').read_text().split();seed=w/'checkpoint'/generation
assert marker=='EONSim_checkpoint_v4' and (seed/'manifest').read_text().split()[:3]==[marker,'1','23200']
probe=json.loads((w/'dense-replay-probe/comparison.json').read_text());pd=json.loads((w/'dense-replay-probe/definition.json').read_text())
assert probe['passed'] and probe['steps']==list(range(23201,23209)) and len(probe['full_volume_pairs'])==16
assert pd['binary_sha256']==d['binary_sha256'] and pd['seed']==str(seed)
assert all(sha(seed/k)==v for k,v in pd['seed_sha256'].items())
for row in probe['full_volume_pairs']:assert sha(Path(row['original']))==sha(Path(row['replay']))==row['sha256']
original=json.loads((w/'dense/command.json').read_text());assert original[-2:]==['-restart',str(seed)]
cfg=json.loads((w/'dense/case.json').read_text());base=json.loads((w/'case.json').read_text());base['mesh']='../fluid.msh';base['fsi']['domains']['solid_mesh']='../solid.msh';base['fsi']['output_interval']=1
assert cfg==base and cfg['fsi']['steps']==25600
assert time.time()<deadline and shutil.disk_usage(w).free>24*2**30 and not out.exists()
print('Original failed process absent; exact checkpoint and16 replay pairs verified; original deadline retained',flush=True)
if args.check:raise SystemExit(0)
out.mkdir();shutil.copy2(w/'dense/case.json',out/'case.json')
command=original.copy();command[command.index('-checkpoint')+1]=str(out/'checkpoint')
dump(out/'command.json',command)
dump(out/'definition.json',dict(original_start_unix=oldlive['start_unix'],deadline_unix=deadline,seed=str(seed),seed_sha256=pd['seed_sha256'],binary_sha256=d['binary_sha256'],case_sha256=sha(out/'case.json'),controller_sha256=sha(Path(__file__)),compression_controller_sha256=sha(b/'compress-fsi-tau-recovery.py'),original_failure_sha256=sha(w/'failure.json'),scope='Replay dense23201..25600 from unchanged23200 production checkpoint; original failed branch retained. No numerical gate changes. Original24h deadline includes all held time.'))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
start=time.time();peak=0;held=False;events=[];compressor=None;compression_log=None;through=23200;process=None
try:
 with (out/'solve.log').open('w') as log:
  process=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while process.poll() is None:
   now=time.time();free=shutil.disk_usage(w).free
   if now>=deadline:raise TimeoutError('Original dense24h deadline')
   if free<20*2**30:raise RuntimeError('Disk floor')
   rss=subprocess.run(['ps','-p',str(process.pid),'-o','rss='],capture_output=True,text=True)
   if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
   if peak>d['memory_rss_limit_bytes']:raise MemoryError('RSS limit')
   if not held and free<22*2**30:
    os.killpg(process.pid,signal.SIGSTOP);held=True;events.append(dict(action='hold',unix=now,free_bytes=free))
   elif held and free>24*2**30:
    os.killpg(process.pid,signal.SIGCONT);held=False;events.append(dict(action='resume',unix=now,free_bytes=free))
   raw=(out/'solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fsi_step=(\d+) ',raw,re.M)));last=steps[-1] if steps else 23200
   assert steps==list(range(23201,last+1))
   if compressor is not None and compressor.poll() is not None:
    compression_log.close();assert compressor.returncode==0,'Compression failed';compressor=None
   if compressor is None and last-1>through and (last-1-through>=32 or held):
    through=last-1;compression_log=(out/f'compression-through{through}.log').open('w')
    compressor=subprocess.Popen(['python3',str(b/'compress-fsi-tau-recovery.py'),'--work',str(w),'--through',str(through)],stdout=compression_log,stderr=subprocess.STDOUT)
   dump(out/'live.json',dict(pid=process.pid,status='held' if held else 'running',last_complete_step=last,through=through,observed_unix=now,free_bytes=free,peak_rss_bytes=peak,deadline_unix=deadline,events=events))
   time.sleep(2)
 if compressor is not None:
  assert compressor.wait(timeout=300)==0;compression_log.close();compressor=None
 text=(out/'solve.log').read_text();assert process.returncode==0 and 'status=success' in text
 steps=list(map(int,re.findall(r'^fsi_step=(\d+) ',text,re.M)));assert steps==list(range(23201,25601))
 assert all(sha(seed/k)==v for k,v in pd['seed_sha256'].items())
 pairs=[]
 for step in range(23201,23640):
  for suffix in ['', '_solid']:
   name=f'solution_restart23200_step{step}{suffix}.vtu';a=w/'dense'/name;c=out/name
   assert sha(a)==sha(c);pairs.append(dict(step=step,suffix=suffix,sha256=sha(c)))
 dump(out/'overlap.json',dict(pairs=pairs,all_byte_identical=True))
 dump(out/'receipt.json',dict(exit_code=0,accepted_first=23201,accepted_last=25600,seconds=time.time()-start,elapsed_original_seconds=time.time()-oldlive['start_unix'],peak_rss_bytes=peak,events=events,scope='Dense numerical trajectory complete; merged inventory and physics/decomposition remain pending.'))
 print('Dense recovery complete;878 overlapping body files byte-identical; full physical audit pending',flush=True)
except BaseException as error:
 if process is not None and process.poll() is None:
  if held:os.killpg(process.pid,signal.SIGCONT)
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 if compressor is not None:
  compressor.wait(timeout=300);compression_log.close()
 dump(out/'failure.json',dict(error=repr(error),events=events,seconds=time.time()-start));raise
