"""Screen four existing FGMRES preconditioners on the frozen 20-step physical case."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from paired_tube import DATA, DT, digest, physical, read_mesh, run, save
sys.path.insert(0,str(DATA.parents[2]/'tests'))
import arterial_ksp
import benchmark_fsi_assembly as assembly
import verify_fsi_multigrid as mg


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('gate','root','binary'): cli.add_argument('--'+name,type=Path,required=True)
    args=cli.parse_args()
    gate=args.gate.resolve(); root=args.root.resolve(); binary=args.binary.resolve()
    receipt=json.loads((gate/'summary.json').read_text())
    if not receipt['passed'] or receipt['steps']!=20 or len(os.sched_getaffinity(0))!=1 or not os.environ.get('SLURM_JOB_ID'):
        cli.error('requires passing paired 20-step reference and a single allocated physical core')
    source=gate/'prepared/eon'; ref=gate/'0-eon'
    meshes=[read_mesh(source/(s+'.msh')) for s in ('fluid','solid')]
    root.mkdir(parents=True,exist_ok=False)
    flags={mode:[*mg.flags(mode),'-pc_plan_rcr_ports','true'] for mode in ('mono_braess_tentative','mono_pressure_auto')}
    flags.update(asm=arterial_ksp.options('asm'),physics=arterial_ksp.options('inner-mgs'))
    results=dict(binary=digest(binary),input=receipt['inputs'],runs=[])
    for mode,options in flags.items():
        folder=root/mode; shutil.copytree(source,folder)
        row=dict(mode=mode); results['runs'].append(row)
        try:
            command=[str(binary),'-case','case.json',*options,'-ksp_type','fgmres','-ksp_rtol','1e-10','-ksp_atol','1e-23',
                     '-nonlinear_true_residual','true','-linear_report','-solver_report']
            run(folder,command,row,180)
            data=physical(folder,'eon',meshes,20)
            if data['circuit_error']>2e-6: raise ValueError('Circuit gate failed')
            row['history_difference']=assembly.compare_history(assembly.history(ref/'tube.csv',20,DT),assembly.history(folder/'tube.csv',20,DT))
            difference=0.
            from study_hydrostatic_fsi import recovered_state
            for step in range(4,21,4):
                for index,suffix in enumerate(('','_solid')):
                    stem=f'tube_step{step}'+suffix
                    states=[recovered_state(directory,stem,meshes[index],bool(index),1) for directory in (folder,ref)]
                    for node,field in states[0].items():
                        other=states[1][node]
                        difference=max(difference,abs(field.pressure-other.pressure),*(abs(a-b) for a,b in zip(field.velocity+field.displacement,other.velocity+other.displacement)))
            row['field_difference']=difference
            if difference>2e-9: raise ValueError('Full field gate failed')
            text=(folder/'solve.log').read_text(); solves=assembly.records(text,'solver_report ')
            if len(solves)!=20 or any(int(r['true_residual_checks'])<1 for r in solves): raise ValueError('Missing original-operator checks')
            row.update(status='passed',true_residual_checks=sum(int(r['true_residual_checks']) for r in solves))
        except Exception as error:
            row.update(status='failed',error=str(error))
        save(root/'summary.json',results)


if __name__=='__main__': main()
