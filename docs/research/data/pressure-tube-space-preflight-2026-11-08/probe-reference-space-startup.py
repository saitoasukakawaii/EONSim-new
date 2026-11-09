"""Five coupled steps with a strictly tighter linear absolute floor."""
import fcntl,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'reference-space-startup-c49c69c';assert not out.exists()
cpu=20;env=os.environ.copy()
for key in list(env):
    if key in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH') or key.startswith(('OMPI_','PMIX_','PRTE_')):env.pop(key)
env.update(PATH='/usr/bin:/bin',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,command,cwd):
    command=list(map(str,command));print(json.dumps(dict(job=label,command=command,cpu=cpu)),flush=True)
    (out/(label+'-command.json')).write_text(json.dumps(dict(command=command,cwd=str(cwd),cpu=cpu),indent=2)+'\n')
    with (out/(label+'.log')).open('x') as stream:
        subprocess.run(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=600)
    assert not re.search(r'\bERROR\b',(out/(label+'.log')).read_text())
with (work/'elastic-space-reference.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{cpu})
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            argv=(proc/'cmdline').read_bytes().split(b'\0')
            if argv and Path(os.fsdecode(argv[0])).name in ('eonsim','svFSI'):assert cpu not in os.sched_getaffinity(int(proc.name))
        except (FileNotFoundError,ProcessLookupError):pass
    out.mkdir();shutil.copy2(__file__,out/'original-controller.py');source=out/'source';hashes={}
    for name in ('scripts/export_svfsi_tube.py','scripts/audit_svfsi_convergence.py','scripts/study_rigid_tube.py','cases/fsi/generate_tube.py'):
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,p);hashes[name]=sha(p)
    (out/'provenance.json').write_text(json.dumps(dict(source_head='c49c69c',modified_source_hashes=hashes,
        reference_sha256=sha(work/'reference/build/bin/svFSI'),linear_atol=1e-26,unchanged_nonlinear_tolerance=1e-10,
        scope='Actual five-step coupled convergence probe; not periodic or spatial qualification'),indent=2)+'\n')
    results={}
    for ramp in (16,):
        label='ramp'+str(ramp);case_dir=out/(label+'-case');case_dir.mkdir();origin=work/'elastic-s12-l1-n200-probe-c49c69c/case'
        for name in ('fluid.msh','solid.msh','geometry.json'):shutil.copy2(origin/name,case_dir/name)
        cfg=json.loads((origin/'case.json').read_text());cfg['fsi']['steps']=5
        cfg['fsi']['pressure_time']['ramp_time']=ramp*cfg['fsi']['pressure_time']['period']
        case=case_dir/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n');reference=out/label
        run(label+'-export',[sys.executable,source/'scripts/export_svfsi_tube.py','--case',case,
            '--output',reference,'--stage-pressure','--general-pressure','--tight-linear-atol','1e-26'],root)
        run(label+'-solve',[work/'reference/build/bin/svFSI','svFSI.inp'],reference)
        run(label+'-audit',[sys.executable,source/'scripts/audit_svfsi_convergence.py','--work',reference,
            '--log',out/(label+'-solve.log'),'--output',out/(label+'-convergence.json')],root)
        results[label]=json.loads((out/(label+'-convergence.json')).read_text())
    (out/'summary.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results),flush=True)
