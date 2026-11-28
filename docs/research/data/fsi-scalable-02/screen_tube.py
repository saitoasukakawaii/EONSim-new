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


sys.path.insert(0, str(DATA / 'fsi-scalable-05'))
from tube_protocol import audit_corrections, compare_trajectories, select, solver_options


def historical_strict_audit(folder, steps, ranks, policy):
    # Untagged #72 direct receipts are reusable only under the historical gate.
    if policy['protocol_id'] != 'STRICT-v1' or policy['mode'] != 'lu':
        raise ValueError('Untagged correction log is ineligible for this protocol')
    rtol, atol = policy['rtol'], policy['atol']
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
    cli.add_argument('--protocol', choices=('STRICT-v1','CALIBRATED-v2'), default='STRICT-v1')
    cli.add_argument('--profile', help='Frozen iterative profile, e.g. fixed-1e-6')
    cli.add_argument('--steps', type=int, choices=(4,20,32,100,224), default=20)
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
    cli.add_argument('--new-reference', choices=('physics','lu-refined','direct'),
                     help='replay the prepared equations under the declared reference profile')
    cli.add_argument('--audited-direct-reference', type=Path,
                     help='reuse a completed direct replay on the requested partition with per-correction reports')
    args = cli.parse_args()
    strict = args.protocol == 'STRICT-v1'
    candidate_policy = select(args.protocol,args.profile or ('fixed-1e-10' if strict else 'fixed-1e-8'))
    if candidate_policy['mode'] == 'lu':
        cli.error('--profile must be an iterative candidate profile')
    reference_policy = select(args.protocol, ('lu' if args.new_reference in ('direct',None) else
                              'strict-reference' if strict else 'fixed-1e-8'))
    if not strict and not (args.new_reference or args.audited_direct_reference):
        args.new_reference = 'direct'
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
    if steps != 20 or (not (args.new_reference or args.audited_direct_reference) and receipt.get('eon_linear','direct') != 'direct'):
        cli.error('requires prepared 20-step inputs and an archived direct or independent new reference')
    if args.steps != steps and not args.new_reference:
        cli.error('a different time window requires a fresh reference')
    steps = args.steps
    root.mkdir(parents=True, exist_ok=False)
    external = dict(status='OPEN', reason='No matched svFSI run for this screen', paired_receipt=str(gate/'summary.json'),
                    paired_receipt_sha256=digest(gate/'summary.json'), archived_pair_passed=receipt['passed'],
                    archived_binaries=receipt['binaries'], archived_inputs=receipt['inputs'])
    results = dict(binary=digest(binary), slurm=os.environ['SLURM_JOB_ID'], ranks=ranks,
                   affinity=sorted(os.sched_getaffinity(0)), external=external,
                   protocol_id=args.protocol, candidate_profile=candidate_policy['profile'],
                   candidate_protocol_hash=candidate_policy['hash'], reference_protocol_hash=reference_policy['hash'], runs=[], passed=False)
    try:
        inputs = {n: digest(source/n) for n in ('case.json','fluid.msh','solid.msh')}
        if any(inputs[n] != receipt['inputs']['eon/'+n] for n in inputs):
            raise ValueError('Prepared inputs differ from the archived hashes')
        if steps != receipt['steps']:
            frozen = source
            source = root/'inputs'
            source.mkdir()
            cfg = json.loads((frozen/'case.json').read_text())
            cfg['fsi'].update(steps=steps, checkpoint_interval=steps)
            save(source/'case.json',cfg)
            for n in ('fluid.msh','solid.msh'):
                shutil.copyfile(frozen/n,source/n)
            inputs = {n:digest(source/n) for n in inputs}
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
            row.update(protocol_id=args.protocol, protocol_hash=reference_policy['hash'], profile=reference_policy['profile'])
            command = launcher + [str(binary),'-case','case.json'] + part + flags[args.new_reference] + solver_options(reference_policy)
            run(ref,command,row,args.timeout,140*2**30 if ranks>1 else 8*2**30)
            row['linear_audit'] = audit_corrections(ref,steps,ranks,reference_policy)
        else:
            original = json.loads((ref/'run.json').read_text()) if (ref/'run.json').exists() else {}
            if not args.audited_direct_reference and (original.get('exit_code') != 0 or original['log_sha256'] != digest(ref/'solve.log')
                    or any(inputs[n] != digest(ref/n) for n in inputs)):
                raise ValueError('Archived direct solve failed or its input/log changed')
            results['reference'] = dict(mode='direct', ranks=ref_ranks, binary=receipt['binaries']['eon'],
                                        log=str(ref/'solve.log'),log_sha256=original.get('log_sha256'))
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
                        solver_options(reference_policy),record,args.timeout,140*2**30 if ranks>1 else 8*2**30)
                legacy = (args.audited_direct_reference and strict and
                          not assembly.records((ref/'solve.log').read_text(),'linear_residual ')[0].get('protocol_hash'))
                record['linear_audit'] = (historical_strict_audit if legacy else audit_corrections)(ref,steps,ranks,reference_policy)
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
                results['reference']['linear_audit'] = historical_strict_audit(ref,steps,ref_ranks,reference_policy)
        for mode in args.modes:
            folder = root/mode
            folder.mkdir()
            for name in inputs:
                shutil.copyfile(source/name,folder/name)
            row = dict(mode=mode, log=str(folder/'solve.log'))
            results['runs'].append(row)
            try:
                policy = select(args.protocol,'lu') if mode == 'direct' else candidate_policy
                row.update(protocol_id=args.protocol, protocol_hash=policy['hash'], profile=policy['profile'])
                opts = list(flags[mode]) + solver_options(policy)
                command = launcher + [str(binary),'-case','case.json'] + part + opts
                run(folder,command,row,args.timeout,140*2**30 if ranks>1 else 8*2**30)
                row['linear_audit'] = audit_corrections(folder,steps,ranks,policy)
                row.update(compare_trajectories(folder,ref,steps,meshes,(ranks,ref_ranks),policy))
                reference_mode = args.new_reference or 'direct'
                self_comparison = (mode == reference_mode or
                                   {mode,reference_mode} <= {'direct','lu-refined'})
                row['status'] = 'diagnostic_same_solver' if self_comparison else 'passed'
            except Exception as error:
                row.update(status='failed', error=str(error))
            save(root/'summary.json',results)
        eligible = [row for row in results['runs'] if row['status']!='diagnostic_same_solver']
        results['reference']['independent_cross_check'] = any(r['status']=='passed' for r in eligible)
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
