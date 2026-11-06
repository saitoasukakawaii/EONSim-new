"""Exploratory 30-cycle comparison; run from repository root, not an acceptance driver."""
import sys,os,re,subprocess,json
from pathlib import Path
sys.path[:0]=['tests','scripts']
from verify_fsi_inlet import Runner,generate
from fsi_cycle_metrics import compare_cycles
prefix=Path('/workspace/scratch/b8438b07bb94/eonsim-cloud/petsc-3.23.7')
os.environ.update(LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMPI_ALLOW_RUN_AS_ROOT='1',OMPI_ALLOW_RUN_AS_ROOT_CONFIRM='1',PRTE_ALLOW_RUN_AS_ROOT='1',PRTE_ALLOW_RUN_AS_ROOT_CONFIRM='1')
ceiling=max([int(m.group(1)) for p in Path('/dev/shm').iterdir() if (m:=re.fullmatch(r'__KMP_REGISTERED_LIB_(\d+)_\d+',p.name))],default=0)
if ceiling>20000:raise RuntimeError('PID ceiling')
while True:
 p=subprocess.Popen(['/bin/true']);p.wait()
 if p.pid>ceiling:break
results=[]
for mode in ('fixed','automatic'):
 run=Runner('build/cloud-3.23.7-release/eonsim',str(prefix/'bin/mpiexec'),Path('build/fsi-next-03')/mode,timeout=3600)
 cfg=json.loads(generate(run.work,n=2,periodic_flow=True).read_text())
 cfg['fsi'].update(dt=.001,steps=3000,output_interval=100)
 if mode=='automatic':cfg['fsi'].pop('stabilization_tau')
 fields,rows,log=run.solve('pilot',cfg,2)
 t=[r['time'] for r in rows];v=[r['area_displacement_y'] for r in rows]
 for cycle in range(3,30):
  results.append(dict(mode=mode,cycle=cycle,**compare_cycles(t,v,.1,cycle*.1,1e-4)))
 Path('build/fsi-next-03/pilot-results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(mode,results[-1],flush=True)
