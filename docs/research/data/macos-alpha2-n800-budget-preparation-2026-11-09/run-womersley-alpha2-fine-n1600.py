"""Bounded fresh alpha2 fine N1600 time control, adopted only after raw startup validation."""
from pathlib import Path
import json,os,sys,time,signal,subprocess,shutil,hashlib,argparse
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--alpha',type=int,choices=(2,),required=True);p.add_argument('--n',type=int,choices=(1600,),required=True);a=p.parse_args()
w=root/f'build/recompute-20261109/alpha{a.alpha}-s96-l1-n{a.n}'
assert not w.exists(),'Never overwrite or automatically resume a study'
assert shutil.disk_usage(root).free>42*1024**3, 'Need20GiB floor plus22GiB conservative raw capacity before new N1600 start'
screen=root/'build/recompute-20261109/alpha1-s96-l1-screen'
assert json.loads((screen/'report.json').read_text())['eligible']
assert json.loads((screen/'raw-review.json').read_text())['passed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(root/'build/macos-release/eonsim')==json.loads((screen/'definition.json').read_text())['binary_sha256']
cmd=[sys.executable,'scripts/study_womersley.py','--work',str(w),'--executable','build/macos-release/eonsim','--seed','96','8','8','--level','1','--alpha',str(a.alpha),'--steps-per-cycle',str(a.n),'--phases',str(a.n),'--warmup','2','--cycles','6','--ranks','1','--mumps','--lu-reuse-window','32','--chord','--cycles-per-solve','1','--timeout','86400']
record=w.with_suffix('.execution.json');logpath=w.with_suffix('.controller.log')
info=dict(command=cmd,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),start_unix=time.time(),rss_limit_bytes=6*1024**3,disk_floor_bytes=20*1024**3,timeout_seconds=86400,adoption_screen_sha256=sha(screen/'report.json'),raw_review_sha256=sha(screen/'raw-review.json'),scope='Fresh alpha2 fine N1600 temporal control for N800 target; six complete cycles from zero, default tau, original physics/gates. N400 failed budget retained.')
def save():record.write_text(json.dumps(info,indent=2)+'\n')
save();env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
with logpath.open('w') as log:
 proc=subprocess.Popen(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);info['pid']=proc.pid;save();peak=0;start=time.monotonic()
 try:
  while proc.poll() is None:
   listing=subprocess.check_output(['ps','-axo','pgid=,rss='],text=True)
   rss=sum(int(parts[1])*1024 for row in listing.splitlines() if len(parts:=row.split())==2 and int(parts[0])==proc.pid);peak=max(peak,rss)
   if peak>info['rss_limit_bytes']:raise MemoryError('Process group RSS limit')
   if shutil.disk_usage(root).free<info['disk_floor_bytes']:raise RuntimeError('Free disk floor')
   if time.monotonic()-start>info['timeout_seconds']:raise TimeoutError('Study time limit')
   time.sleep(3)
  info.update(exit_code=proc.returncode,seconds=time.monotonic()-start,peak_group_rss_bytes=peak,finished_unix=time.time());save();assert proc.returncode==0
 except BaseException as e:
  if proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
  info.update(error=repr(e),peak_group_rss_bytes=peak,exit_code=proc.returncode);save();raise
print(json.dumps(info),flush=True)
