from pathlib import Path
import sys,os,json,shutil,hashlib,subprocess,time,signal,re,struct
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from svfsi_restart_evidence import native_checkpoint,fsi_ilut_input
from audit_svfsi_convergence import analyze
base=ROOT/'build/recompute-20261109';source=base/'reference-elastic-s24-l1-n800-nu0';w=base/'reference-mesh-backend-diagnostic'
assert (w/'failure.json').exists() and not (w/'gmres-ilut').exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def run(name,candidate=True,ilut=False,start=400,seed=None,stop=540):
 d=w/name;d.mkdir();report=json.loads(json.dumps(original))
 for file in original['files']:
  p=d/file;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/file,p)
 shutil.copy2(source/'source-case.json',d/'source-case.json')
 text=inp.replace('Number of time steps: 25600',f'Number of time steps: {stop}').replace('Increment in saving restart files: 100','Increment in saving restart files: 1').replace('Start saving after time step: 23200',f'Start saving after time step: {start+1}')
 if name!='cg-fsils':
  before,marker,mesh=text.partition('Add equation: mesh {\n');assert marker and mesh.count('LS type: CG')==1
  mesh=mesh.replace('LS type: CG','LS type: GMRES')
  if name=='gmres-ilut':mesh=mesh.replace('Preconditioner: FSILS','Preconditioner: Trilinos-ILUT\n    Use Trilinos for assembly: 0')
  text=before+marker+mesh
 if seed:
  shutil.copy2(seed,d/'seed.bin');record=native_checkpoint(d/'seed.bin');assert record['step']==start
  text=text.replace('Continue previous simulation: 0','Continue previous simulation: 1\nSimulation initialization file path: seed.bin')
  report['files']['seed.bin']=sha(d/'seed.bin');report['restart_provenance']=dict(record,layout='svFSI-7bdb74c-serial-linear-fsi-i32-f64')
 (d/'svFSI.inp').write_text(text);report['files']['svFSI.inp']=sha(d/'svFSI.inp');report['output_start_step']=start+1;report['local_backend_screen']=dict(ilut=ilut,candidate=candidate,start=start,stop=stop);dump(d/'export.json',report)
 cmd=[str(w/('candidate-svFSI' if candidate else 'original-svFSI')),'svFSI.inp'];dump(d/'command.json',cmd);t=time.monotonic();peak=0
 with (d/'solve.log').open('w') as log:
  proc=subprocess.Popen(cmd,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   while proc.poll() is None:
    rss=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True)
    if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
    if peak>2*1024**3 or shutil.disk_usage(w).free<20*1024**3 or time.monotonic()-t>1800:raise RuntimeError('Resource limit')
    time.sleep(.2)
  except BaseException:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   raise
 assert proc.returncode==0,(name,proc.returncode)
 convergence=analyze(d,d/'solve.log');dump(d/'convergence.json',convergence)
 row=dict(convergence_passed=convergence['passed'],seconds=time.monotonic()-t,peak_rss_bytes=peak,exit_code=0,start=start,stop=stop);results[name]=row;dump(d/'receipt.json',row);return d

def actual(folder,kind,step):
 matches=[p for p in folder.glob(kind+'_*') if p.stem.rsplit('_',1)[1].isdecimal() and int(p.stem.rsplit('_',1)[1])==step]
 assert len(matches)==1,(folder,kind,step);return matches[0]
original=json.loads((source/'export.json').read_text());inp=(source/'svFSI.inp').read_text()
for name,value in original['files'].items():assert sha(source/name)==value
definition=json.loads((w/'definition.json').read_text());assert sha(w/'candidate-svFSI')==definition['new_sha256']
results={'cg-fsils':json.loads((w/'cg-fsils/receipt.json').read_text())}
r=json.loads((w/'gmres-fsils/prefix-convergence.json').read_text());assert not r['passed'] and r['first_step']==401
partial=dict(start=400,stop=r['last_step'],convergence_passed=False,scientific_stop=True,intended_stop=540,scope='Only frozen completed prefix included; later partial tail excluded')
results['gmres-fsils']=partial;dump(w/'gmres-fsils/partial-receipt.json',partial)
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
try:
 run('gmres-ilut',seed=source/'results/stFile_400.bin')
 dump(w/'diagnostic.json',dict(runs=results,scope=definition['scope'],production_adopted=False,original_failure_preserved=True))
 print((w/'diagnostic.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'continuation-failure.json',dict(error=repr(e),completed=results));raise
