"""Verify true correction residuals, MPI fields and failed Krylov attempts in the SI tube."""
import argparse
import csv
import json
import lzma
import math
from pathlib import Path
import re
import sys

import numpy as np

from arterial_ksp import PROFILE_MODES, digest, options
DATA=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(DATA/'fsi-smooth-load-2026-11-24'),str(DATA/'fsi-phase-costs-2026-11-24'),
              str(Path(__file__).resolve().parents[4]/'scripts')]
from audit_reflection import measured_ring_strains
from profile_case import core_placement
from study_rigid_tube import read_mesh


def parse(log,success,ranks):
    placement=core_placement(log,ranks)
    corrections=[]
    steps=[]
    reports=[]
    equation_rows={}
    reasons=[]
    failures=[]
    for line in log.splitlines():
        row=dict(re.findall(r'(\w+)=([^\s]+)',line))
        if line.startswith(('linear_residual ','linear_iteration_limit_residual ')):
            ordinal=int(row['solve'])
            if ordinal!=1+sum(r['step']==len(steps)+1 for r in corrections):raise ValueError('Noncontiguous Newton correction')
            norm,rhs=float(row['norm']),float(row['rhs_norm'])
            if not all(math.isfinite(v) and v>=0 for v in (norm,rhs)):raise ValueError('Invalid independently measured linear norm')
            corrections.append(dict(step=len(steps)+1,correction=ordinal,norm=norm,rhs=rhs,
                                    exhausted=line.startswith('linear_iteration_limit_'),field_rms={}))
        elif line.startswith(('linear_field_residual ','linear_iteration_limit_field_residual ')):
            rec=corrections[-1]
            if (rec['correction']!=int(row['solve']) or rec['exhausted']!=line.startswith('linear_iteration_limit_')
                    or row['name'] in rec['field_rms'] or float(row['residual_scale'])!=1.):
                raise ValueError('Field residual belongs to a different correction or scale')
            rms=float(row['rms'])
            if not math.isfinite(rms) or rms<0 or float(row['constraint_max'])!=0:
                raise ValueError('Invalid physical row RMS or nonzero eliminated constraint')
            rec['field_rms'][row['name']]=rms
        elif line.startswith('field_residual '):
            name=row['name']
            count=int(row['equation_rows'])
            if count<=0 or int(row['constraint_rows'])!=0 or equation_rows.setdefault(name,count)!=count:
                raise ValueError('The set of free equations changed during the 32-step tube')
        elif line.startswith('solver_report '):
            reports.append({k:int(row[k]) for k in ('dofs','linear_iterations','linear_completed','snes_reason','ksp_reason','domain_rejections')})
        elif line.startswith('fsi_step='):
            steps.append({k:float(row[k]) for k in ('fsi_step','time','evaluation_time','applied_pressure','residual','snes_iterations')})
        elif line.startswith('solver_node ') and row.get('rank')=='0' and row.get('path')=='root':
            reasons.append({k:row[k] for k in ('ksp','pc','ksp_reason_name','last_iterations','reported_norm','norm_type')})
        elif line.startswith(('linear_residual_unavailable','step_retry=','error=','EONSim rank 0:')):
            failures.append(line)
    if 'Option left:' in log:raise ValueError('An option was unused by this measured solver')
    failed=log.count('status=failed')
    signal=re.search(r'Caught signal number (\d+) [^:]+:',log)
    if log.count('status=success')!=int(success) or failed>ranks or (success and failed):
        raise ValueError('Process status disagrees with solver')
    if not success and not failed:
        if signal is None:
            raise ValueError('An unfinished solver produced neither a failure record nor a signal')
        failures.append(signal.group(0).rstrip(':'))
    if len(steps)!=len(reports) or (success and len(steps)!=32):
        raise ValueError('Missing step or Newton solver evidence')
    for i,(r,info) in enumerate(zip(steps,reports),1):
        stage=(i-1+(1 if i==1 else 2/3))/32
        load=80*stage**3*(10+stage*(-15+6*stage))
        if (r['fsi_step']!=i or abs(r['time']-i/32)>1e-14 or abs(r['evaluation_time']-stage)>1e-14 or
                abs(r['applied_pressure']-load)>1e-11 or min(info['snes_reason'],info['ksp_reason'])<=0 or info['domain_rejections'] or
                sum(c['step']==i and not c['exhausted'] for c in corrections)!=info['linear_completed']):
            raise ValueError('Mismatch in physical stage, load or number of converged corrections')
    if any(set(c['field_rms'])!={'velocity','pressure','structure','mesh'} for c in corrections):
        raise ValueError('Incomplete per-field residual')
    return dict(steps=steps,corrections=corrections,solver=reports,equation_rows=equation_rows,
                root_reasons=reasons,other_diagnostics=failures,placement=placement)


