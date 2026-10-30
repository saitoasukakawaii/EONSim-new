"""SOLVER-02: fixed fluid/elastic FSI, solver_report only, first/later step statistics."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
from benchmark_nonlinear_setup import fields, ROOT

TIMERS = ['setup_seconds', 'schur_setup_seconds', 'solve_seconds', 'assembly_seconds',
          'ghost_seconds', 'linear_seconds', 'finalize_seconds', 'rss_max_bytes']


def parse(text, marker):
    reports = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith('solver_report ')]
    steps = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith(marker+'=')]
    if len(reports) != 10 or len(steps) != 10 or [int(s[marker]) for s in steps] != list(range(1,11)):
        raise RuntimeError('Expected exactly 10 accepted steps/reports; investigate retries or missing output')
    for report, step in zip(reports, steps):
        for key in TIMERS + ['linear_iterations', 'snes_reason', 'ksp_reason']:
            report[key] = float(report[key])
        if report['snes_reason'] <= 0 or report['ksp_reason'] <= 0:
            raise RuntimeError('Unconverged solve')
        report.update(step=int(step[marker]), residual=float(step['residual']), snes_iterations=int(step['snes_iterations']))
        if any(not math.isfinite(report[k]) for k in TIMERS+['residual']):
            raise RuntimeError('Nonfinite measurement')
    return reports


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--executable', type=Path, required=True)
    ap.add_argument('--mpiexec', required=True)
    ap.add_argument('--work', type=Path, required=True)
    a=ap.parse_args(); exe=a.executable.resolve(); work=a.work.resolve(); work.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    runs=[]; commands=[]
    def run(cmd, log):
        commands.append(cmd); start=time.perf_counter()
        with log.open('w') as f: subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        return time.perf_counter()-start,log.read_text()
    cases={}
    for name,relative,marker in [('fluid','cases/fluid/transient.yaml','fluid_step'),('elastic','cases/fsi/elastic.yaml','fsi_step')]:
        case=ROOT/relative;cases[name]=dict(path=relative,sha256=hashlib.sha256(case.read_bytes()).hexdigest(),yaml=case.read_text())
        for ranks in (1,2):
            part=work/f'{name}-part{ranks}'
            run([str(exe),'-case',str(case),'-prepare',str(part),'-parts',str(ranks)],work/f'{name}-prepare{ranks}.log')
            reference=None
            for repeat in range(3):
                stem=f'{name}-r{ranks}-n{repeat}';output=work/(stem+'.vtu')
                cmd=[a.mpiexec,'-n',str(ranks),str(exe),'-case',str(case),'-partition',str(part),'-output',str(output),'-solver_report']
                wall,text=run(cmd,work/(stem+'.log'));steps=parse(text,marker);current=fields(output)
                if reference is None:reference=current
                if len(reference)!=len(current) or any(abs(x-y)>1e-10*(1+abs(y)) for x,y in zip(current,reference)):raise RuntimeError('Repeated output differs')
                runs.append(dict(case=name,ranks=ranks,repeat=repeat,wall_seconds=wall,steps=steps,max_delta=max(abs(x-y) for x,y in zip(current,reference))))
                (work/'partial.json').write_text(json.dumps(runs,indent=2))
    summary=[]
    for name in cases:
        for ranks in (1,2):
            group=[r for r in runs if r['case']==name and r['ranks']==ranks]
            for phase in ('first','later'):
                # A later-step sample is the mean of steps 2–10 in one run; n remains three.
                metrics={}
                for key in TIMERS:
                    samples=[statistics.mean(s[key] for s in (r['steps'][:1] if phase=='first' else r['steps'][1:])) for r in group]
                    metrics[key]=dict(median=statistics.median(samples),minimum=min(samples),maximum=max(samples))
                summary.append(dict(case=name,ranks=ranks,phase=phase,metrics=metrics))
    result=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases=cases,commands=commands,runs=runs,summary=summary,cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),threads=1)
    (work/'results.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: 12 runs, 120 accepted steps; summaries in results.json')


if __name__=='__main__':main()
