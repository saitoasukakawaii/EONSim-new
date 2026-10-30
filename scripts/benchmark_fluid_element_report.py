"""Paired opt-in fluid element timing study; solver_report enabled in both modes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
from profile_multistep_setup import parse
from profile_schur_mesh import records, fields, delta, ROOT


def element_records(text, ranks, enabled):
    rows=records(text,'fluid_element_report')
    if not enabled:
        if rows: raise RuntimeError('Unexpected opt-out element report')
        return rows
    expected={(r,s) for r in range(ranks) for s in range(1,11)}
    if len(rows)!=len(expected) or {(int(x['rank']),int(x['step'])) for x in rows}!=expected:
        raise RuntimeError('Missing or duplicate rank/step reports')
    for row in rows:
        cells=int(row['local_cells'])
        if cells<=0: raise RuntimeError('Expected nonempty partition')
        for k in ('residual_elements','jacobian_elements'):
            if int(row[k])<=0 or int(row[k])%cells: raise RuntimeError('Invalid element count')
        for k in ('kernel_seconds','insert_seconds'):
            if not math.isfinite(float(row[k])) or float(row[k])<0: raise RuntimeError('Invalid element timer')
    return rows


def stats(values):
    return dict(median=statistics.median(values),minimum=min(values),maximum=max(values))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args()
    if a.repeats<3: p.error('At least three paired repetitions required')
    exe=a.executable.resolve();work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    case=ROOT/'cases/fluid/transient.yaml'
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    commands=[];runs=[];pairs=[];rank_reference=None
    def run(cmd,stem):
        commands.append(cmd);start=time.perf_counter()
        with (work/(stem+'.log')).open('w') as f:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,check=True)
        return time.perf_counter()-start,(work/(stem+'.log')).read_text()
    for ranks in (1,2,4):
        part=work/f'part{ranks}'
        run([str(exe),'-case',str(case),'-prepare',str(part),'-parts',str(ranks)],f'prepare{ranks}')
        reference=None;iteration_reference=None;count_reference=None
        # Warm up both modes; alternate pair order across measured repeats.
        for repeat in range(-1,a.repeats):
            pair={}
            for enabled in ((False,True) if repeat%2 else (True,False)):
                stem=f'r{ranks}-n{repeat}-on{int(enabled)}';out=work/(stem+'.vtu')
                cmd=[a.mpiexec,'-n',str(ranks),str(exe),'-case',str(case),'-partition',str(part),'-output',str(out),'-solver_report']
                if enabled:cmd.append('-fluid_element_report')
                wall,text=run(cmd,stem);steps=parse(text,'fluid_step');elements=element_records(text,ranks,enabled)
                current=fields(out,ranks)
                if reference is None:reference=current
                if rank_reference is None:rank_reference=current
                difference=delta(reference,current);rank_difference=delta(rank_reference,current)
                if difference>1e-12:raise RuntimeError('On/off or repeat physical outputs differ')
                iterations=[(s['snes_iterations'],s['linear_iterations']) for s in steps]
                if iteration_reference is None:iteration_reference=iterations
                if iterations!=iteration_reference:raise RuntimeError('Iteration trajectory changed')
                if enabled:
                    counts=[(e['rank'],e['step'],e['residual_elements'],e['jacobian_elements']) for e in elements]
                    if count_reference is None:count_reference=counts
                    if counts!=count_reference:raise RuntimeError('Element counts changed across repeats')
                row=dict(ranks=ranks,repeat=repeat,enabled=enabled,wall_seconds=wall,
                         solve_seconds=sum(s['solve_seconds'] for s in steps),max_delta=difference,
                         rank_delta=rank_difference,steps=steps,elements=elements)
                if enabled:
                    row['rank_totals']=[dict(rank=r,**{k:sum(float(e[k]) for e in elements if int(e['rank'])==r)
                        for k in ('kernel_seconds','insert_seconds')}) for r in range(ranks)]
                pair[enabled]=row
                if repeat>=0:runs.append(row)
            if repeat>=0:
                pairs.append(dict(ranks=ranks,repeat=repeat,**{k:pair[True][k]/pair[False][k]-1
                                 for k in ('wall_seconds','solve_seconds')}))
            print(ranks,repeat,'passed',flush=True)
    summary=[]
    for ranks in (1,2,4):
        summary.append(dict(ranks=ranks,paired_relative_change={k:stats([r[k] for r in pairs if r['ranks']==ranks])
                    for k in ('wall_seconds','solve_seconds')},modes=[dict(enabled=enabled,
                    **{k:stats([r[k] for r in runs if r['ranks']==ranks and r['enabled']==enabled])
                       for k in ('wall_seconds','solve_seconds')}) for enabled in (False,True)],
                    element_rank_max={k:stats([max(t[k] for t in r['rank_totals']) for r in runs if r['ranks']==ranks and r['enabled']])
                                      for k in ('kernel_seconds','insert_seconds')}))
    result=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),case_yaml=case.read_text(),
                case_sha256=hashlib.sha256(case.read_bytes()).hexdigest(),commands=commands,runs=runs,pairs=pairs,summary=summary,
                cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),threads=1)
    (work/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {len(runs)} measured runs, {len(pairs)} pairs; six warmup runs excluded')


if __name__=='__main__':main()
