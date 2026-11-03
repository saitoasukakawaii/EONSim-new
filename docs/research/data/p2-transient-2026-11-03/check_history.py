"""Supplemental local HDF5 fault checks; requires h5py, not a CI dependency."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
import h5py
root=Path.cwd()
work=root/'build/p2-local/history-faults';work.mkdir(exist_ok=True)
exe=root/'build/cloud-3.23.7-debug/eonsim'
prefix=root/'.cloud/petsc-3.23.7'
env=dict(os.environ,LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp',PRTE_MCA_rmaps_default_mapping_policy=':oversubscribe',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
records=[]
for scheme in ('bdf2','generalized_alpha'):
 src=root/'build/cloud-3.23.7-debug/scalar-p2-failure'/f'{scheme}-2'
 # Fresh accepted checkpoint must use the current signature implementation.
 fresh=work/f'{scheme}-fresh';fresh.mkdir(exist_ok=True)
 cmd=[str(prefix/'bin/mpiexec'),'-n','2',str(exe),'-case',str(src/'case.json'),'-partition',str(src/'part'),'-checkpoint',str(fresh),'-stop_after','2','-output',str(work/f'{scheme}.vtu')]
 result=subprocess.run(cmd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
 assert result.returncode==0,result.stdout
 for mode in ('missing','invalid','nonfinite','space-identity'):
  target=work/f'{scheme}-{mode}'
  if target.exists():shutil.rmtree(target)
  shutil.copytree(fresh,target)
  generation=(target/'current').read_text().split()[1]
  rankfile=target/generation/'state_rank1.h5'
  part=src/'part'
  if mode=='space-identity':
   part=target/'part';shutil.copytree(src/'part',part)
   with h5py.File(part/'rank_1.h5','r+') as f:
    g=f['scalar_p2'];keys=g['entities'][:].reshape(-1,2)
    i=next(i for i,k in enumerate(keys) if k[0]!=k[1]);g['entity_ids'][i]+=1
   expected='Checkpoint mesh/partition/physics mismatch'
  else:
   with h5py.File(rankfile,'r+') as f:
    if mode=='missing':del f['previous' if scheme=='bdf2' else 'rate'];expected='Checkpoint HDF5 operation failed'
    elif mode=='invalid':f['time_metadata'][0]=-1;expected='Invalid P2'
    else:f['scalar'][0]=float('nan');expected='Nonfinite checkpoint field'
  before=hashlib.sha256((target/'current').read_bytes()).hexdigest()
  cmd=[str(prefix/'bin/mpiexec'),'-n','2',str(exe),'-case',str(src/'case.json'),'-partition',str(part),'-restart',str(target),'-output',str(target/'bad.vtu')]
  result=subprocess.run(cmd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
  (target/'run.log').write_text(result.stdout)
  assert result.returncode and expected in result.stdout,result.stdout
  assert not (target/'bad.pvtu').exists() and not (target/'bad.pvd').exists()
  assert hashlib.sha256((target/'current').read_bytes()).hexdigest()==before
  records.append(dict(scheme=scheme,mode=mode,ranks=2,expected=expected,exit_code=result.returncode,command=cmd))
(work/'evidence.json').write_text(json.dumps(records,indent=2)+'\n')
print('8/8 checkpoint history/space fault checks passed')
