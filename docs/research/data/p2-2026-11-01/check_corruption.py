import os,json,shutil,subprocess
from pathlib import Path
import h5py
root=Path.cwd();base=root/'build/cloud-3.23.7-debug/scalar-p2/patch-2';work=root/'build/p2-local/corruption';work.mkdir(exist_ok=True)
prefix=root/'.cloud/petsc-3.23.7';env=dict(os.environ,LD_LIBRARY_PATH=str(prefix/'lib'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp',PRTE_MCA_rmaps_default_mapping_policy=':oversubscribe')
exe=root/'build/cloud-3.23.7-debug/eonsim'
for kind in ('missing','connectivity','owner'):
 folder=work/kind;folder.mkdir(exist_ok=True);part=folder/'part';shutil.copytree(base/'part',part,dirs_exist_ok=True)
 cfg=json.loads((base/'case.json').read_text());cfg['mesh']=str(base/'mesh.msh');cfg['output']=str(folder/'failed.vtu');case=folder/'case.json';case.write_text(json.dumps(cfg))
 with h5py.File(part/'rank_1.h5','r+') as f:
  if kind=='missing':del f['scalar_p2']
  elif kind=='connectivity':f['scalar_p2/cells'][0]=f['scalar_p2/cells'][1]
  else:f['scalar_p2/owners'][0]=99
 r=subprocess.run([str(prefix/'bin/mpiexec'),'-n','2',str(exe),'-case',str(case),'-partition',str(part)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
 (folder/'run.log').write_text(r.stdout);assert r.returncode!=0 and not (folder/'failed.pvtu').exists(),r.stdout
 expected={'missing':'Missing P2 space','connectivity':'P2 connectivity does not match geometry','owner':'Invalid P2 entity ownership'}[kind];assert expected in r.stdout,r.stdout
 print(kind,'rejected on rank 1; no successful output index')