def profile_events(path,ranks):
    """Retain per-rank PETSc counters. A reduction event is already counted at each participant."""
    events={name:{} for name in ('summary','KSPSolve','KSPGMRESOrthog','VecDot','VecMDot','VecNorm')}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            name=row['Event Name']
            if row['Stage Name']!='Main Stage' or name not in events:
                continue
            rank=int(row['Rank'])
            values={key:float(row[key]) for key in ('Count','Num Reductions','Num Messages','Time')}
            if rank in events[name] or any(v<0 or not math.isfinite(v) for v in values.values()):
                raise ValueError('Duplicate rank or invalid PETSc log counters')
            events[name][rank]=values
    if any(set(found)!=set(range(ranks)) for found in events.values()):
        raise ValueError('Missing PETSc event/rank evidence')
    return {name:[found[i] for i in range(ranks)] for name,found in events.items()}


def fields_at(directory,ref,meshes,ranks):
    from study_hydrostatic_fsi import recovered_state
    peaks={}
    hashes={}
    left=[]
    for step in range(4,33,4):
        for solid,mesh in enumerate(meshes):
            stem=f'tube_step{step}'+('_solid' if solid else '')
            a=recovered_state(ref,stem,mesh,bool(solid),1)
            b=recovered_state(directory,stem,mesh,bool(solid),ranks)
            for j in range(ranks):
                file=stem+(f'_rank{j}' if ranks>1 else '')+'.vtu'
                hashes[file]=digest(directory/file)
            if a.keys()!=b.keys():raise ValueError('Physical grid differs from direct reference')
            for name in ('velocity','displacement') if solid else ('velocity','displacement','pressure'):
                first=np.array([getattr(a[k],name) for k in sorted(a)])
                second=np.array([getattr(b[k],name) for k in sorted(a)])
                key=('wall_' if solid else 'fluid_')+name
                peak=peaks.setdefault(key,dict(base=0.,difference=0.))
                peak['base']=max(peak['base'],float(np.max(abs(first))))
                peak['difference']=max(peak['difference'],float(np.max(abs(second-first))))
            if solid:
                _,areas=measured_ring_strains(mesh,b)
                left.append(100*areas[0])
    if any(v['base']<=0 for v in peaks.values()):raise ValueError('Missing direct physical signal')
    return dict(fields=peaks,end_areas_pct=left,vtu_sha256=hashes)


def pack(root,reference,exe,scripts):
    sys.path.append(str(scripts.resolve()))
    out=[]
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():continue
        case=reference/(directory.name+'-n32-arterial-volume')
        hashes={n:digest(case/n) for n in ('case.json','fluid.msh','solid.msh')}
        meshes=[read_mesh(case/n) for n in ('fluid.msh','solid.msh')]
        ref=json.loads((case/'result.json').read_text())
        if ref['problem']!='arterial' or ref['steps']!=32 or ref['model']!='volume':raise ValueError('Different direct trajectory')
        for receipt in sorted(directory.glob('r*-*/run.json')):
            d=json.loads(receipt.read_text())
            path=receipt.parent
            if (d['inputs']!=hashes or d['flags']!=options(d['mode']) or d['executable']!=digest(exe)
                    or d['log_sha256']!=digest(path/'solve.log')):
                raise ValueError('Changed measured input, binary, solver flags or history')
            if d['mode']=='preset':
                actual=digest(path/'arterial-fieldsplit.opts')
                if actual!=d['options_file_sha256'] or actual!=digest(Path(__file__).with_name('arterial-fieldsplit.opts')):
                    raise ValueError('Changed solver options file')
            log=(path/'solve.log').read_text()
            good=d['exit_code']==0
            solved=log.splitlines().count('status=success')==1
            if good and not solved:
                raise ValueError('Launcher returned success without an accepted solver status')
            d.update(grid=directory.name,direct_reference_sha256=digest(case/'result.json'),solver_completed=solved)
            d.update(parse(log,solved,d['ranks']))
            if d['mode'] in PROFILE_MODES:
                if 'profile_sha256' in d:
                    if d['profile_sha256']!=digest(path/'events.csv'):
                        raise ValueError('Changed PETSc profile')
                    d['profile']=profile_events(path/'events.csv',d['ranks'])
                elif good:
                    raise ValueError('Completed profiled solve has no PETSc event data')
            if solved:
                d.update(fields_at(path,case,meshes,d['ranks']))
                if abs(d['end_areas_pct'][-1]-100*ref['samples'][-1]['strains'][0])>1e-6:
                    raise ValueError('End sample differs from original VTU area')
            out.append(d)
    return out


def field_layouts(data):
    layouts={}
    for run in data:
        counts=run['equation_rows']
        if not counts:
            continue
        if set(counts)!={'mesh','pressure','structure','velocity'}:
            raise ValueError('Incomplete field layout')
        if any(step['dofs']!=sum(counts.values()) for step in run['solver']):
            raise ValueError('The fields do not partition the global operator')
        if layouts.setdefault(run['grid'],counts)!=counts:
            raise ValueError('MPI partitions disagree on the number of global equations')
    return layouts


