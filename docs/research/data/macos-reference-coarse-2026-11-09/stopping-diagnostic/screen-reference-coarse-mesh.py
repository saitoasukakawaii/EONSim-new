"""Bounded local startup, loaded and native replay checks; no old raw inputs."""
from pathlib import Path
import sys,os,json,shutil,hashlib,subprocess,time,signal,re,struct
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from svfsi_restart_evidence import native_checkpoint,fsi_ilut_input
from audit_svfsi_convergence import analyze
from audit_pressure_tube import Domain,svfsi_frame
base=ROOT/'build/recompute-20261109';source=base/'reference-elastic-s24-l0-n800-nu0'
w=base/'reference-coarse-mesh-startup';w.mkdir()
old=base/'svfsi-build-cmake3/bin/svFSI';new=base/'svfsi-build-trilinos/bin/svFSI'
assert old.is_file() and new.is_file()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
original=json.loads((source/'export.json').read_text());inp=(source/'svFSI.inp').read_text()
for name,value in original['files'].items():assert sha(source/name)==value
shutil.copy2(old,w/'original-svFSI');shutil.copy2(new,w/'candidate-svFSI')
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),upstream='7bdb74cdd517310d6bf32c0bb7d42072aeac8658',trilinos='4a5f7906a6420ee2f9450367e9cc95b28c00d744',old_sha256=sha(old),new_sha256=sha(new),node_limit=2e-9,mass_relative_limit=1e-8,history_limit=2e-9,saved_norm_limit=2e-9,saved_norm_limit_source='scripts/svfsi_restart_evidence.py:reviewed_backend_transition existing bound',ranks=1,threads=1,scope='Coarse N800 from-zero mesh solver normalization diagnostic; unchanged physics and tolerances, no production adoption')
dump(w/'definition.json',definition);results={};env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
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
try:
 for name in ('cg-fsils','gmres-fsils','gmres-ilut'):run(name,seed=None,start=0,stop=100)
 dump(w/'diagnostic.json',dict(runs=results,scope=definition['scope'],production_adopted=False))
 print((w/'diagnostic.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'failure.json',dict(error=repr(e),completed=results));raise
