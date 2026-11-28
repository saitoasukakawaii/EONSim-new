"""Screen assembled tube solvers against a completed same-equation direct reference."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys

from paired_tube import DATA, DT, compare, digest, physical, read_mesh, run, save
from internal_tube import compare_states
sys.path.insert(0, str(DATA.parents[2] / 'tests'))
import arterial_ksp
import benchmark_fsi_assembly as assembly
import verify_fsi_multigrid as mg


def audit_corrections(folder, steps, ranks):
    log = (folder / 'solve.log').read_text()
    accepted = assembly.records(log, 'fsi_step=')
    reports = assembly.records(log, 'solver_report ')
    rows = assembly.records(log, 'linear_residual ')
    if len(reports) != steps or len(accepted) != steps:
        raise ValueError('Missing accepted step or solver report')
    offset = 0
    ratios = []
    for step, (report, state) in enumerate(zip(reports, accepted), 1):
        count = int(state['snes_iterations'])
        if (int(state['fsi_step']) != step or int(report['ranks']) != ranks
                or int(report['linear_started']) != count or int(report['snes_reason']) <= 0
                or int(report['ksp_reason']) <= 0):
            raise ValueError(f'Invalid solver report at step {step}')
        for index in range(count):
            row = rows[offset + index]
            # The diagnostic counter restarts with each time-step solve.
            if int(row['solve']) != index + 1:
                raise ValueError(f'Correction sequence mismatch at step {step}')
            norm, rhs = float(row['norm']), float(row['rhs_norm'])
            if not all(math.isfinite(v) and v >= 0 for v in (norm, rhs)):
                raise ValueError('Nonfinite or negative original-operator norm')
            ratio = norm / max(1e-23, 1e-10 * rhs)
            if ratio > 1:
                raise ValueError(f'Original-operator residual failed at {step}/{index+1}: {ratio}')
            ratios.append(ratio)
        offset += count
    if len(rows) != offset or not ratios:
        raise ValueError('Incomplete original-operator audit')
    return dict(corrections=len(rows), max_ratio=max(ratios), dofs=int(reports[0]['dofs']),
                ksp_iterations=sum(int(row['linear_iterations']) for row in reports),
                ksp=reports[0]['ksp'], pc=reports[0]['pc'])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('gate', 'root', 'binary'):
        cli.add_argument('--' + name, type=Path, required=True)
    cli.add_argument('--ranks', type=int, default=1)
    cli.add_argument('--mpiexec', type=Path)
    cli.add_argument('--timeout', type=int, default=780)
    flags = {mode: mg.flags(mode, ports=True) for mode in ('mono_braess_tentative','mono_pressure_auto')}
    flags.update(asm=arterial_ksp.options('asm'), physics=arterial_ksp.options('inner-mgs'), direct=[])
    cli.add_argument('--modes', nargs='+', choices=flags, default=['asm','physics','mono_braess_tentative','mono_pressure_auto'])
    args = cli.parse_args()
    ranks = args.ranks
    if (not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0)) != ranks
            or ranks > 1 and not args.mpiexec):
        cli.error('requires one allocated physical core per rank and an MPI launcher for multiple ranks')
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    gate, root, binary = args.gate.resolve(), args.root.resolve(), args.binary.resolve()
    source, ref = gate/'prepared/eon', gate/'0-eon'
    receipt = json.loads((gate/'summary.json').read_text())
    steps, ref_ranks = receipt['steps'], receipt.get('ranks', 1)
    if steps != 20 or receipt.get('eon_linear','direct') != 'direct':
        cli.error('requires a 20-step direct reference')
    root.mkdir(parents=True, exist_ok=False)
    external = dict(status='OPEN', reason='No matched svFSI run for this screen', paired_receipt=str(gate/'summary.json'),
                    paired_receipt_sha256=digest(gate/'summary.json'), archived_pair_passed=receipt['passed'],
                    archived_binaries=receipt['binaries'], archived_inputs=receipt['inputs'])
    results = dict(binary=digest(binary), slurm=os.environ['SLURM_JOB_ID'], ranks=ranks,
                   affinity=sorted(os.sched_getaffinity(0)), external=external, runs=[], passed=False)
    try:
        original = json.loads((ref/'run.json').read_text())
        if original['exit_code'] != 0 or original['log_sha256'] != digest(ref/'solve.log'):
            raise ValueError('Archived direct solve failed or its log changed')
        inputs = {n: digest(source/n) for n in ('case.json','fluid.msh','solid.msh')}
        if any(inputs[n] != receipt['inputs']['eon/'+n] or inputs[n] != digest(ref/n) for n in inputs):
            raise ValueError('Prepared, archived and executed reference inputs disagree')
        results.update(inputs=inputs, reference=dict(ranks=ref_ranks, binary=receipt['binaries']['eon'],
                       log=str(ref/'solve.log'), log_sha256=original['log_sha256']))
        meshes = [read_mesh(source/(name+'.msh')) for name in ('fluid','solid')]
        baseline = physical(ref,'eon',meshes,steps,ref_ranks,write=False)
        history = assembly.history(ref/'tube.csv',steps,DT)
        part, launcher = [], []
        if ranks > 1:
            prep = root/'prepare'
            prep.mkdir()
            for name in inputs:
                shutil.copyfile(source/name,prep/name)
            partition = root/'partition'
            results['prepare'] = dict(log=str(prep/'solve.log'))
            run(prep,[str(binary),'-case','case.json','-prepare',str(partition),'-parts',str(ranks)],
                results['prepare'],args.timeout,140*2**30)
            part = ['-partition',str(partition)]
            launcher = [str(args.mpiexec.resolve()),'--map-by','core','--bind-to','core','-n',str(ranks)]
        for mode in args.modes:
            folder = root/mode
            folder.mkdir()
            for name in inputs:
                shutil.copyfile(source/name,folder/name)
            row = dict(mode=mode, log=str(folder/'solve.log'))
            results['runs'].append(row)
            try:
                opts = list(flags[mode])
                if mode != 'direct':
                    opts += ['-ksp_type','fgmres','-ksp_rtol','1e-10','-ksp_atol','1e-23','-nonlinear_true_residual','true']
                command = launcher + [str(binary),'-case','case.json'] + part + opts + ['-linear_report','-solver_report']
                run(folder,command,row,args.timeout,140*2**30 if ranks>1 else 8*2**30)
                row['linear_audit'] = audit_corrections(folder,steps,ranks)
                measured = physical(folder,'eon',meshes,steps,ranks)
                row['physical_gates'] = compare(baseline,measured)
                if not all(math.isfinite(v) and v<=1 for v in row['physical_gates'].values()):
                    raise ValueError('Frozen physical budget exceeded')
                row['history_difference'] = assembly.compare_history(history,assembly.history(folder/'tube.csv',steps,DT))
                row['field_difference'] = compare_states(folder,ref,steps,meshes,ranks=(ranks,ref_ranks))
                row['status'] = 'passed'
            except Exception as error:
                row.update(status='failed', error=str(error))
            save(root/'summary.json',results)
        results['passed'] = all(row['status']=='passed' for row in results['runs'])
    except Exception as error:
        results['error'] = str(error)
        raise
    finally:
        save(root/'summary.json',results)
    if not results['passed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
