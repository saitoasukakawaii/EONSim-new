"""Matched direct/ASM trials and separately timed native/EONSim loop diagnostics."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
from paired_tube import DT, arterial_options, digest, physical, read_mesh, run, save, wall
from study_hydrostatic_fsi import recovered_state
import benchmark_fsi_assembly as assembly


def compare_states(first,second,steps,meshes,solver='eon',ranks=(1,1)):
    maximum=0.
    for step in range(4,steps+1,4):
        if solver=='svfsi':
            native=[wall.external_fields(folder/'1-procs'/f'result_{step:03d}.vtu',meshes) for folder in (first,second)]
        for i,suffix in enumerate(('','_solid')):
            name=f'tube_step{step}'+suffix
            states=([recovered_state(folder,name,meshes[i],bool(i),n) for folder,n in zip((first,second),ranks)]
                    if solver=='eon' else [fields[i] for fields in native])
            if states[0].keys()!=states[1].keys():raise ValueError('Field node coverage differs')
            for node,a in states[0].items():
                b=states[1][node]
                maximum=max(maximum,abs(a.pressure-b.pressure),*(abs(x-y) for x,y in zip(a.velocity+a.displacement,b.velocity+b.displacement)))
    if maximum>2e-9:raise ValueError(f'Field mismatch {maximum}')
    return maximum


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for k in ('gate','root','eon','native'):cli.add_argument('--'+k,required=True,type=Path)
    a=cli.parse_args(); root=a.root.resolve(); gate=a.gate.resolve()
    receipt=json.loads((gate/'summary.json').read_text());steps=receipt['steps']
    if not receipt['passed'] or receipt['ranks']!=1 or receipt['eon_linear']!='asm' or len(os.sched_getaffinity(0))!=1 or not os.getenv('SLURM_JOB_ID'):
        cli.error('requires validated single-core physical window and single-core Slurm allocation')
    src=gate/'prepared';build=json.loads((a.native.parent/'build.json').read_text())
    if digest(a.eon)!=receipt['binaries']['eon'] or build['source_binary_sha256']!=receipt['binaries']['svfsi'] or digest(a.native)!=build['binary_sha256']:
        raise ValueError('Input gate and binaries belong to different builds')
    if {path:digest(src/path) for path in receipt['inputs']}!=receipt['inputs']:
        raise ValueError('Prepared input differs from physical gate')
    root.mkdir(parents=True,exist_ok=False);meshes=[read_mesh(src/'eon'/(s+'.msh')) for s in ('fluid','solid')]
    results=dict(steps=steps,slurm=os.environ['SLURM_JOB_ID'],source_input=receipt['inputs'],binary=digest(a.eon),native_diagnostic_binary=digest(a.native),runs=[],passed=False)
    for repeat in range(4):
        trial=root/str(repeat);trial.mkdir()
        for mode in (('direct','asm') if repeat%2==0 else ('asm','direct')):
            folder=trial/mode;shutil.copytree(src/'eon',folder)
            command=[str(a.eon.resolve()),'-case','case.json',*arterial_options(mode)]
            if mode=='asm':command+=['-nonlinear_true_residual','true']
            row=dict(repeat=repeat,mode=mode,kind='timed' if repeat else 'warmup');results['runs'].append(row)
            try:
                run(folder,command,row,180);data=physical(folder,'eon',meshes,steps)
                if data['circuit_error']>2e-6:raise ValueError('RCR check')
                row['max_accepted_snes_residual']=data['convergence']['maximum_accepted_residual']
            finally:save(root/'summary.json',results)
        results.setdefault('field_differences',[]).append(compare_states(trial/'direct',trial/'asm',steps,meshes))
        histories=[assembly.history(trial/mode/'tube.csv',steps,DT) for mode in ('direct','asm')]
        results.setdefault('history_differences',[]).append(assembly.compare_history(*histories))
    results['medians']={m:statistics.median(r['T_job'] for r in results['runs'] if r['repeat'] and r['mode']==m) for m in ('direct','asm')}
    if steps in (32,100):
        for solver,binary,extra,pattern in [('eon',a.eon,['-case','case.json',*arterial_options('asm'),'-nonlinear_true_residual','true','-fsi_step_timing','true','-linear_report','-solver_report'],r'^fsi_step_timing step=(\d+) elapsed=(\S+)'),('svfsi',a.native,['svFSI.inp'],r'^\s*svfsi_step_timing\s+(\d+)\s+([\d.]+)')]:
            folder=root/('diag-'+solver);shutil.copytree(src/solver,folder);r={};run(folder,[str(binary.resolve()),*extra],r,180)
            measured=physical(folder,solver,meshes,steps);reference=json.loads((gate/('1-'+solver)/'physical.json').read_text())
            if measured['circuit_error']>2e-6 or len(reference['trace'])!=len(measured['trace']):raise ValueError('Diagnostic gate failed')
            results.setdefault('diagnostic_fields',{})[solver]=compare_states(folder,gate/('1-'+solver),steps,meshes,solver)
            for old,new in zip(reference['trace'],measured['trace']):
                if old.keys()!=new.keys() or old['step']!=new['step']:raise ValueError('Mismatched diagnostic output phase')
                for key in old:
                    v,w=old[key],new[key];v=v if isinstance(v,list) else [v];w=w if isinstance(w,list) else [w]
                    if len(v)!=len(w) or any(abs(x-y)>2e-9 for x,y in zip(v,w)):raise ValueError('Diagnostic trajectory changed')
            log=(folder/'solve.log').read_text()
            if solver=='eon':
                records=assembly.records(log,'linear_residual ')
                count=sum(map(int,re.findall(r'^fsi_step=.*? snes_iterations=(\d+)',log,re.M)))
                ratios=[float(x['norm'])/max(1e-23,1e-10*float(x['rhs_norm'])) for x in records]
                if not ratios or len(ratios)!=count or not all(math.isfinite(x) and 0<=x<=1 for x in ratios):raise ValueError('Original operator residual mismatch')
                results['linear_audit']=dict(corrections=count,max_ratio=max(ratios))
            pairs=[(int(n),float(v)) for n,v in re.findall(pattern,log,re.M)]
            if [n for n,_ in pairs]!=list(range(1,steps+1)):raise ValueError('Missing timing records')
            elapsed=[v for _,v in pairs];results.setdefault('loop',{})[solver]=dict(elapsed=elapsed,first=elapsed[0],T_loop=elapsed[-1],T_job=r['T_job'])
    results['passed']=True;save(root/'summary.json',results)


if __name__=='__main__':main()
