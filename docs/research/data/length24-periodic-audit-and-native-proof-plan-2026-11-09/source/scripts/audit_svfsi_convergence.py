"""Conservative relative-convergence evidence for pinned exported svFSI runs.

PIC.f marks an equation ok at its iteration cap even when neither relative
criterion is met. Read every equation at every step; file output/exit zero is
not convergence. Require a printed ratio strictly below its input tolerance,
so a rounded value on the threshold is not accepted as proof. This check does
not infer an unavailable absolute residual from rounded normalized log values.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

PIN='7bdb74cdd517310d6bf32c0bb7d42072aeac8658'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def analyze(work,log,*,first_step=None,last_step=None):
    export=json.loads((work/'export.json').read_text())
    if export['svfsi_commit']!=PIN:raise ValueError('Unsupported reference version')
    for name,digest in export['files'].items():
        if sha(work/name)!=digest:raise ValueError('Reference input changed: '+name)
    inputs=(work/'svFSI.inp').read_text()
    from svfsi_restart_evidence import restart_evidence,setting
    restart=restart_evidence(work,export,inputs,log)
    steps=int(setting(inputs,'Number of time steps'))
    begin=restart['step']+1 if restart is not None else 1
    if first_step is None:first_step=begin
    if last_step is None:last_step=steps
    if (type(first_step) is not int or type(last_step) is not int or
            first_step!=begin or not first_step<=last_step<=steps):
        raise ValueError('Invalid reference segment range')
    names={'FSI':'FS','mesh':'MS','fluid':'NS'};equations={}
    for match in re.finditer(r'^Add equation: (\w+) \{\n(.*?)(?=^Add equation:|\Z)',inputs,re.M|re.S):
        name,block=match.groups()
        if name not in names or names[name] in equations:raise ValueError('Unsupported equation inventory')
        number=lambda key:float(re.search(r'^  '+key+r': (\S+)$',block,re.M)[1])
        equations[names[name]]=dict(tolerance=number('Tolerance'),maximum_iterations=int(number('Max iterations')),
            minimum_iterations=int(number('Min iterations')))
    expected={'FS','MS'} if export['mode']=='linear elastic pressure tube' else {'NS'}
    if set(equations)!=expected:raise ValueError('Incomplete reference equation input')
    text=re.sub(r'\x1b\[[0-9;]*m','',log.read_text())
    if re.search(r'\bERROR\b|MPI_INIT failed',text):raise ValueError('Reference error in log')
    pattern=re.compile(r'^\s*(FS|MS|NS)\s+(\d+)-(\d+)[s*]?\s+(\S+)\s+\[\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*\]',re.M)
    # Do not silently drop an unreadable later iteration and accept an earlier
    # converged-looking row. The equation/step prefix identifies numeric rows
    # separately from solver banners and headings in this pinned log format.
    for line in text.splitlines():
        if re.match(r'^\s*(FS|MS|NS)\s+\d+-',line) and pattern.match(line) is None:
            raise ValueError('Unreadable reference iteration row')
    final={};last_observed=0;rows=0
    for match in pattern.finditer(text):
        name,step,iteration,elapsed,db,local,initial,linear=match.groups()
        step=int(step);iteration=int(iteration)
        values=list(map(float,(elapsed,local,initial,linear)))
        # Pinned UTIL.f CPUT() is local seconds since midnight. OUTPUT.f's
        # diagnostic T = CPUT()-timeP(1) can become negative across midnight;
        # it is neither physical time nor a residual or a monotonic cost clock.
        # Keep it finite, while every printed residual ratio remains >=0.
        if (name not in equations or not last_observed<=step<=steps or step<begin or
                not all(math.isfinite(v) for v in values) or min(values[1:])<0):
            raise ValueError('Invalid reference iteration row')
        key=(step,name);previous=final.get(key,dict(iteration=0))
        if iteration!=previous['iteration']+1 or iteration>equations[name]['maximum_iterations']:
            raise ValueError('Missing, duplicate or out-of-range reference iteration')
        final[key]=dict(step=step,equation=name,iteration=iteration,relative_to_step=values[1],relative_to_initial=values[2])
        last_observed=step;rows+=1
    excluded={key:value for key,value in final.items() if key[0]>last_step}
    final={key:value for key,value in final.items() if key[0]<=last_step}
    if set(final)!={(step,name) for step in range(first_step,last_step+1) for name in equations}:
        raise ValueError('Missing or unexpected reference steps/equations')
    failures=[];cap_rows=0;maximum={name:0 for name in equations}
    worst_ratio={name:0. for name in equations}
    for (_,name),row in final.items():
        config=equations[name];ratio=min(row['relative_to_step'],row['relative_to_initial'])
        maximum[name]=max(maximum[name],row['iteration']);worst_ratio[name]=max(worst_ratio[name],ratio)
        cap_rows+=row['iteration']==config['maximum_iterations']
        if row['iteration']<config['minimum_iterations'] or not ratio<config['tolerance']:
            failures.append(dict(**row,tolerance=config['tolerance'],at_iteration_limit=row['iteration']==config['maximum_iterations']))
    return dict(svfsi_commit=PIN,steps=last_step-first_step+1,declared_steps=steps,
        first_step=first_step,last_step=last_step,restart=restart,
        excluded_tail=dict(final_equation_rows=len(excluded),last_observed_step=last_observed,
            iteration_rows=sum(row['iteration'] for row in excluded.values()),
            scope='Explicitly excluded tail; its completeness and convergence are not asserted'),
        equations=equations,iteration_rows=rows,
        final_equation_rows=len(final),iteration_limit_rows=cap_rows,maximum_iterations=maximum,
        maximum_final_relative_ratio=worst_ratio,failed_equation_steps=failures,passed=not failures,
        input_manifest_sha256=sha(work/'export.json'),log_sha256=sha(log),analysis_source_sha256=sha(Path(__file__)),
        scope='Printed relative convergence for every equation/step, not physical qualification; equality after rounding is unproven')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--first-step',type=int);parser.add_argument('--last-step',type=int)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    result=analyze(a.work.resolve(),a.log.resolve(),first_step=a.first_step,last_step=a.last_step)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='failed_equation_steps'}))
    if not result['passed']:raise SystemExit('Reference convergence is not established for every equation/step')
