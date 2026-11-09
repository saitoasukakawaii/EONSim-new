"""Continue the original S24 budgets with matched analyzers and unchanged arithmetic."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
work=Path('/home/tfblab633/EONSim-prod48-20261107')
storage=Path('/mnt/d/EONSim-prod48-20261107')
handoff=work/'reference-fine-ilut-handoff-midnight2-a0a4675'
out=work/'elastic-s24-midnight2-budgets-a0a4675'
status=work/'elastic-s24-midnight2-budgets-current.json'
source=out/'source'
read=lambda p:json.loads(p.read_text())

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def update(state,**kw):
    v=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    pending=status.with_suffix('.tmp');dump(pending,v);pending.replace(status);print(json.dumps(v),flush=True)

def plans():
    result={}
    for solver in ('eonsim','svfsi'):
        fine=storage/('elastic-s24-l1-n400-sample11600-recovery-abec003' if solver=='eonsim' else 'reference-s24-l1-n400-ilut-m4000-midnight2-a0a4675')
        result[solver]=dict(coarse=storage/'elastic-s24-l0-n400-ramp16-c32',time=storage/'elastic-s24-l1-n200-ramp16-c32',fine=fine,
            statuses=[work/f'elastic-budget-s24-l0-n400-{solver}-current.json',work/f'elastic-budget-s24-l1-n200-{solver}-current.json',
                work/('elastic-s24-sample11600-recovery-current.json' if solver=='eonsim' else 'reference-fine-ilut-continuation-midnight2-current.json')])
    return result

def unchanged_report(previous,matched):
    # The analyzer gained explicit restart-chain metadata. Every physical
    # quantity and every pre-existing convergence criterion must be identical.
    omit={'analysis_script_sha256','reference_convergence'}
    assert {k:v for k,v in previous.items() if k not in omit}=={k:v for k,v in matched.items() if k not in omit}
    if previous.get('reference_convergence') is not None:
        for key in ('steps','equations','final_equation_rows','iteration_rows','iteration_limit_rows',
                    'maximum_iterations','maximum_final_relative_ratio','failed_equation_steps','passed','input_manifest_sha256','log_sha256'):
            assert previous['reference_convergence'][key]==matched['reference_convergence'][key],key

def matched_audit(solver,role,path,directory):
    old=path/(solver+'-audit.json');before=sha(old);previous=read(old)
    expected=sha(source/'scripts/audit_pressure_tube.py')
    target=directory/(solver+'-'+role+'-audit.json')
    if previous['analysis_script_sha256']==expected:
        shutil.copy2(old,target)
        equivalence=dict(reused_same_analyzer=True,original_sha256=before,matched_sha256=sha(target))
    else:
        command=[sys.executable,source/'scripts/audit_pressure_tube.py','--case',path/'case.json',
            '--work',path if solver=='eonsim' else path/'reference','--first-step',str(previous['first_step']),'--output',target]
        if solver=='svfsi':command+=['--svfsi','--reference-log',path/'svfsi.log']
        with (directory/(solver+'-'+role+'-audit.log')).open('xb') as stream:
            subprocess.run(list(map(str,command)),cwd=source,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=7200)
        matched=read(target);unchanged_report(previous,matched)
        equivalence=dict(reused_same_analyzer=False,all_physical_report_values_identical=True,
            original_sha256=before,matched_sha256=sha(target),original_analyzer=previous['analysis_script_sha256'],matched_analyzer=expected)
    assert sha(old)==before and read(target)['analysis_script_sha256']==expected
    dump(directory/(solver+'-'+role+'-equivalence.json'),equivalence)
    return target

def worker(solver):
    group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
    deadline=time.monotonic()+5
    while (group/'memory.max').read_text().strip()=='max' and time.monotonic()<deadline:time.sleep(.05)
    assert int((group/'memory.max').read_text())==2*1024**3 and int((group/'memory.swap.max').read_text())==0
    import numpy as np
    spec=importlib.util.spec_from_file_location('fields',source/'build/prod48-20261107/compare-pressure-fields.py')
    fields=importlib.util.module_from_spec(spec);spec.loader.exec_module(fields)
    if solver=='cross':
        audits={s:out/'matched-audits'/s/(s+'-fine-audit.json') for s in ('eonsim','svfsi')}
        spec=importlib.util.spec_from_file_location('observables',source/'build/prod48-20261107/compare-pressure-audits.py')
        obs=importlib.util.module_from_spec(spec);spec.loader.exec_module(obs)
        dump(out/'cross-code-observables.json',obs.compare(read(audits['eonsim']),read(audits['svfsi'])))
        study={s:fields.Study(plans()[s]['fine']/'case.json',plans()[s]['fine'] if s=='eonsim' else plans()[s]['fine']/'reference',audits[s]) for s in audits}
        dump(out/'cross-code-fields.json',fields.compare(study['eonsim'],study['svfsi'],32,32,400))
        return
    plan=plans()[solver];directory=out/'matched-audits'/solver;directory.mkdir(parents=True)
    audits={role:matched_audit(solver,role,plan[role],directory) for role in ('coarse','time','fine')}
    def study(s,path):
        role=next(k for k in audits if path==plan[k])
        return fields.Study(path/'case.json',path if s=='eonsim' else path/'reference',audits[role])
    definition=read(handoff/'definition.json')
    kernel=source/'build/prod48-20261107/s24-budget-kernel.py'
    assert sha(kernel)==definition['source_hashes']['build/prod48-20261107/s24-budget-kernel.py']
    context=dict(out=out,dump=dump,study=study,fields=fields,np=np,math=math,
                 EXPECTED_ANALYZER=sha(source/'scripts/audit_pressure_tube.py'))
    exec(compile(kernel.read_text(),str(kernel),'exec'),context)
    receipts={p.name:read(p) for p in plan['statuses']};assert all(v['state']=='completed' for v in receipts.values())
    context['analyze'](solver,plan,receipts)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker',choices=['eonsim','svfsi','cross']);args=parser.parse_args()
    if args.worker:worker(args.worker);return
    assert not out.exists() and not status.exists()
    definition=read(handoff/'definition.json')
    assert sha(Path(__file__))==definition['source_hashes']['build/prod48-20261107/analyze-elastic-s24-midnight2-budgets.py']
    out.mkdir();shutil.copy2(__file__,out/'controller.py');shutil.copytree(handoff/'source',source,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(handoff/'bounded_cgroup_job_2g.py',out/'bounded_cgroup_job_2g.py')
    dump(out/'definition.json',dict(handoff_definition_sha256=sha(handoff/'definition.json'),
        controller_sha256=sha(out/'controller.py'),source_hashes=definition['source_hashes'],
        numerical_budget_tail_sha256=definition['numerical_budget_tail_sha256'],
        scope='Same independent error-budget arithmetic, limits, fields and exact phases. Re-audit unchanged reports with matched frozen analyzer, preserve every physical value. New fine reference routing only; no physical qualification inferred from execution.'))
    spec=importlib.util.spec_from_file_location('cap',out/'bounded_cgroup_job_2g.py');cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    try:
        update('waiting_for_handoff_adoption')
        while not (handoff/'adoption.json').exists():
            producer=work/'reference-fine-ilut-continuation-midnight2-current.json'
            if producer.exists() and read(producer)['state']=='failed':raise RuntimeError('Handoff failed before adoption')
            time.sleep(5)
        pending=set(plans());complete={};update('waiting_for_producers',pending=sorted(pending))
        while pending:
            progressed=False
            for solver in sorted(pending):
                receipts={p.name:read(p) for p in plans()[solver]['statuses']}
                if any(v['state']=='failed' for v in receipts.values()):raise RuntimeError('A required producer failed: '+solver)
                if not all(v['state']=='completed' for v in receipts.values()):continue
                with (work/'elastic-budget-analysis.lock').open('a') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{19})
                    while cap.available()<=10*1024**3:time.sleep(5)
                    update('analyzing',solver=solver)
                    receipt=cap.run([sys.executable,out/'controller.py','--worker',solver],source,out/(solver+'.log'),dict(os.environ),
                        f'eonsim-ilut-budget-{solver}-{os.getpid()}.scope',14400)
                    assert receipt['returncode']==0 and not receipt['remaining_scope_members']
                    assert all(int(line.split()[1])==0 for line in receipt['memory_events'].splitlines())
                    complete[solver]=read(out/solver/'budget.json')
                pending.remove(solver);progressed=True;dump(out/'partial-summary.json',complete)
                update('waiting_for_producers' if pending else 'waiting_for_cross_comparison',pending=sorted(pending),completed=sorted(complete))
            if not progressed:time.sleep(15)
        with (work/'elastic-budget-analysis.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);os.sched_setaffinity(0,{19})
            while cap.available()<=10*1024**3:time.sleep(5)
            update('comparing_fine_pair')
            receipt=cap.run([sys.executable,out/'controller.py','--worker','cross'],source,out/'cross.log',dict(os.environ),
                f'eonsim-ilut-budget-cross-{os.getpid()}.scope',14400)
            assert receipt['returncode']==0 and not receipt['remaining_scope_members']
            assert all(int(line.split()[1])==0 for line in receipt['memory_events'].splitlines())
        dump(out/'summary.json',dict(solvers=complete,both_budget_gates_passed=all(v['passed'] for v in complete.values()),
            full_production_qualification=False,observable_comparison=read(out/'cross-code-observables.json')))
        update('completed',full_production_qualification=False)
    except BaseException as error:
        dump(out/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise

if __name__=='__main__':main()
