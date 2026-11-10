"""Fresh explicitly patched reference family; frozen provenance and convergence auditor."""
from pathlib import Path
import os,sys,argparse,json,hashlib,shutil,subprocess,time,signal
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from export_svfsi_tube import export
from svfsi_restart_evidence import fsi_ilut_input
p=argparse.ArgumentParser();p.add_argument('--level',type=int,choices=(0,1),required=True);p.add_argument('--n',type=int,choices=(400,800),required=True);p.add_argument('--backend',choices=('fsils','ilut'),required=True);a=p.parse_args()
b=ROOT/'build/recompute-20261109';src=b/f'elastic-s24-l{a.level}-n{a.n}';w=b/f'reference-patched-elastic-s24-l{a.level}-n{a.n}-nu0';assert not w.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
adoption_path=b/'reference-patched-adoption.json';adoption=json.loads(adoption_path.read_text())
assert adoption['passed'] and adoption['user_authorized']
exe=b/'svfsi-strict-increment-build/bin/svFSI';patch=b/'svfsi-strict-increment.patch'
assert sha(exe)==adoption['binary_sha256'] and sha(patch)==adoption['patch_sha256']
for name,digest in adoption['proofs'].items():assert sha(b/name)==digest
proof=dict(adoption_path=str(adoption_path),adoption_sha256=sha(adoption_path),proofs=adoption['proofs'])
assert (a.level,a.n,a.backend) in [(0,800,'fsils'),(1,400,'ilut'),(1,800,'ilut')]
cfg=json.loads((src/'case.json').read_text());assert cfg['fsi']['steps']==32*a.n and cfg['fsi']['pressure_time']['ramp_time']==16*cfg['fsi']['pressure_time']['period']
assert json.loads((src/'geometry.json').read_text())['red_refinements']==a.level
before={name:sha(src/name) for name in ('case.json','fluid.msh','solid.msh','geometry.json')}
report=export(src/'case.json',w,stage_pressure=True,general_pressure=True,output_start_step=29*a.n,tight_linear_atol=1e-26,mesh_poisson=0.)
if a.backend=='ilut':
 p=w/'svFSI.inp';p.write_text(fsi_ilut_input(p.read_text()));report['files']['svFSI.inp']=sha(p);report['explicit_fsi_preconditioner']='Trilinos-ILUT';dump(w/'export.json',report)
assert before=={name:sha(src/name) for name in before};shutil.copy2(exe,w/'svFSI')
shutil.copy2(patch,w/'source.patch')
report['reference_build']=dict(kind='patched-fixed-reference',base_commit=adoption['base_commit'],binary=dict(path='svFSI',sha256=sha(w/'svFSI')),patch=dict(path='source.patch',sha256=sha(w/'source.patch')))
for name in ['svFSI','source.patch']:report['files'][name]=sha(w/name)
# Freeze the audit implementation before launch; later workspace edits cannot
# change which acceptance code or source hash this running controller uses.
(w/'audit-sources').mkdir()
for name in ['audit_svfsi_convergence.py','svfsi_restart_evidence.py']:
 shutil.copy2(ROOT/'scripts'/name,w/'audit-sources'/name)
 report['files']['audit-sources/'+name]=sha(w/'audit-sources'/name)
dump(w/'export.json',report)

command=[str(w/'svFSI'),'svFSI.inp'];definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_case=str(src/'case.json'),source_inputs=before,binary_sha256=sha(exe),backend=a.backend,backend_proof=proof,level=a.level,steps_per_cycle=a.n,cycles=32,ramp_cycles=16,ranks=1,threads=1,command=command,start_unix=time.time(),rss_limit_bytes=3*1024**3,disk_floor_bytes=20*1024**3,timeout_seconds=86400,reference_build=report['reference_build'],user_authorization='允许采用有记录、经验证的补丁',scope='Fresh zero-state full32cycles with explicitly patched pinned reference; full convergence/fields/budgets required')
dump(w/'execution.json',definition);env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');start=time.monotonic();peak=0
try:
 with (w/'solve.log').open('w') as log:
  proc=subprocess.Popen(command,cwd=w,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);dump(w/'live.json',dict(pid=proc.pid,start_unix=time.time()))
  try:
   while proc.poll() is None:
    rss=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True)
    if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
    if peak>definition['rss_limit_bytes'] or shutil.disk_usage(w).free<definition['disk_floor_bytes'] or time.monotonic()-start>definition['timeout_seconds']:raise RuntimeError('Resource limit')
    time.sleep(2)
  except BaseException:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   raise
 result=dict(exit_code=proc.returncode,seconds=time.monotonic()-start,peak_rss_bytes=peak,finished_unix=time.time());dump(w/'process-result.json',result);assert proc.returncode==0
 subprocess.run([sys.executable,str(w/'audit-sources/audit_svfsi_convergence.py'),'--work',str(w),'--log',str(w/'solve.log'),'--output',str(w/'convergence.json')],env=env,stdout=(w/'convergence-summary.log').open('w'),stderr=subprocess.STDOUT,check=True)
 convergence=json.loads((w/'convergence.json').read_text());assert convergence['passed'] and convergence['reference_build']==report['reference_build']
 dump(w/'completion.json',dict(process=result,steps=32*a.n,full_equation_convergence_passed=True,source_case_sha256=before['case.json'],reference_build=report['reference_build'],scope='Numerical and equation convergence complete; full-field/physics/budgets pending'))
 print((w/'completion.json').read_text(),flush=True)
except BaseException as e:
 dump(w/'failure.json',dict(error=repr(e),peak_rss_bytes=peak));raise
