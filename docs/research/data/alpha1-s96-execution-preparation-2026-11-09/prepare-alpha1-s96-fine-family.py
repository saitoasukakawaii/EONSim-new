"""Prepare, but never launch, a concrete alpha1 family after the real raw review.

Preflight is read-only and may run while the screen is waiting. Preparation
requires actual eligible screen/review results and preserves the failed coarse
flow diagnostic. A separate reviewed execution controller remains necessary.
"""
import argparse,ast,hashlib,json,os,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];w=Path('/home/tfblab633/EONSim-prod48-20261107');d=Path('/mnt/d/EONSim-prod48-20261107')
screen=d/'alpha1-s96-fine-execution-screen-a341bc6';review=w/'alpha1-s96-fine-execution-review-a341bc6'
coarse=d/'womersley-a1-s96-r8-a8-l0-n400-native32-fcc2956';cc=w/'alpha1-s96-coarse-n400-fcc2956'
previous=w/'s96-n400-qualified-family-a3e1c87';out=w/'alpha1-s96-fine-family-plan-b0fd881'
runtime=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
ap=argparse.ArgumentParser();ap.add_argument('action',choices=('preflight','prepare'));args=ap.parse_args()
states={name:read(w/(name+'-current.json')) for name in ('alpha1-native200-lu32-recovery','alpha1-s96-coarse-n400','alpha1-s96-fine-execution-screen','alpha1-s96-fine-execution-review')}
pending={name:s['state'] for name,s in states.items() if s['state']!='completed'}
if pending:
 print(json.dumps(dict(ready=False,pending=pending,prepared=False,adopted=False)))
 if args.action=='prepare':raise SystemExit('Preparation requires actual completed eligible screen and separate raw review')
 raise SystemExit(0)
report=read(screen/'report.json');raw=read(review/'review.json');sd=read(screen/'definition.json')
assert report['passed'] and report['eligible'] and not report['adopted']
assert raw['passed'] and raw['eligible'] and not raw['adopted']
assert raw['definition_sha256']==sha(screen/'definition.json') and raw['report_sha256']==sha(screen/'report.json')
selected=raw['selected'];assert selected==report['selected'] and selected in ('native32','four32')
assert raw['candidate_sha256']==sd['candidate_sha256']==sha(screen/'eonsim')=='60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07'
assert raw['datasets_reopened']==1440 and raw['states_per_mode']==32
assert raw['raw_state_hashes']==report['raw_state_hashes'] and raw['comparisons']==report['comparisons']
assert sha(screen/'controller.py')==sd['controller_sha256']
assert sha(review/'controller.py')==raw['controller_sha256']
for name,z in sd['source_hashes'].items():assert sha(screen/'source'/name)==z
assert sd['alpha']==1 and sd['level']==1 and sd['seed']==[96,8,8] and sd['steps_per_cycle']==400
assert sd['node_limit']==2e-9 and sd['mass_limit']==1e-8 and sd['minimum_cost_reduction']==.1
seconds=raw['seconds'];assert all(seconds[selected]<=.9*seconds[k] for k in seconds if k!=selected)
for name in ('four8','native32','four32'):
 r=read(screen/(name+'.resource.json'))
 assert r==report['runs'][name]['resource'] and r['returncode']==0 and not r['remaining_scope_members']
 assert r['memory_max_bytes']==6*1024**3 and r['memory_swap_max_bytes']==0
 assert all(int(x.split()[1])==0 for x in r['memory_events'].splitlines())
