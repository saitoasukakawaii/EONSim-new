"""Five-step red-refined coupled cost/convergence screen on the free CPU18."""
import fcntl,hashlib,json,math,os,re,shutil,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'elastic-s12-l1-n200-probe-c49c69c'
status=work/'elastic-space-probe-current.json'
prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not out.exists() and not status.exists()
env=os.environ.copy()
for key in list(env):
    if key in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH') or key.startswith(('OMPI_','PMIX_','PRTE_')):env.pop(key)
env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR=tempfile.mkdtemp(prefix='eonsim-space-probe-'))
refenv=env.copy();refenv['PATH']='/usr/bin:/bin'
for key in list(refenv):
    if key=='LD_LIBRARY_PATH' or key.startswith(('OMPI_','PMIX_','PRTE_')):refenv.pop(key)
def update(state,**kw):
    r=dict(state=state,pid=os.getpid(),cpu=18,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2)+'\n');tmp.replace(status);print(json.dumps(r),flush=True)
def run(name,cmd,cwd,reference=False):
    cmd=list(map(str,cmd));update('running',job=name,command=cmd)
    (out/(name+'-command.json')).write_text(json.dumps(dict(command=cmd,cwd=str(cwd)),indent=2)+'\n')
    start=time.perf_counter()
    with (out/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=cwd,env=refenv if reference else env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    return time.perf_counter()-start
try:
    with (work/'elastic-ramp-queue.lock').open('a') as lock:
        update('waiting_for_cpu18_queue');fcntl.flock(lock,fcntl.LOCK_EX)
        resources=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                args=(p/'cmdline').read_bytes().split(b'\0')
                if args and Path(os.fsdecode(args[0])).name in ('eonsim','svFSI'):
                    cpus=sorted(os.sched_getaffinity(int(p.name)));assert 18 not in cpus
                    resources.append(dict(pid=int(p.name),cpus=cpus))
            except (FileNotFoundError,ProcessLookupError):pass
        os.sched_setaffinity(0,{18});out.mkdir();shutil.copy2(__file__,out/'original-controller.py')
        source=out/'source';hashes={}
        for name in ('cases/fsi/generate_pressure_tube.py','cases/fsi/generate_tube.py','scripts/study_rigid_tube.py',
                     'scripts/export_svfsi_tube.py','scripts/audit_svfsi_convergence.py'):
            dst=source/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dst);hashes[name]=sha(dst)
        run('generate',[sys.executable,source/'cases/fsi/generate_pressure_tube.py','--output',out/'case',
            '--level','1','--steps-per-cycle','200','--cycles','1'],root)
        case=out/'case/case.json';cfg=json.loads(case.read_text());cfg['fsi'].update(steps=5,output_interval=1)
        case.write_text(json.dumps(cfg,indent=2)+'\n');shutil.copy2(work/'eonsim-b072cc8',out/'eonsim')
        (out/'provenance.json').write_text(json.dumps(dict(source_head='c49c69c',exact_sources=hashes,
            resources=resources,cpu=18,eonsim_sha256=sha(out/'eonsim'),
            scope='Five-step S12 level1 N200 no-ramp onset cost/convergence screen; not periodic or spatial qualification'),indent=2)+'\n')
        timings={}
        timings['eonsim']=run('eonsim',[out/'eonsim','-case','case.json','-solver_report'],out/'case')
        text=(out/'eonsim.log').read_text();assert 'status=success' in text
        rows=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith('fsi_step=')]
        assert len(rows)==5 and [int(r['fsi_step']) for r in rows]==list(range(1,6))
        for r in rows:assert all(math.isfinite(float(r[k])) and float(r[k])>0 for k in ('endpoint_min_fluid_j','endpoint_min_solid_j'))
        ref=out/'reference'
        run('export',[sys.executable,source/'scripts/export_svfsi_tube.py','--case',case,'--output',ref,'--stage-pressure','--tight-linear-atol','1e-26'],root)
        timings['svfsi']=run('svfsi',[work/'reference/build/bin/svFSI','svFSI.inp'],ref,True)
        run('convergence',[sys.executable,source/'scripts/audit_svfsi_convergence.py','--work',ref,
            '--log',out/'svfsi.log','--output',out/'svfsi-convergence.json'],root)
        (out/'summary.json').write_text(json.dumps(dict(timings=timings,steps=5,accepted_rows=rows,
            reference_convergence=json.loads((out/'svfsi-convergence.json').read_text()),
            scope='Local concurrent cost observation, not a performance/scaling claim or periodic qualification'),indent=2)+'\n')
        update('completed',work=str(out),timings=timings)
except Exception as error:update('failed',error=str(error));raise