def residual_shares(correction,counts):
    # The benchmark has unit row scales and only free equations. Squared block
    # norms therefore add to the squared full norm even after MPI repartitioning.
    norms={name:math.sqrt(count)*correction['field_rms'][name] for name,count in counts.items()}
    measured=correction['norm']
    if not math.isclose(math.hypot(*norms.values()),measured,rel_tol=2e-12,abs_tol=1e-300):
        raise ValueError('The distributed field RMS values do not reproduce the full residual')
    return {name:100*(norm/measured)**2 if measured else 0. for name,norm in norms.items()}


def table(data):
    layouts=field_layouts(data)
    rows=[]
    for d in data:
        cor=d['corrections']
        # All modes have a reference physical threshold. All iterative modes except the untouched default use it as the outer Krylov tolerance.
        ratios=[c['norm']/max(1e-23,1e-10*c['rhs']) for c in cor]
        if d['grid'] not in layouts:
            raise ValueError('Each mesh needs a completed step to establish its physical row counts')
        shares=[residual_shares(c,layouts[d['grid']]) for c in cor]
        worst=max(range(len(ratios)),key=ratios.__getitem__) if ratios else None
        dominant=max(shares[worst],key=shares[worst].get) if worst is not None else None
        fields=d.get('fields',{})
        delta=max((p['difference']/p['base'] for p in fields.values()),default=None)
        if delta is not None and delta>2e-6:raise ValueError('Accepted FSI fields differ from the direct reference')
        failed=[i for i,c in enumerate(cor) if c['exhausted']]
        modes=d['root_reasons']
        solve_events=d.get('profile',{}).get('KSPSolve',[])
        orthog_events=d.get('profile',{}).get('KSPGMRESOrthog',[])
        if solve_events and d['solver_completed'] and any(v['Count']!=len(cor) for v in solve_events):
            raise ValueError('PETSc outer solve count and true correction histories disagree')
        rows.append(dict(grid=d['grid'],ranks=d['ranks'],method=d['mode'],complete=d['exit_code']==0,
                         process_exit=d['exit_code'],solver_completed=d['solver_completed'],steps=len(d['steps']),
                         corrections=len(cor),within_comparison_target=sum(v<=1 for v in ratios),worst_true_norm_over_target=max(ratios,default=None),
                         worst_step=cor[worst]['step'] if worst is not None else None,
                         worst_correction=cor[worst]['correction'] if worst is not None else None,
                         worst_dominant_field=dominant,worst_field_pct_of_squared_norm=shares[worst][dominant] if dominant else None,
                         last_exhausted_true_norm_over_target=ratios[failed[-1]] if failed else None,
                         last_root_reason=modes[-1]['ksp_reason_name'] if modes else None,
                         failure=('nonzero process exit after all 32 steps and reported solver success'
                                  if d['solver_completed'] and d['exit_code']!=0 else
                                  next((msg for msg in d['other_diagnostics'] if msg.startswith(('EONSim rank 0:','Caught signal'))),None)),
                         last_root_iterations=int(modes[-1]['last_iterations']) if modes else None,
                         accepted_krylov_iterations=sum(r['linear_iterations'] for r in d['solver']),
                         max_nonlinear_residual=max((r['residual'] for r in d['steps']),default=None),
                         max_field_delta_over_own_peak=delta,left_end_area_pct=d['end_areas_pct'][-1] if fields else None,
                         linear_reductions_min_rank=min((e['Num Reductions'] for e in solve_events),default=None),
                         linear_reductions_max_rank=max((e['Num Reductions'] for e in solve_events),default=None),
                         orthogonalization_reductions_max_rank=max((e['Num Reductions'] for e in orthog_events),default=None),
                         wall_seconds=d['seconds']))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--runs',type=Path);group.add_argument('--archive',type=Path)
    p.add_argument('--reference',type=Path);p.add_argument('--executable',type=Path);p.add_argument('--reference-scripts',type=Path)
    p.add_argument('--write-archive',type=Path);p.add_argument('--csv',type=Path,required=True)
    a=p.parse_args()
    if a.runs and not all((a.reference,a.executable,a.reference_scripts)):p.error('Raw mode requires source cases, executable and field readers')
    data=pack(a.runs,a.reference,a.executable,a.reference_scripts) if a.runs else json.loads(lzma.decompress(a.archive.read_bytes()))
    rows=table(data)
    if not rows:raise ValueError('No completed attempts')
    with a.csv.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    if a.write_archive:a.write_archive.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
    print(len(rows),'attempts;',sum(r['complete'] for r in rows),'completed 32-step trajectories')


if __name__=='__main__':
    main()
