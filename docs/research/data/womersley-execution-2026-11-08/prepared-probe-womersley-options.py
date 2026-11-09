"""Bounded option screen from one immutable physical checkpoint.

Run after the existing acceptance queue. This is not a scaling benchmark.
The chord option relies on the audited EONSim Schur path preassembling a valid
Jacobian before SNESSolve; it is not suitable for an arbitrary PETSc program.
"""
import argparse,fcntl,hashlib,json,math,os,re,shutil,signal,subprocess,sys,tempfile,time
from pathlib import Path

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
import study_rigid_tube as tube

OPTIONS={'standard':[],'coo':['-fluid_coo'],'chord':['-snes_lag_jacobian','-1'],
         'coo_chord':['-fluid_coo','-snes_lag_jacobian','-1']}
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--study',type=Path,required=True);p.add_argument('--restart-step',type=int,required=True)
p.add_argument('--work',type=Path,required=True);p.add_argument('--steps',type=int,default=3)
p.add_argument('--timeout',type=float,default=3600)
p.add_argument('--modes',nargs='+',choices=OPTIONS,default=list(OPTIONS))
a=p.parse_args()
if a.steps<1 or a.steps>10 or a.restart_step<2 or not 0<a.timeout<=7200:
    p.error('Invalid bounded probe size/time')
if 'standard' not in a.modes or len(set(a.modes))!=len(a.modes):p.error('Need one standard reference and unique modes')
base=Path('/home/tfblab633/EONSim-prod48-20261107')
prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
study=a.study.resolve();out=a.work.resolve()
definition=json.loads((study/'definition.json').read_text())
if not definition['schur']:raise ValueError('Chord probe requires the audited preassembled Schur path')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
if sha(study/'eonsim')!=definition['executable_sha256']:raise ValueError('Study executable changed')
if sha(study/'fluid.msh')!=(study/'mesh-sha256.txt').read_text().strip():raise ValueError('Study mesh changed')
matches=[]
for manifest in (study/'checkpoint').glob('generation_*/manifest'):
    words=manifest.read_text().split()
    if len(words)==5 and words[0]=='EONSim_checkpoint_v3' and int(words[2])==a.restart_step:
        matches.append((manifest.parent,words))
if len(matches)!=1:raise ValueError('Need one complete requested checkpoint generation')
source,manifest=matches[0];ranks=definition['ranks']
if int(manifest[1])!=ranks:raise ValueError('Checkpoint ranks differ')
dt=definition['period']/definition['steps_per_cycle']
if abs(float(manifest[3])-a.restart_step*dt)>1e-10:raise ValueError('Checkpoint time differs')
for rank in range(ranks):
    if not (source/f'state_rank{rank}.h5').is_file():raise ValueError('Incomplete rank state')
original=json.loads((study/'attempt-001/case.json').read_text())
if original.get('time_control') or original['time']['scheme']!='bdf2':raise ValueError('Only fixed-step BDF2 probe is defined')

env=os.environ.copy()
for name in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH'):
    env.pop(name,None)
env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
           OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
           OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1')
reports=[];physical={}
receipt=dict(source_study=str(study),definition=definition,source_step=a.restart_step,
    source_generation=source.name,source_checkpoint_hashes={path.name:sha(path) for path in source.iterdir() if path.is_file()},
    requested_steps=a.steps,modes=a.modes,field_tolerance=2e-9,
    helper_sha256=sha(Path(__file__)),runtime_prefix=str(prefix),
    scope='Single bounded option screen with unchanged residual/tolerances; no general speedup, scaling or physical accuracy claim',runs=reports)

def save():
    (out/'report.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')

