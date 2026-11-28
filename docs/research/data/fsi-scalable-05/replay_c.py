"""Solve job 409's literal PETSc snapshot with the production semantic PC."""
import argparse
import json
import math
import os
from pathlib import Path
import shlex
import subprocess

from c_first import DATA, ROOT, describe, digest, run, save, select
from tube_protocol import records


def build_replay(stage, library):
    old = Path.home()/'workspace/fsi-scalable-04-runs/release-final/build/release'
    target = old/'CMakeFiles/eonsim.dir'
    flags = [tok.replace(str(old.parents[1]),str(ROOT)) for line in (target/'flags.make').read_text().splitlines()
             if line.startswith('CXX_') for tok in shlex.split(line.split(' = ',1)[1])]
    flags += ['-isystem',str(Path.home()/'software/petsc-3.23.7/arch-linux-c-opt/include')]
    link = shlex.split((target/'link.txt').read_text())
    compile_cmd = [link[0], *flags, '-c', str(Path(__file__).with_suffix('.cpp')), '-o', 'replay_c.o']
    if link.count('CMakeFiles/eonsim.dir/src/main.cpp.o')!=1 or link.count('libeonsim_core.a')!=1:
        raise ValueError('Unexpected Release link description')
    link[link.index('CMakeFiles/eonsim.dir/src/main.cpp.o')] = 'replay_c.o'
    link[link.index('libeonsim_core.a')] = str(library)
    link[link.index('-o')+1] = 'replay_c'
    for cmd in (compile_cmd,link):
        subprocess.run(cmd,cwd=stage,check=True)
    return [compile_cmd,link]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('physics','mg-scaled','mg-unscaled'))
    cli.add_argument('stage', type=Path)
    args = cli.parse_args()
    if not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0))!=64 or os.getenv('PETSC_OPTIONS'):
        cli.error('requires 64 Slurm cores and a clean PETSc environment')
    work = Path.home()/'workspace'
    old = work/'fsi-scalable-03-runs/C-first-64'
    partition = work/'fsi-scalable-02-runs/C20-fixed/partition'
    declaration = json.loads((DATA/'fsi-scalable-03/validation.json').read_text())[
        '$HOME/workspace/fsi-scalable-03-runs/C-first-64/diagnosis.json']
    parts = {f.name:digest(f) for f in partition.iterdir() if f.is_file()}
    if parts != declaration['partition']:
        raise ValueError('Archived partition changed')
    artifacts = {name:digest(old/name) for name in ('operator.petsc','rhs.petsc')}
    if (any(sha != declaration['artifacts'][name] for name,sha in artifacts.items())
            or digest(old/'case.json') != declaration['inputs']['case.json']):
        raise ValueError('Archived equation changed')
    stage = args.stage.resolve()
    stage.mkdir(parents=True,exist_ok=False)
    receipt = (work/'fsi-scalable-05-runs/build/build-receipt.json').resolve(strict=True)
    build = json.loads(receipt.read_text())
    library = receipt.parent/'libeonsim_core.a'
    if digest(library)!=build['archive']:
        raise ValueError('Production archive differs from Release receipt')
    subprocess.run(['git','diff','--exit-code',build['source'],'HEAD','--','include','src','cmake','CMakeLists.txt'],
                   cwd=ROOT,check=True)
    policy = select('CALIBRATED-v2','fixed-1e-8')
    physics = args.mode == 'physics'
    opts = describe('physics' if physics else 'pressure-mg')
    # One cold comparison per MG scale setting. The same 100-iteration prefix
    # isolates early progress well before the known 500-iteration plateau.
    budget = 500 if physics else 100
    if args.mode == 'mg-scaled':
        opts += ['-rcr_bulk_monolithic_mg_field_scaling','true']
    opts += ['-ksp_type','fgmres','-ksp_pc_side','right','-ksp_norm_type','unpreconditioned',
             '-ksp_rtol',str(policy['rtol']),'-ksp_atol',str(policy['atol']),'-ksp_max_it',str(budget),
             '-ksp_monitor','-ksp_converged_reason','-options_view']
    row = dict(mode=args.mode, scope='cold archived linear system, no accepted time step',
               protocol_hash=policy['hash'], protocol_id=policy['protocol_id'], profile=policy['profile'],
               job=os.environ['SLURM_JOB_ID'], affinity=sorted(os.sched_getaffinity(0)), artifacts=artifacts,
               case_sha256=declaration['inputs']['case.json'], partition=parts, archive_sha256=build['archive'],
               compile_source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
               production_commit=build['source'], build_receipt_sha256=digest(receipt), outer_budget=budget)
    try:
        row['build'] = build_replay(stage,library)
        row['binary_sha256'] = digest(stage/'replay_c')
        cmd = [declaration['command'][0],'--map-by','core','--bind-to','core','-n','64',
               str(stage/'replay_c'),str(old),str(partition),'physics' if physics else 'monolithic_mg',
               str(stage/'iterate.petsc'),*opts]
        os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        run(stage,cmd,row,180 if physics else 90,100*2**30)
        event, = records((stage/'solve.log').read_text().splitlines(),'snapshot_correction ')
        row['event'] = event
        row['artifacts']['iterate.petsc'] = digest(stage/'iterate.petsc')
        actual, rhs = float(event['norm']), float(event['rhs'])
        if (float(event['rtol'])!=policy['rtol'] or float(event['atol'])!=policy['atol']
                or not all(math.isfinite(n) and n >= 0 for n in (actual,rhs))
                or int(event['reason'])<=0 or actual>max(policy['atol'],policy['rtol']*rhs)):
            raise ValueError('Returned vector fails archived original equation or KSP status')
        row['linear_screen'] = 'passed'
    except Exception as error:
        row.update(linear_screen='failed',diagnosis=str(error))
        raise
    finally:
        save(stage/'replay.json',row)


if __name__ == '__main__':
    main()
