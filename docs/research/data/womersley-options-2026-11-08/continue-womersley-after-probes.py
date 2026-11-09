"""One sequential continuation after the explicit fine-state option screen."""
import fcntl,hashlib,json,math,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
status=work/'womersley-continuation-2eabb47.json'
if status.exists():raise ValueError('Continuation controller already has a status record')
out=work/'womersley-continuation-2eabb47';out.mkdir()
shutil.copy2(__file__,out/'original-controller.py')
env=os.environ.copy()
for key in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH'):
    env.pop(key,None)
env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR=tempfile.mkdtemp(prefix='eonsim-followup-'))
def update(state,**kwargs):
    data=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kwargs)
    temp=status.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(status)
    print(json.dumps(data),flush=True)
def run(name,args,timeout=86400):
    command=[sys.executable,*map(str,args)]
    update('running',job=name,command=command)
    (out/(name+'-command.json')).write_text(json.dumps(command,indent=2)+'\n')
    with (out/(name+'.log')).open('w') as log:
        subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
try:
    update('queued',waiting_for='fine lag=-2 probe and mpi-queue.lock')
    with (work/'mpi-queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        report=work/'option-probe-fine-lag2-865b101/report.json'
        receipt=json.loads(report.read_text())
        if not receipt.get('complete'):raise ValueError('Fine option screen did not complete')
        modes={r['mode']:r for r in receipt['runs']}
        if modes['standard']['state']!='passed':raise ValueError('Fine baseline failed')
        chord=modes['chord']
        selected='chord' if (chord['state']=='passed' and
            chord['wall_seconds']<.95*modes['standard']['wall_seconds']) else 'standard'
        (out/'selection.json').write_text(json.dumps(dict(selected=selected,
            rule='Passed same-state 3-step field/solver check and at least5% lower observed wall time; otherwise standard',
            fine_probe_sha256=hashlib.sha256(report.read_bytes()).hexdigest()),indent=2)+'\n')
        # Now that the optional tau-time parameter passed Debug and Release,
        # isolate its effect at the existing coarse N200 resolution.
        frozen=work/'eonsim-2189a8c'
        accepted=json.loads((work/'acceptance-2189a8c/binary.json').read_text())
        if hashlib.sha256(frozen.read_bytes()).hexdigest()!=accepted['executable_sha256']:
            raise ValueError('Accepted diagnostic executable changed')
        tau_work=work/'womersley-a2-s48-l0-n200-fixed-time-n100'
        run('coarse-tau-time',[root/'scripts/study_womersley.py','--executable',frozen,
            '--work',tau_work,'--alpha','2','--steps-per-cycle','200','--phases','100',
            '--warmup','2','--cycles','5','--ranks','4','--schur',
            '--tau-time-scale',2*(2*math.pi/4/100)/3,'--timeout','86400'])
        source=work/'womersley-a2-s48-l2-n200'
        target=work/('womersley-a2-s48-l2-n200-'+selected+'-m200')
        run('fork-fine',[root/'build/prod48-20261107/fork-womersley-execution.py',
            '--study',source,'--probe',report,'--mode',selected,'--work',target,'--phases','200'],600)
        run('fine-continuation',[root/'scripts/study_womersley.py','--executable',source/'eonsim',
            '--work',target,'--seed','48','4','8','--level','2','--alpha','2',
            '--steps-per-cycle','200','--phases','200','--warmup','2','--cycles','5',
            '--ranks','4','--schur',*(['--chord'] if selected=='chord' else []),
            '--resume','--timeout','86400'],172800)
        update('completed',fine_study=str(target),coarse_tau_study=str(tau_work),
            scope='Numerical endpoints reached; field analysis and full physical qualification still required')
except Exception as error:
    update('failed',error=str(error));raise
