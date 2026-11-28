"""Run one cold-start window against a frozen partition and retain the raw solver receipt."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'fsi-scalable-02'))
from paired_tube import compare, digest, physical, read_mesh, run, save
from arterial_ksp import options
from tube_checkpoint import checkpoint_receipt, last_two_cycles, verified_prefix
from resource_accounting import resource_hours
from scale_c import SOLVE_SECONDS, prepare_partition, read_bindings, verify_baseline
from tube_protocol import archived_case, audit_corrections, compare_trajectories, output_manifest, select, solver_options


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('case', choices=('A', 'B', 'C'))
    cli.add_argument('steps', type=int, choices=(1, 4, 20, 32, 100, 224))
    cli.add_argument('profile')
    cli.add_argument('binary', type=Path)
    cli.add_argument('output', type=Path)
    cli.add_argument('--reference', type=Path)
    cli.add_argument('--scaling-from',type=Path,help='32/128-rank cold C20 diagnostic anchored to a qualified C64 fixed window')
    cli.add_argument('--save-checkpoint', action='store_true', help='write a checked native HDF5 generation for continuation')
    cli.add_argument('--resume-from',type=Path,help='continue the selected profile from its own qualified window')
    cli.add_argument('--prefix-pair',type=Path,help='independent iterative partner required for a direct prefix')
    cli.add_argument('--formal', action='store_true', help='omit componentwise and line-search diagnostics')
    cli.add_argument('--pc', choices=('physics','pressure-mg'), default='physics')
    cli.add_argument('--owner', choices=('on','off'), default='on')
    cli.add_argument('--coarse-rows', type=int, default=64)
    cli.add_argument('--mg-scale', action='store_true')
    cli.add_argument('--limit', type=int, required=True, help='Process-tree wall budget in seconds')
    args = cli.parse_args()
    if (args.prefix_pair and not args.resume_from) or (args.resume_from and args.formal):
        cli.error('a restart is a separately timed continuation; --prefix-pair requires --resume-from')
    if args.coarse_rows<=0 or ((args.pc!='pressure-mg' or args.profile=='lu') and
            (args.mg_scale or args.owner!='on' or args.coarse_rows!=64 or
             (args.pc=='pressure-mg' and args.profile=='lu'))):
        cli.error('owner, Telescope and internal scaling require a pressure-mg candidate')
    archived,origin,origin_sha = archived_case(args.case)
    part = Path(origin['command'][origin['command'].index('-partition') + 1])
    ranks = {'A': 4, 'B': 32, 'C': 64}[args.case]
    if args.scaling_from:
        ranks=int(os.environ['SLURM_NTASKS'])
        if (args.case!='C' or args.steps!=20 or ranks not in SOLVE_SECONDS or not args.reference or args.formal
                or args.resume_from or args.limit!=SOLVE_SECONDS[ranks]):
            cli.error('strong scaling uses cold diagnostic C20, its C64 LU reference and the fixed 32/128-rank budget')
    affinity = sorted(os.sched_getaffinity(0))
    if not os.getenv('SLURM_JOB_ID') or len(affinity) != ranks or os.getenv('PETSC_OPTIONS'):
        cli.error('requires one allocated physical core per rank and no PETSC_OPTIONS override')
    binary = args.binary.resolve(strict=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    build = json.loads((binary.parent / 'build-receipt.json').read_text())
    compiled_paths = ['src', 'include', 'cmake', 'CMakeLists.txt']
    source_diff = subprocess.run(['git','diff','--quiet',build['source'],source,'--',*compiled_paths],
                                 cwd=SOURCE).returncode
    if build['binary'] != digest(binary) or source_diff:
        cli.error('build receipt differs from executable or checkout')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    policy = select('CALIBRATED-v2', args.profile)
    row = dict(case=args.case, steps=args.steps, profile=args.profile, policy=policy,
               source=source, compiled_source=build['source'], binary=build['binary'], job=os.environ['SLURM_JOB_ID'],
               ranks=ranks, affinity=affinity, formal=args.formal,
               allocation=os.getenv('SLURM_JOB_CPUS_PER_NODE'),
               limit_seconds=args.limit, rss_limit=140*2**30,
               archive_receipt=origin_sha, qualification='open')
    row['preconditioner'] = dict(pc='lu' if args.profile=='lu' else args.pc)
    if args.pc=='pressure-mg':
        row['preconditioner'].update(owner=args.owner,coarse_rows=args.coarse_rows,mg_scale=args.mg_scale)
    try:
        for name in ('case.json', 'fluid.msh', 'solid.msh'):
            if digest(archived/name) != origin['inputs'][name]:
                raise ValueError('Frozen input changed: ' + name)
            shutil.copyfile(archived/name, out/name)
        archive_ranks=64 if args.scaling_from else ranks
        pieces = {name: digest(part/name) for name in
                  ['manifest.yaml', *(f'rank_{i}.h5' for i in range(archive_ranks))]}
        if any(origin['partition'].get(name) != sha for name, sha in pieces.items()):
            raise ValueError('Frozen partition differs from the archived receipt')
        row['partition'] = pieces
        config = json.loads((out/'case.json').read_text())
        if args.steps != config['fsi']['steps']:
            config['fsi'].update(steps=args.steps, checkpoint_interval=args.steps)
            save(out/'case.json', config)
        row['inputs'] = {name: digest(out/name) for name in ('case.json', 'fluid.msh', 'solid.msh')}
        if args.scaling_from:
            row['scaling']=verify_baseline(args.scaling_from.resolve(strict=True),
                args.reference.resolve(strict=True),row,pieces)
            part,row['partition']=prepare_partition(out,binary,ranks,row)
        start=0
        generation=None
        if args.resume_from:
            previous,segments,generation=verified_prefix(args.resume_from.resolve(strict=True),row,out,
                args.prefix_pair.resolve(strict=True) if args.prefix_pair else None)
            start=previous['steps']
            if args.case=='C' and args.steps in (32,100,224) and start!={32:20,100:32,224:100}[args.steps]:
                raise ValueError('C continuation must extend the qualified preceding milestone')
            row.update(prefix_segments=segments, prefix_T_job=sum(s['T_job'] for s in segments),
                       prefix_receipt=segments[-1]['window_sha256'], restart_generation=str(generation))
            if args.prefix_pair:
                row['prefix_pair_receipt']=digest(args.prefix_pair/'window.json')
                row['prefix_pair_directory']=str(args.prefix_pair.resolve())
        row.update(start_step=start, segment_steps=args.steps-start)
        recipe = [] if args.profile == 'lu' else options('inner-mgs')
        if args.pc=='pressure-mg':
            from verify_fsi_multigrid import flags
            recipe = flags('mono_pressure_auto',ports=True,coarse_rows_per_rank=args.coarse_rows)
            recipe[recipe.index('-ksp_max_it')+1] = '500'
            prefix = '-rcr_bulk_monolithic_mg_'
            recipe += [prefix+'braess_local_fields',str(args.owner=='on').lower(),
                       prefix+'field_scaling',str(args.mg_scale).lower()]
            recipe = [v for v in recipe if v not in ('-solver_report','-linear_report')]
            if args.formal:
                recipe = [v for v in recipe if v not in ('-pc_plan_report','-rcr_port_report')]
            else:
                recipe += [prefix+'report','true']
        policy_flags = solver_options(policy, diagnostics=not args.formal)
        # The same outer option must never appear twice in a campaign command.
        for key in ('-ksp_rtol', '-ksp_atol', '-ksp_type', '-ksp_norm_type', '-ksp_pc_side'):
            if key in recipe and key in policy_flags:
                pos = recipe.index(key)
                del recipe[pos:pos+2]
        check_bindings=args.case=='C' and args.steps==20 and not args.formal and not args.resume_from
        cmd = ['/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpiexec', '--map-by', 'core',
               '--bind-to', 'core', *(['--report-bindings'] if check_bindings else []),
               '-n', str(ranks), str(binary), '-case', 'case.json',
               '-partition', str(part), *recipe, *policy_flags]
        save_checkpoint = args.save_checkpoint or (args.case=='C' and args.steps>=20 and not args.formal)
        if save_checkpoint:
            cmd += ['-checkpoint',str(out/'checkpoint')]
        if generation:
            cmd += ['-restart',str(generation)]
        if not args.formal:
            cmd.extend(['-snes_monitor', '-snes_linesearch_monitor'])
        row['thread_environment'] = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
        os.environ.update(row['thread_environment'])
        run(out, cmd, row, args.limit, row['rss_limit'])
        if check_bindings:
            row['rank_bindings']=read_bindings((out/'solve.log').read_text(),ranks)
        row['linear'] = audit_corrections(out, args.steps, ranks, policy,start)
        if save_checkpoint:
            row['checkpoint'] = checkpoint_receipt(out/'checkpoint',args.steps,ranks)
        row['outputs'] = output_manifest(out, args.steps, ranks,start)
        row['qualification'] = 'linear_window_only'
        if args.steps >= 4:
            meshes = [read_mesh(out/(name+'.msh')) for name in ('fluid','solid')]
            state = physical(out, 'eon', meshes, args.steps, ranks,start_step=start)
            checks = compare(state, state)
            if not all(0 <= v <= 1 for v in checks.values()):
                raise ValueError('Frozen per-run physical budget failed')
            row['physical'] = checks
            if args.steps==224:
                row['periodic']=last_two_cycles(out,meshes,ranks,start,state)
            row['qualification'] = 'awaiting_independent_crosscheck'
            if args.reference:
                ref = args.reference.resolve(strict=True)
                prev = json.loads((ref/'window.json').read_text())
                ref_ranks=64 if args.scaling_from else ranks
                expected_partition=pieces if args.scaling_from else row['partition']
                if (prev['qualification'] != 'awaiting_independent_crosscheck' or prev.get('start_step',0)!=start or
                        prev['profile'] != 'lu' or args.profile == 'lu' or
                        prev['ranks']!=ref_ranks or prev['partition']!=expected_partition or
                        any(prev[k] != row[k] for k in ('inputs', 'binary', 'compiled_source')) or
                        prev['log_sha256'] != digest(ref/'solve.log')):
                    raise ValueError('Invalid or incompatible independent LU reference candidate')
                if start and prev['prefix_receipt']!=previous['reference_receipt']:
                    raise ValueError('Resumed algorithms do not extend the same independently qualified pair')
                audit_corrections(ref, args.steps, ref_ranks, select('CALIBRATED-v2','lu'),start)
                snapshot = output_manifest(ref,args.steps,ref_ranks,start)
                if 'outputs' in prev and snapshot!=prev['outputs']:
                    raise ValueError('Reference outputs changed since its run')
                row['reference_outputs'] = snapshot
                row['comparison'] = compare_trajectories(out, ref, args.steps, meshes,
                                                          ranks=(ranks,ref_ranks), policy=policy, starts=(start,start))
                row['reference_receipt'] = digest(ref/'window.json')
                row['qualification'] = 'independent_pair_passed'
                if args.scaling_from:
                    speedup=row['scaling']['baseline_seconds']/row['T_job']
                    row['scaling_result']=dict(diagnostic_samples=1,relative_to_64=speedup,
                        relative_parallel_efficiency=speedup*64/ranks,
                        partition_seconds=row['partition_preparation']['T_job'])
        row['covered_steps']=args.steps
        row['cumulative_T_job']=row.get('prefix_T_job',0)+row['T_job']
    except Exception as error:
        row.update(qualification='failed', error=str(error))
        raise
    finally:
        if (out/'solve.log').is_file():
            log = (out/'solve.log').read_text(errors='replace')
            row['accepted_steps'] = list(map(int, re.findall(r'^fsi_step=(\d+)', log, re.M)))
            row.update(resource_hours(ranks,row['allocation'],row.get('T_job')))
        save(out/'window.json', row)


if __name__ == '__main__':
    main()
