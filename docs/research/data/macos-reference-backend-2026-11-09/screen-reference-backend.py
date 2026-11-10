"""Bounded local startup, loaded and native replay checks; no old raw inputs."""
from pathlib import Path
import sys,os,json,shutil,hashlib,subprocess,time,signal,re,struct
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from svfsi_restart_evidence import native_checkpoint,fsi_ilut_input
from audit_svfsi_convergence import analyze
from audit_pressure_tube import Domain,svfsi_frame
base=ROOT/'build/recompute-20261109';source=base/'reference-elastic-s24-l0-n400-nu0'
w=base/'reference-backend-screen';w.mkdir()
old=base/'svfsi-build-cmake3/bin/svFSI';new=base/'svfsi-build-trilinos/bin/svFSI'
assert old.is_file() and new.is_file()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
original=json.loads((source/'export.json').read_text());inp=(source/'svFSI.inp').read_text()
for name,value in original['files'].items():assert sha(source/name)==value
shutil.copy2(old,w/'original-svFSI');shutil.copy2(new,w/'candidate-svFSI')
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),upstream='7bdb74cdd517310d6bf32c0bb7d42072aeac8658',trilinos='4a5f7906a6420ee2f9450367e9cc95b28c00d744',old_sha256=sha(old),new_sha256=sha(new),node_limit=2e-9,mass_relative_limit=1e-8,history_limit=2e-9,ranks=1,threads=1,scope='Coarse local startup/loaded/replay backend proof; not fine or long-run qualification')
dump(w/'definition.json',definition);results={};env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
def run(name,candidate=False,ilut=False,start=0,seed=None,stop=20):
 d=w/name;d.mkdir();report=json.loads(json.dumps(original))
 for file in original['files']:
  p=d/file;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/file,p)
 shutil.copy2(source/'source-case.json',d/'source-case.json')
 text=inp.replace('Number of time steps: 12800',f'Number of time steps: {stop}').replace('Increment in saving restart files: 100','Increment in saving restart files: 1').replace('Start saving after time step: 11600',f'Start saving after time step: {start+1}')
 if ilut:text=fsi_ilut_input(text)
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
 convergence=analyze(d,d/'solve.log');dump(d/'convergence.json',convergence);assert convergence['passed']
 row=dict(seconds=time.monotonic()-t,peak_rss_bytes=peak,exit_code=0,start=start,stop=stop);results[name]=row;dump(d/'receipt.json',row);return d
try:
 run('startup-old');run('startup-fsils',True);run('startup-ilut',True,True)
 seed=source/'results/stFile_12400.bin'
 run('loaded-old',start=12400,seed=seed,stop=12420)
 run('loaded-fsils',True,start=12400,seed=seed,stop=12420)
 run('loaded-ilut',True,True,start=12400,seed=seed,stop=12420)
 run('loaded-replay',True,True,start=12410,seed=w/'loaded-ilut/results/stFile_12410.bin',stop=12420)
 case=base/'reference-elastic-s24-l0-n400-nu0-case';domains=[Domain(case/'fluid.msh'),Domain(case/'solid.msh')]
 ds=.01*(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
 comparisons={}
 for name,baseline in [('startup-fsils','startup-old'),('startup-ilut','startup-old'),('loaded-fsils','loaded-old'),('loaded-ilut','loaded-old'),('loaded-replay','loaded-ilut')]:
  row=results[name];node=mass=history=0.;pairs=0
  for step in range(row['start']+1,row['stop']+1):
   folders=[w/baseline/'results',w/name/'results'];frames=[svfsi_frame(folder/f'result_{step}.vtu',domains) for folder in folders]
   for i,domain in enumerate(domains):
    for field,scale in scales[i].items():
     x,y=frames[0][i],frames[1][i];delta=max(abs(a-b) for n in x for a,b in zip(x[n][field],y[n][field]));node=max(node,delta);mass=max(mass,domain.rms_difference(x,y,field)/scale)
   records=[native_checkpoint(folder/f'stFile_{step}.bin') for folder in folders]
   assert records[0]['stamp']==records[1]['stamp'] and records[0]['time']==records[1]['time']
   values=[np.frombuffer((folder/f'stFile_{step}.bin').read_bytes(),dtype='<f8',offset=32) for folder in folders]
   assert values[0].shape==values[1].shape and np.array_equal(values[0][2:4],values[1][2:4])
   history=max(history,float(np.max(np.abs(values[0][4:]-values[1][4:]),initial=0)));pairs+=1
  assert node<2e-9 and mass<1e-8 and history<2e-9,(name,node,mass,history)
  comparisons[name]=dict(pairs=pairs,maximum_node_delta=node,maximum_relative_mass=mass,maximum_native_history_delta=history,exact_native_time=True,exact_saved_equation_norms=True,passed=True)
 dump(w/'report.json',dict(definition=definition,runs=results,comparisons=comparisons,passed=True,adopted=False,scope=definition['scope']))
 print((w/'report.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'failure.json',dict(error=repr(e),completed=results));raise
