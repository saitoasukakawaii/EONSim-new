"""Archive completed startup checks/failures and immutable controller snapshots."""
import importlib.util,json,os,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107');storage=Path('/mnt/d/EONSim-prod48-20261107')
os.sched_setaffinity(0,{19})
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-production-followups.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
snapshot=work/'queue-snapshot-f0422d0';snapshot.mkdir();states={}
for name in ['elastic-mpi-restart-current.json','womersley-alpha2-middle-current.json',
    'womersley-alpha2-middle-retry2-current.json','womersley-vector-boundary-current.json',
    'womersley-vector-boundary-retry2-current.json','alpha1-fine-vector-current.json','elastic-s24-budgets-current.json']:
    value=(work/name).read_text();states[name]=json.loads(value);(snapshot/name).write_text(value)
summary=dict(snapshot_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),states=states,
    scope='Completed MPI five-step preflight and alpha2 middle three-step field comparison, preserved startup failures, and dated active-controller snapshots. Long trajectories and waiting probes are not complete.')
(snapshot/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files=list(snapshot.iterdir())
mpi_failed=storage/'elastic-mpi-s12-l0-n400-f0422d0';files+=list(mpi_failed.rglob('*'))
mpi=storage/'elastic-mpi-s12-l0-n400-f0422d0-attempt2'
files+=list((mpi/'source').rglob('*'))+[mpi/n for n in ['original-controller.py','definition.json','case.json','fluid.msh','solid.msh','geometry.json','preflight-summary.json']]
for r in [1,2,4]:
    files+=list((mpi/f'r{r}/preflight').rglob('*'))+list((mpi/f'r{r}/parts').rglob('*'))
    files += [mpi/f'r{r}-{label}{suffix}' for label in ['prepare','preflight'] for suffix in ['.log','-command.json','-completion.json']]
for r in [2,4]:files+=[mpi/f'preflight-r{r}.json']
middle_failed=work/'womersley-alpha2-middle-f0422d0';files+=list(middle_failed.rglob('*'))
middle=work/'womersley-alpha2-middle-f0422d0-attempt2'
files+=list((middle/'source').rglob('*'))+[middle/n for n in ['original-controller.py','provenance.json','mpiexec-cpu21','preflight.json']]
for mode in ['old','vector']:
    files+=list((middle/('preflight-'+mode)).rglob('*'))
    files+=[middle/('preflight-'+mode+suffix) for suffix in ['.log','-command.json','-completion.json']]
for folder in [work/'womersley-vector-boundary-054b64a',work/'womersley-vector-boundary-f0422d0',work/'alpha1-fine-vector-f0422d0',work/'elastic-s24-budgets-f0422d0']:
    files+=list((folder/'source').rglob('*'))
    files += [p for p in folder.iterdir() if p.is_file() and (p.suffix in ('.py','.json') or p.name.startswith('mpiexec-'))]
c.capture('production-queues-2026-11-08',files,[snapshot/'summary.json',middle/'preflight.json',Path(__file__)])