r=read(review/'review.resource.json');assert r['returncode']==0 and not r['remaining_scope_members']
assert r['memory_max_bytes']==2*1024**3 and r['memory_swap_max_bytes']==0
assert all(int(x.split()[1])==0 for x in r['memory_events'].splitlines())
cd=read(coarse/'definition.json');ca=read(cc/'analysis.json')
assert read(coarse/'receipt.json')['step']==2400 and cd['alpha']==1 and cd['steps_per_cycle']==cd['phases']==400
assert cd['level']==0 and cd['ranks']==1 and cd['seed']==[96,8,8] and cd['warmup']==2
assert cd['executable_sha256']==sd['candidate_sha256']
assert ca['preliminary_gates']['periodic'] and ca['preliminary_gates']['global_mass']
assert ca['preliminary_gates']['flow_amplitude'] is False
print(json.dumps(dict(ready=True,selected=selected,prepared=False,adopted=False,coarse_flow_failure_preserved=True)))
if args.action=='preflight':raise SystemExit(0)
assert not out.exists()
ranks=1 if selected=='native32' else 4;cpus=[0] if ranks==1 else list(range(8))
fine=d/('womersley-a1-s96-r8-a8-l1-n400-'+selected+'-b0fd881')
time_control=d/('womersley-a1-s96-r8-a8-l1-n800-'+selected+'-b0fd881')
assert not fine.exists() and not time_control.exists()
assert shutil.disk_usage(d).free>80*1024**3
out.mkdir();shutil.copy2(__file__,out/'preparer.py')
shutil.copytree(screen/'source',out/'source',ignore=shutil.ignore_patterns('__pycache__'))
for name in ('eonsim','bounded_cgroup_job_6g.py','rank-guard.py'):shutil.copy2(screen/name,out/name)
assert sha(out/'bounded_cgroup_job_6g.py')==sd['cap_sha256'] and sha(out/'rank-guard.py')==sd['guard_sha256']
snapshots={'screen-definition.json':screen/'definition.json','screen-report.json':screen/'report.json','screen-raw-review.json':review/'review.json',
 'middle-analysis.json':cc/'analysis.json','coarse-tail-n400.json':cc/'tail-n400.json','coarse-completion.json':cc/'completion.json'}
for name,p in snapshots.items():shutil.copy2(p,out/name);assert sha(p)==sha(out/name)
wrapper=out/'mpiexec-fixed'
wrapper.write_text('#!/usr/bin/python3\nimport os,sys\na=sys.argv[1:];assert a[:2]==["-n","4"]\n'
 'p='+repr(str(runtime/'bin/mpiexec'))+'\n'
 'os.execv(p,[p,"--bind-to","none","--oversubscribe",*a[:2],"/usr/bin/python3",'+repr(str(out/'rank-guard.py'))+',"four",*a[2:]])\n')
wrapper.chmod(0o755)
guard=out/'workflow-guard.py'
guard.write_text('import os,sys,time\nfrom pathlib import Path\nos.sched_setaffinity(0,'+repr(set(cpus))+')\n'
 'g=Path("/sys/fs/cgroup")/Path("/proc/self/cgroup").read_text().strip().split("::",1)[1].lstrip("/")\n'
 'end=time.monotonic()+5\nwhile (g/"memory.max").read_text().strip()=="max" and time.monotonic()<end:time.sleep(.05)\n'
 'assert int((g/"memory.max").read_text())==6*1024**3 and int((g/"memory.swap.max").read_text())==0\n'
 'os.execv(sys.argv[1],sys.argv[1:])\n')
