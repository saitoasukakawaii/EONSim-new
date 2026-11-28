"""Bounded paired timing of existing owner/Telescope options on archived 64x2 inputs."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SOURCE / 'scripts'))
import benchmark_fsi_block_scaling as scaling


def field_gate(folder, reference, cache):
    """Identical ordered piece bytes inherit a completed topology/field audit."""
    outcomes = {}
    for stem, db in [('solution', 'fields.sqlite'), ('solution_step5', 'last-step.sqlite')]:
        hashes = {}
        for domain in ('', '_solid'):
            for rank in range(64):
                suffix = f'{domain}_rank{rank}.vtu'
                hashes[suffix] = scaling.assembly.digest(folder / (stem + suffix))
        key = tuple(hashes.values()), db
        if key not in cache:
            actual = folder / (stem + '.sqlite')
            scaling.spool_fields(folder / (stem + '.vtu'), 64, actual)
            diff = scaling.compare_spools(reference / db, actual)
            cache[key] = (diff, str(actual))
        diff, witness = cache[key]
        outcomes[stem] = dict(difference=diff, audited_spool=witness, pieces=hashes)
    return outcomes


def telescope_report(text, budget):
    hierarchy = scaling.assembly.records(text, 'pc_monolithic_mg ')
    observed = sorted({(int(row['coarsest_rows']), int(row['coarse_processes'])) for row in hierarchy})
    nodes = scaling.assembly.records(text, 'solver_node ')
    outer = [row for row in nodes if row['path'] == 'root/monolithic_coarse']
    children = [row for row in nodes if row['path'] == 'root/monolithic_coarse/telescope']
    if observed and observed[0][1] == 64:
        children = outer  # Without redistribution the outer KSP is the coarse solve.
    if not outer or not children or len(observed) != 1:
        raise ValueError('Missing observed coarse hierarchy or child communicator')
    ranks = {int(row['rank']) for row in children}
    if {int(row['comm_size']) for row in children} != {len(ranks)} or observed[0][1] != len(ranks):
        raise ValueError('Child rank participation does not match coarse communicator')
    for rank in ranks:
        if sum(int(row['rank']) == rank for row in children) != 5:
            raise ValueError('Incomplete per-step coarse KSP reports')
    local_rows = {r: {int(row['operator_local_rows']) for row in children if int(row['rank']) == r} for r in ranks}
    if any(len(sizes) != 1 for sizes in local_rows.values()) or sum(next(iter(s)) for s in local_rows.values()) != observed[0][0]:
        raise ValueError('Local ownership does not cover the coarse matrix')
    reduced = observed[0][1] != 64
    if reduced and not all(row['ksp'] == 'preonly' for row in outer):
        raise ValueError('Missing outer coarse PREONLY report')
    counters = [row for row in scaling.assembly.records(text, 'monolithic_mg_stats ') if int(row['rank']) == 0]
    return dict(rows_budget=budget, coarsest_rows=observed[0][0], participating_ranks=sorted(ranks),
                child=[{k: r[k] for k in ('rank', 'comm_size', 'operator_rows', 'operator_local_rows', 'last_iterations',
                                           'ksp', 'pc', 'ksp_reason')} for r in children],
                coarse_calls=[int(row['coarse_solves']) for row in counters],
                outer_last_iterations=[int(row['last_iterations']) for row in outer if int(row['rank']) == 0])


def run_case(args, case, result):
    original = next(row for row in case['runs'] if row['label'] == 'warmup-mono_braess_tentative'
                    and row['status'] == 'passed')
    reference = Path(next(row['log'] for row in case['runs']
                          if row['label'] == 'reference' and row['status'] == 'passed')).parent
    n = case['subdivisions']
    inputs = {}
    for item in case['input_sha256'] + case['preparation']['artifacts']:
        path = args.seed.parent / item['path']
        inputs[str(path)] = scaling.assembly.digest(path)
        if inputs[str(path)] != item['sha256']:
            raise ValueError(f'Archived seed file has changed: {path}')
    dt = case['configuration']['fsi']['dt']
    history = scaling.assembly.history(reference / 'solution.csv', 5, dt)
    ref_hashes = {p: scaling.assembly.digest(reference / p)
                  for p in ('solution.csv', 'fields.sqlite', 'last-step.sqlite')}
    metadata = result['cases'][n] = dict(inputs=inputs, reference=str(reference), reference_sha256=ref_hashes)
    base = original['command'].copy()
    if (base[base.index('-n') + 1], base[base.index('-fsi_threads') + 1],
            base[base.index('--bind-to') + 1], base[base.index('--map-by') + 1]) != ('64', '2', 'core', 'slot:PE=2'):
        raise ValueError('Seed rank/thread placement differs')
    base[base.index('-case') - 1] = str(args.binary)
    modes = (0, 1) if args.experiment == 'owner' else (64, 0)
    cache = {}
    for repeat in range(4):
        order = modes if repeat % 2 == 0 else reversed(modes)
        for mode in order:
            folder = args.root / f'n{n}-r{repeat}-m{mode}'
            folder.mkdir()
            command = base.copy()
            command[command.index('-output') + 1] = str(folder / 'solution.vtu')
            budget = 64
            if args.experiment == 'owner':
                name = 'mono_braess_tentative'
                command += ['-monolithic_mg_braess_local_fields', str(bool(mode)).lower()]
            else:
                # Set the second budget using the observed row count of the first diagnostic.
                # ceil(rows / budget)=2, selecting exactly two participating ranks.
                name = 'mono_pressure_auto'
                if mode == 0:
                    budget = (metadata['coarsest_rows'] + 1) // 2
                command = command[:command.index('-ksp_type')] + scaling.multigrid.flags(name, coarse_rows_per_rank=budget)
                command += ['-monolithic_mg_braess_local_fields', 'true']
            if repeat:
                command = [arg for arg in command if arg not in
                           ('-solver_report', '-linear_report', '-pc_plan_report', '-fsi_assembly_report', '-solver_rank_report')]
            row = dict(subdivisions=n, mode=mode, repeat=repeat, kind='formal' if repeat else 'diagnostic_warmup',
                       log=str(folder / 'solve.log'), command=command, status='running')
            result['runs'].append(row)
            try:
                text = scaling.block.timed_command(command, folder / 'solve.log', 600, row,
                                                  rss_interval=.5, rss_limit=140 * 2**30)
                if text.count('status=success') != 1 or 'status=failed' in text:
                    raise ValueError('Incomplete solve')
                row['core_hours'] = 128 * row['wall_seconds'] / 3600
                trace = scaling.assembly.history(folder / 'solution.csv', 5, dt)
                row['history_difference'] = scaling.assembly.compare_history(history, trace)
                row['history_sha256'] = scaling.assembly.digest(folder / 'solution.csv')
                if not repeat:
                    audit = scaling.multigrid.audit(text, trace, 64, name, coarse_rows_per_rank=budget)
                    row['corrections'] = {k: audit[k] for k in
                                          ('outer_iterations', 'corrections', 'dofs', 'max_true_residual_ratio')}
                    if args.experiment == 'telescope':
                        row['coarse'] = telescope_report(text, budget)
                        if mode == 64:
                            metadata['coarsest_rows'] = row['coarse']['coarsest_rows']
                            if len(row['coarse']['participating_ranks']) <= 2:
                                raise ValueError('Baseline already uses two or fewer coarse ranks')
                        elif len(row['coarse']['participating_ranks']) != 2:
                            raise ValueError('Two-rank coarse comparison not exercised')
                row['fields'] = field_gate(folder, reference, cache)
                row['status'] = 'passed'
            except Exception as error:
                row.update(status='failed', error=str(error))
                raise
            finally:
                if (folder / 'solve.log').exists():
                    row['log_sha256'] = scaling.assembly.digest(folder / 'solve.log')
                scaling.save(result, args.root / 'summary.json')
    stats = {}
    for mode in modes:
        subset = [r for r in result['runs'] if r['mode'] == mode and r['subdivisions'] == n and r['repeat']]
        stats[mode] = {key: scaling.assembly.stats([r[key] for r in subset]) for key in
                       ('wall_seconds', 'local_job_peak_sampled_rss_bytes', 'core_hours')}
    metadata['stats'] = stats
    metadata['median_reduction'] = 1 - stats[modes[1]]['wall_seconds']['median'] / stats[modes[0]]['wall_seconds']['median']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', choices=['owner', 'telescope'])
    parser.add_argument('binary', type=Path)
    parser.add_argument('binary_commit')
    parser.add_argument('seed', type=Path)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.binary = args.binary.resolve(strict=True)
    if not os.environ.get('SLURM_JOB_ID') or len(os.sched_getaffinity(0)) != 128:
        parser.error('requires exclusive allocation of all 128 physical cores')
    seed_hash = scaling.assembly.digest(args.seed)
    if seed_hash != 'b634faab2675ae5d86f62f00b72e2427ce1cb3e5fa6681e9b7fb86ac6f8a012c':
        raise ValueError('The reference receipt differs from #71')
    seed = json.loads(args.seed.read_text())
    threads = dict(OMP_NUM_THREADS='2', OMP_DYNAMIC='FALSE', OMP_PLACES='cores', OMP_PROC_BIND='close',
                   MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    if any(seed['environment'].get(k) != v for k, v in threads.items()):
        raise ValueError('Thread environment differs from seed')
    os.environ.update(threads)
    args.root.mkdir(parents=True, exist_ok=False)
    result = dict(job=os.environ['SLURM_JOB_ID'], affinity=sorted(os.sched_getaffinity(0)),
                  source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip(),
                  binary=str(args.binary), binary_commit=args.binary_commit, binary_sha256=scaling.assembly.digest(args.binary),
                  experiment=args.experiment, environment=threads, seed=str(args.seed), seed_sha256=seed_hash,
                  cases={}, runs=[], passed=False)
    for n in ((37, 47) if args.experiment == 'owner' else (37,)):
        case = next(c for c in seed['cases'] if c['subdivisions'] == n and c['ranks'] == 64 and c['status'] == 'passed')
        run_case(args, case, result)
    result['passed'] = True
    scaling.save(result, args.root / 'summary.json')


if __name__ == '__main__':
    main()
