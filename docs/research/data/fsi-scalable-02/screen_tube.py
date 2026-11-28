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


def audit_corrections(folder, steps, ranks, rtol=1e-10, atol=1e-23):
    log = (folder / 'solve.log').read_text()
    accepted = assembly.records(log, 'fsi_step=')
    reports = assembly.records(log, 'solver_report ')
    rows = assembly.records(log, 'linear_residual ')
    fields = assembly.records(log, 'linear_field_residual ')
    if len(fields) != 4 * len(rows):
        raise ValueError('Missing block or constraint residual records')
    if len(reports) != steps or len(accepted) != steps:
        raise ValueError('Missing accepted step or solver report')
    offset = 0
    ratios = []
    for step, (report, state) in enumerate(zip(reports, accepted), 1):
        count = int(state['snes_iterations'])
        if (int(state['fsi_step']) != step or int(report['ranks']) != ranks
                or int(report['linear_started']) != count or int(report['linear_completed']) != count
                or int(report['snes_reason']) <= 0
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
            ratio = norm / max(atol, rtol * rhs)
            if ratio > 1:
                raise ValueError(f'Original-operator residual failed at {step}/{index+1}: {ratio}')
            blocks = fields[4*(offset+index):4*(offset+index+1)]
            if {field['name'] for field in blocks} != {'mesh','pressure','structure','velocity'}:
                raise ValueError(f'Incomplete field layout at {step}/{index+1}')
            for field in blocks:
                values = [float(field[k]) for k in ('rms','constraint_max')]
                if int(field['solve']) != index+1 or not all(math.isfinite(v) and v>=0 for v in values):
                    raise ValueError(f'Invalid block residual at {step}/{index+1}')
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
    # B's one-shot distributed LU missed the first original-operator tolerance.
    # Use the same numeric factor as a right PC and rebuild b-Ax at short restarts.
    flags['lu-refined'] = ['-pc_type','lu','-pc_factor_mat_solver_type','superlu_dist',
                           '-ksp_pc_side','right','-ksp_norm_type','unpreconditioned',
                           '-ksp_gmres_restart','2','-ksp_max_it','12']
    cli.add_argument('--modes', nargs='+', choices=flags, default=['asm','physics','mono_braess_tentative','mono_pressure_auto'])
    cli.add_argument('--new-reference', choices=('physics','lu-refined'),
                     help='solve the prepared equations independently at 1e-11/1e-24')
    cli.add_argument('--audited-direct-reference', type=Path,
                     help='reuse a completed direct replay on the requested partition with per-correction reports')
    args = cli.parse_args()
    if args.new_reference in args.modes or len(set(args.modes)) != len(args.modes):
        cli.error('reference and candidate modes must be distinct and candidate names unique')
    if args.new_reference and args.audited_direct_reference:
        cli.error('select one reference trajectory')
    ranks = args.ranks
    if (not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0)) != ranks
            or ranks > 1 and not args.mpiexec):
        cli.error('requires one allocated physical core per rank and an MPI launcher for multiple ranks')
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    gate, root, binary = args.gate.resolve(), args.root.resolve(), args.binary.resolve()
    source, ref = gate/'prepared/eon', gate/'0-eon'
    receipt = json.loads((gate/'summary.json').read_text())
    steps, ref_ranks = receipt['steps'], receipt.get('ranks', 1)
    if steps != 20 or (not args.new_reference and receipt.get('eon_linear','direct') != 'direct'):
        cli.error('requires prepared 20-step inputs and an archived direct or independent new reference')
    root.mkdir(parents=True, exist_ok=False)
    external = dict(status='OPEN', reason='No matched svFSI run for this screen', paired_receipt=str(gate/'summary.json'),
                    paired_receipt_sha256=digest(gate/'summary.json'), archived_pair_passed=receipt['passed'],
                    archived_binaries=receipt['binaries'], archived_inputs=receipt['inputs'])
    results = dict(binary=digest(binary), slurm=os.environ['SLURM_JOB_ID'], ranks=ranks,
                   affinity=sorted(os.sched_getaffinity(0)), external=external, runs=[], passed=False)
    try:
        inputs = {n: digest(source/n) for n in ('case.json','fluid.msh','solid.msh')}
        if any(inputs[n] != receipt['inputs']['eon/'+n] for n in inputs):
            raise ValueError('Prepared inputs differ from the archived hashes')
        results.update(inputs=inputs, steps=steps, petsc_options=os.getenv('PETSC_OPTIONS',''))
        meshes = [read_mesh(source/(name+'.msh')) for name in ('fluid','solid')]
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
            results['prepare']['pieces'] = {p.name:digest(p) for p in [partition/'manifest.yaml',
                *(partition/f'rank_{i}.h5' for i in range(ranks))]}
        if args.new_reference:
            ref, ref_ranks = root/'reference', ranks
            ref.mkdir()
            for name in inputs:
                shutil.copyfile(source/name,ref/name)
            row = dict(mode=args.new_reference,ranks=ranks,binary=digest(binary),log=str(ref/'solve.log'))
            results['reference'] = row
            command = launcher + [str(binary),'-case','case.json'] + part + flags[args.new_reference] + [
                '-ksp_type','fgmres','-ksp_rtol','1e-11','-ksp_atol','1e-24',
                '-nonlinear_true_residual','true','-linear_report','-solver_report']
            run(ref,command,row,args.timeout,140*2**30 if ranks>1 else 8*2**30)
            row['linear_audit'] = audit_corrections(ref,steps,ranks,1e-11,1e-24)
        else:
            original = json.loads((ref/'run.json').read_text())
            if (original['exit_code'] != 0 or original['log_sha256'] != digest(ref/'solve.log')
                    or any(inputs[n] != digest(ref/n) for n in inputs)):
                raise ValueError('Archived direct solve failed or its input/log changed')
            results['reference'] = dict(mode='direct', ranks=ref_ranks, binary=receipt['binaries']['eon'],
                                        log=str(ref/'solve.log'),log_sha256=original['log_sha256'])
            # A direct trajectory can finish every nonlinear step and still fail its
            # first linear correction. A missing audit requires a separate replay.
            if args.audited_direct_reference or not assembly.records((ref/'solve.log').read_text(),'linear_residual '):
                archived, archived_ranks = ref, ref_ranks
                ref, ref_ranks = (args.audited_direct_reference or root/'direct-reference').resolve(), ranks
                record = dict(mode='direct',ranks=ranks,binary=digest(binary),log=str(ref/'solve.log'),
                              archived=results['reference'])
                results['reference'] = record
                if args.audited_direct_reference:
                    previous = json.loads((ref/'run.json').read_text())
                    if previous.get('exit_code') != 0:
                        raise ValueError(f"Direct reference replay exited {previous.get('exit_code')}: {ref/'solve.log'}")
                    if (previous['log_sha256'] != digest(ref/'solve.log')
                            or previous.get('binary_sha256',previous.get('binary')) != digest(binary)
                            or any(digest(ref/n) != sha for n,sha in inputs.items())):
                        raise ValueError('Direct replay binary, inputs or log do not match')
                    record['log_sha256'] = previous['log_sha256']
                    if ranks > 1:
                        command = previous['command']
                        partition = Path(command[command.index('-partition')+1])
                        pieces = {f.name:digest(f) for f in [partition/'manifest.yaml',
                                  *(partition/f'rank_{i}.h5' for i in range(ranks))]}
                        if any(previous.get('partition',{}).get(k)!=v for k,v in pieces.items()):
                            raise ValueError('Direct replay partition provenance differs')
                        record['partition'] = pieces
                else:
                    ref.mkdir()
                    for n in inputs:
                        shutil.copyfile(source/n,ref/n)
                    if ranks > 1:
                        record['partition'] = results['prepare']['pieces']
                    run(ref,launcher+[str(binary),'-case','case.json']+part+
                        ['-ksp_type','preonly','-pc_type','lu','-pc_factor_mat_solver_type','superlu_dist',
                         '-linear_report','-solver_report'],record,args.timeout,140*2**30 if ranks>1 else 8*2**30)
                record['linear_audit'] = audit_corrections(ref,steps,ranks)
                if (record['linear_audit']['ksp'],record['linear_audit']['pc']) != ('preonly','lu'):
                    raise ValueError('Replay is not the requested direct reference')
                # Historical trajectories without a strict linear audit provide
                # context only. Qualify candidates against the audited replay.
                try:
                    record['archive_history_difference'] = assembly.compare_history(
                        assembly.history(archived/'tube.csv',steps,DT),assembly.history(ref/'tube.csv',steps,DT))
                    record['archive_field_difference'] = compare_states(ref,archived,steps,meshes,ranks=(ranks,archived_ranks))
                except (ValueError,RuntimeError,OSError) as error:
                    record['historical_comparison_error'] = str(error)
            else:
                results['reference']['linear_audit'] = audit_corrections(ref,steps,ref_ranks)
        baseline = physical(ref,'eon',meshes,steps,ref_ranks,write=False)
        history = assembly.history(ref/'tube.csv',steps,DT)
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
                self_comparison = mode == 'direct' and not args.new_reference
                row['status'] = 'diagnostic_same_solver' if self_comparison else 'passed'
            except Exception as error:
                row.update(status='failed', error=str(error))
            save(root/'summary.json',results)
        eligible = [row for row in results['runs'] if row['status']!='diagnostic_same_solver']
        results['passed'] = bool(eligible) and all(row['status']=='passed' for row in eligible)
    except Exception as error:
        results['error'] = str(error)
        raise
    finally:
        save(root/'summary.json',results)
    if not results['passed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
