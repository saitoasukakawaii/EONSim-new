"""Record modest CPU FSI baselines; intentionally not a scalability claim."""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/poisson'))
from generate_mesh import write_mesh
p=argparse.ArgumentParser(); p.add_argument('--executable',type=Path,required=True)
p.add_argument('--mpiexec',default='/usr/bin/mpiexec'); p.add_argument('--work',type=Path,required=True)
p.add_argument('--subdivisions',type=int,default=4); p.add_argument('--ranks',type=int,nargs='+',default=[1,2,4])
a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True); root=Path(__file__).resolve().parents[1]
env=os.environ.copy(); env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',SUPERLU_ACC_OFFLOAD='0')
def run(args):
    start=time.perf_counter()
    r=subprocess.run([str(x) for x in args],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    elapsed=time.perf_counter()-start
    if r.returncode: raise RuntimeError(r.stdout)
    return r.stdout,elapsed
mesh=a.work/'cube.msh'; write_mesh(mesh,a.subdivisions)
records=[]
for case_name in ('rigid','hyperelastic'):
    case=root/'cases/fsi'/f'{case_name}.yaml'
    for ranks in a.ranks:
        partition=a.work/f'partition{ranks}'
        if case_name=='rigid': run([a.executable,'-case',case,'-mesh',mesh,'-prepare',partition,'-parts',ranks,'-device_enable','none'])
        for block in (False,True):
            name=f'{case_name}_{ranks}_{"block" if block else "direct"}'
            cmd=([a.mpiexec,'-n',ranks] if ranks>1 else [])+[a.executable,'-case',case,'-partition',partition,
                '-output',a.work/f'{name}.vtu','-stop_after',5,'-solver_report','-device_enable','none']
            if block: cmd+=['-block_pc']
            text,wall=run(cmd); (a.work/f'{name}.log').write_text(text)
            reports=[]
            for line in text.splitlines():
                if line.startswith('solver_report '):
                    reports.append({k:v for k,v in re.findall(r'(\w+)=([^\s]+)',line)})
            assert len(reports)==5
            record={'case':case_name,'ranks':ranks,'solver':'block' if block else 'direct','wall_seconds':wall,
                    'nodes_per_domain':(a.subdivisions+1)**3,'cells_per_domain':6*a.subdivisions**3,
                    'dofs':int(reports[0]['dofs']),'nnz':int(float(reports[0]['nnz'])),
                    'linear_iterations':sum(int(x['linear_iterations']) for x in reports)}
            for metric in ('solve_seconds','assembly_seconds','ghost_seconds'): record[metric]=sum(float(x[metric]) for x in reports)
            for metric in ('rss_max_bytes','rss_sum_bytes','peak_rss_max_bytes','peak_rss_sum_bytes'): record[metric]=max(float(x[metric]) for x in reports)
            records.append(record); print(json.dumps(record),flush=True)
(a.work/'summary.json').write_text(json.dumps(records,indent=2)+'\n')