with (base/'mpi-queue.lock').open('a') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Numerical queue is occupied; no probe started')
    out.mkdir()
    env['TMPDIR']=tempfile.mkdtemp(prefix='eonsim-option-probe-')
    shutil.copytree(source,out/'initial-checkpoint')
    for name,digest in receipt['source_checkpoint_hashes'].items():
        if sha(out/'initial-checkpoint'/name)!=digest:raise ValueError('Checkpoint copy differs')
    shutil.copy2(study/'eonsim',out/'eonsim')
    shutil.copy2(__file__,out/'original-probe.py')
    save()
    for mode in a.modes:
        directory=out/mode;directory.mkdir()
        cfg=json.loads(json.dumps(original));cfg['mesh']=str(study/'fluid.msh');cfg['output']='solution.vtu'
        cfg['fluid']['steps']=a.restart_step+a.steps
        (directory/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
        command=[str(out/'eonsim'),'-case','case.json','-restart',str(out/'initial-checkpoint'),
                 '-schur_pc','-ksp_gmres_restart','120','-ksp_max_it','2000','-solver_report',*OPTIONS[mode]]
        if ranks>1:
            command=[str(prefix/'bin/mpiexec'),'-n',str(ranks),*command,'-partition',str(study/'parts')]
        (directory/'command.json').write_text(json.dumps(dict(command=command,cwd=str(directory)),indent=2)+'\n')
        report=dict(mode=mode,command=command,state='running');reports.append(report);save()
        begin=time.perf_counter()
        with (directory/'solve.log').open('w') as log:
            process=subprocess.Popen(command,cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                code=process.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGINT)
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait()
                report.update(state='timeout',wall_seconds=time.perf_counter()-begin);save()
                if mode=='standard':raise RuntimeError('Baseline timed out; stop option screen')
                continue
        report.update(returncode=code,wall_seconds=time.perf_counter()-begin)
        text=(directory/'solve.log').read_text()
        try:
            if code or 'status=success' not in text:raise ValueError('Process did not succeed')
            rows=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith('fluid_step=')]
            stats=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith('solver_report ')]
            if len(rows)!=a.steps or len(stats)!=a.steps:raise ValueError('Unexpected accepted/report count')
            events=['report' if line.startswith('solver_report ') else 'step' for line in text.splitlines()
                    if line.startswith('solver_report ') or line.startswith('fluid_step=')]
            if events!=['report','step']*a.steps:raise ValueError('Reports are not associated with accepted steps')
            for step,row,s in zip(range(a.restart_step+1,a.restart_step+a.steps+1),rows,stats):
                if int(row['fluid_step'])!=step or abs(float(row['time'])-step*dt)>1e-10:raise ValueError('Accepted clock changed')
                if not math.isfinite(float(row['residual'])) or int(s['snes_reason'])<=0 or int(s['ksp_reason'])<=0:
                    raise ValueError('Nonconverged or nonfinite reported state')
            physical[mode]=tube.fields(directory,ranks)
            report.update(state='computed',accepted_steps=rows,solver_reports=stats,
                phase_seconds={name:sum(float(s[name]) for s in stats) for name in (
                    'solve_seconds','assembly_seconds','linear_seconds','schur_setup_seconds','finalize_seconds')},
                peak_rank_rss_bytes=max(float(s['peak_rss_max_bytes']) for s in stats))
        except Exception as error:
            report.update(state='failed',error=str(error));save()
            if mode=='standard':raise
        save();print(json.dumps({k:v for k,v in report.items() if k not in ('accepted_steps','solver_reports','command')}),flush=True)
    for report in reports:
        mode=report['mode']
        if mode not in physical:continue
        left,right=physical['standard'],physical[mode]
        if left.keys()!=right.keys():raise ValueError('Physical node set changed')
        error=max(abs(x-y) for n in left for x,y in zip(left[n],right[n]))
        report.update(maximum_field_difference=error,state='passed' if error<2e-9 else 'field_mismatch')
    receipt['complete']=True
    save();print(json.dumps(dict(work=str(out),results=[{k:v for k,v in r.items() if k not in (
        'command','accepted_steps','solver_reports')} for r in reports]),allow_nan=False),flush=True)
