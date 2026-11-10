"""Fresh single-rank 32-cycle elastic study; save dense final three cycles."""
from pathlib import Path
import argparse,os,sys,json,math,hashlib,shutil,subprocess,time,signal,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'cases/fsi'))
from generate_pressure_tube import generate
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--level',type=int,choices=[0,1],required=True);p.add_argument('--n',type=int,choices=[400,800,1600],required=True);p.add_argument('--length',type=float,default=12);p.add_argument('--axial',type=int,default=12);a=p.parse_args()
work=a.work.resolve();n=a.n

def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert (a.level,n,a.length,a.axial)==(1,800,12,12)
base=ROOT/'build/recompute-20261109';prepared=base/'elastic-geometry48-preparation';probe=base/'elastic-geometry48-probe'
preparation=json.loads((prepared/'preparation.json').read_text());check=json.loads((probe/'receipt.json').read_text())
assert check['exit_code']==0 and check['steps']==list(range(1,9)) and check['log_sha256']==sha(probe/'solve.log')
assert json.loads((probe/'definition.json').read_text())['source_preparation_sha256']==sha(prepared/'preparation.json')
assert not work.exists();work.mkdir()
for name,digest in preparation['prepared_inputs'].items():
 assert sha(prepared/name)==digest;shutil.copy2(prepared/name,work/name)
case=work/'case.json'
cfg=json.loads(case.read_text());cfg['fsi']['pressure_time']['ramp_time']=16*2*math.pi;dump(case,cfg)
shutil.copy2(ROOT/'build/macos-release/eonsim',work/'eonsim')
definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),steps_per_cycle=n,cycles=32,ramp_cycles=16,seed=[24,2,a.axial],length=a.length,generator_sha256=sha(ROOT/'cases/fsi/generate_pressure_tube.py'),controller_sha256=sha(Path(__file__)),level=a.level,ranks=1,threads=1,memory_rss_limit_bytes=3*1024**3,disk_floor_bytes=20*1024**3,binary_sha256=sha(work/'eonsim'),inputs={f:sha(work/f) for f in ['case.json','fluid.msh','solid.msh','geometry.json']},solver_options=['-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32'],geometry_control_preparation_sha256=sha(prepared/'preparation.json'),startup_probe_sha256=sha(probe/'receipt.json'),scope='Fresh fixed-topology24-to48 polygon geometry control; same node/cell counts and physical/time settings as S24 level1 N800. Not a nested field-refinement budget member; full32cycle response comparison pending.')
dump(work/'definition.json',definition)
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
receipts=[];allsteps=[]
try:
 for label,target,cadence in [('early',29*n,n),('dense',32*n,1)]:
  folder=work/label;folder.mkdir();local=json.loads(json.dumps(cfg));local['mesh']='../fluid.msh';local['fsi']['domains']['solid_mesh']='../solid.msh';local['fsi']['output_interval']=cadence;dump(folder/'case.json',local)
  command=[str(work/'eonsim'),'-case','case.json','-checkpoint',str(work/'checkpoint'),'-stop_after',str(target),*definition['solver_options']]
  if label=='dense':
   marker,generation=(work/'checkpoint/current').read_text().split();manifest=(work/'checkpoint'/generation/'manifest').read_text().split();assert marker=='EONSim_checkpoint_v4' and int(manifest[2])==29*n
   command+=['-restart',str(work/'checkpoint'/generation)]
  dump(folder/'command.json',command);start=time.monotonic();peak=0
  with (folder/'solve.log').open('w') as log:
   process=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   dump(work/'live.json',dict(pid=process.pid,label=label,target=target,start_unix=time.time()))
   try:
    while process.poll() is None:
     if time.monotonic()-start>86400:raise TimeoutError(label)
     rss=subprocess.run(['ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True)
     if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
     if peak>definition['memory_rss_limit_bytes']:raise MemoryError('RSS limit')
     if shutil.disk_usage(work).free<definition['disk_floor_bytes']:raise RuntimeError('Disk floor')
     time.sleep(2)
   except BaseException:
    if process.poll() is None:
     os.killpg(process.pid,signal.SIGTERM)
     try:process.wait(timeout=10)
     except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    raise
  text=(folder/'solve.log').read_text();assert process.returncode==0 and 'status=success' in text
  steps=list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)));assert steps==list(range(1 if label=='early' else 29*n+1,target+1))
  allsteps+=steps
  row=dict(label=label,accepted_first=steps[0],accepted_last=steps[-1],seconds=time.monotonic()-start,peak_rss_bytes=peak,exit_code=process.returncode)
  receipts.append(row);dump(folder/'receipt.json',row);dump(work/'progress.json',receipts)
 assert allsteps==list(range(1,32*n+1))
 # Merge original saved series by their actual published times; no synthetic frames.
 for suffix in ['', '_solid']:
  root=ET.Element('VTKFile',type='Collection',version='0.1',byte_order='LittleEndian');collection=ET.SubElement(root,'Collection');times=[]
  for label in ['early','dense']:
   stem='solution' if label=='early' else f'solution_restart{29*n}'
   for data in ET.parse(work/label/(stem+suffix+'.pvd')).findall('.//DataSet'):
    values=dict(data.attrib);values['file']=label+'/'+values['file'];assert (work/values['file']).exists();times.append(float(values['timestep']));ET.SubElement(collection,'DataSet',values)
  assert all(x<y for x,y in zip(times,times[1:]));ET.ElementTree(root).write(work/('solution'+suffix+'.pvd'),encoding='utf-8',xml_declaration=True)
 dump(work/'completion.json',dict(accepted_steps=32*n,receipts=receipts,scope='Numerics complete; audit, loaded replay, budgets and physics not yet evaluated'))
 print((work/'completion.json').read_text(),flush=True)
except BaseException as error:
 dump(work/'failure.json',dict(error=repr(error),receipts=receipts));raise