kernel=(previous/'budget-kernel.py').read_text()
assert sha(previous/'budget-kernel.py')=='a7e775f3d2896ba1b7f65f963aa25055bcea5de215141651710730119650d2da'
ast.parse(kernel);(out/'budget-kernel.py').write_text(kernel)
assert (out/'budget-kernel.py').read_bytes()==(previous/'budget-kernel.py').read_bytes()
header='import json,math,sys\nfrom pathlib import Path\nimport numpy as np\nout=Path(__file__).resolve().parent\nsys.path.insert(0,str(out/"source/scripts"))\nfrom analyze_womersley import Study\nstudy=Path('+repr(str(fine))+')\ntarget=Path('+repr(str(time_control))+')\ndefinition=json.loads((study/"definition.json").read_text())\nalpha=1\ndef dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+"\\n")\n'
(out/'budget.py').write_text(header+kernel)
source=out/'source';commands={}
for n,target in ((400,fine),(800,time_control)):
 commands[f'fine-n{n}']=[sys.executable,source/'scripts/study_womersley.py','--executable',out/'eonsim','--work',target,
  '--seed','96','8','8','--level','1','--alpha','1','--steps-per-cycle',str(n),'--phases',str(n),'--warmup','2','--cycles','6',
  '--cycles-per-solve','1','--ranks',str(ranks),'--mumps','--lu-reuse-window','32','--chord','--timeout','86400']
 if ranks==4:commands[f'fine-n{n}']+=['--mpiexec',wrapper]
 commands[f'n{n}-analysis']=[sys.executable,source/'scripts/analyze_womersley.py','--work',target,'--output',out/f'n{n}-analysis.json']
 commands[f'tail-n{n}']=[sys.executable,source/'scripts/compare_womersley.py','--coarse',target,'--fine',target,'--coarse-cycle','5','--fine-cycle','6','--output',out/f'tail-n{n}.json']
 if n==400:commands['space-n400']=[sys.executable,source/'scripts/compare_womersley.py','--coarse',coarse,'--fine',fine,'--coarse-cycle','6','--fine-cycle','6','--output',out/'space-n400.json']
commands['time-n400-n800']=[sys.executable,source/'scripts/compare_womersley.py','--coarse',fine,'--fine',time_control,'--coarse-cycle','6','--fine-cycle','6','--output',out/'time-n400-n800.json']
commands['budget']=[sys.executable,out/'budget.py']
dump(out/'commands.json',{label:list(map(str,command)) for label,command in commands.items()})
for p in (out/'budget.py',guard,wrapper):compile(p.read_text(),str(p),'exec')
dump(out/'definition.json',dict(base='b0fd881a4ad3549e3a9532a89bc1595221356e1b',prepared=True,adopted=False,selected=selected,
 preparer_sha256=sha(out/'preparer.py'),binary_sha256=sha(out/'eonsim'),source_hashes=sd['source_hashes'],
 file_hashes={name:sha(out/name) for name in ('commands.json','budget.py','budget-kernel.py','bounded_cgroup_job_6g.py','rank-guard.py','mpiexec-fixed','workflow-guard.py')},
 snapshots={name:dict(path=str(p),sha256=sha(p)) for name,p in snapshots.items()},
 input_hashes={str(p):sha(p) for p in (coarse/'definition.json',coarse/'receipt.json',coarse/'fluid.msh',screen/'fluid.msh')},
 expected_fine_mesh_sha256=sd['mesh_sha256'],coarse_flow_amplitude_failed=True,
 coarse=str(coarse),fine=str(fine),time_control=str(time_control),ranks=ranks,cpus=cpus,window=32,
 steps_per_cycle=[400,400,800],phases=[400,400,800],cycles=6,warmup=2,memory_max_bytes=6*1024**3,swap_max_bytes=0,
 admission_bytes=22*1024**3,global_floor_bytes=8*1024**3,required_locks=['womersley-direct-memory.lock','mpi-queue.lock'],
 independent_run_review_required=True,numerical_kernel_byte_identical=True,
 runtime_checks_required=['exact planned source/input/command/review hashes','global resource locks in declared order',
  'no active solver on CPU0..7','22GiB available admission and8GiB floor','6GiB/swap0 child guard',
  'positive convergence and complete cycle receipts','all owned groups empty with zero memory events',
  'generated fine mesh exactly equals screened mesh','same fine/time definition except400/800 phase resolution'],
 scope='Concrete preparation only after real eligible alpha1S96 startup screen and separate1440-dataset raw review. Fresh fineN400/N800 with selected measured policy, same60eb/source/physics, coarseQfailure preserved. Exact prior N400-target budget body, alpha1 wrapper only. No execution controller or numerical process is launched; separate review must bind this definition before any future adoption.'))
print(json.dumps(dict(prepared=True,adopted=False,definition=str(out/'definition.json'),definition_sha256=sha(out/'definition.json'))))
