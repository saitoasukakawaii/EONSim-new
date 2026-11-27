"""Bounded coupled FSI mesh-refinement study with unchanged physical gates.

The independent-domain generator supplies n=4/6/8 refinements. Every solver uses
the same mesh, partition, five-step trajectory and field scales. A direct solve
is checked before coupled, twolevel and aggregate responses are compared. The
existing assembly benchmark owns the saved-field, accepted-history and original
linear-residual gates; solver presets come from the arterial block study.

By default only correctness is run. With --timing-repeats >= 3 the initial runs
are unmeasured warmups and passing iterative modes receive interleaved samples.
Timing has no pass threshold. Each command has a process-group watchdog; failed
or timed-out modes remain failed evidence and receive no performance samples.

--campaign strong/weak selects the cluster-capable path. Strong scaling uses
each fixed mesh at every requested rank count; weak scaling pairs subdivisions
with ranks explicitly and reports observed DoF/rank drift. Actual per-rank host
names determine node counts; --minimum-nodes and --minimum-dofs are observed
qualification gates, not estimates. A same-equation iterative reference is the
default at large sizes (direct is optional). All accepted histories and final
nodal fields are checked; final fields and topology are spooled to SQLite so the
auditor holds at most one rank's VTU data, not a global Python field dictionary.
The MPI launcher/environment is inherited on this path: no TCP transport is
forced on clusters. Use repeated --mpi-arg=... for scheduler/hostfile options.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import benchmark_fsi_assembly as assembly

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import verify_fsi_block_efficiency as block
import verify_fsi_multigrid as multigrid

MODES = ('coupled_nodal', 'twolevel_rigid', 'aggregate_rigid',
         'aggregate_rigid_adaptive')
PC_COUNTERS = ('pc_refreshes', 'pc_reuses', 'pc_drift_refreshes',
               'pc_age_refreshes', 'pc_iteration_refreshes', 'pc_context_refreshes',
               'pc_rebuild_retries')


def hierarchy(text, mode, ranks, steps):
    """Inspect observed operators; sizes and levels are never inferred from n."""
    expected = {prefix: (ksp, pc) for prefix, ksp, pc in block.expected_solvers(mode)}
    observed, completed = None, 0
    for line in text.splitlines():
        if line.startswith('solver_report '):
            assembly.require(observed is None, 'Nested solver-report interval')
            observed = {prefix: [0] * ranks for prefix in expected}
        elif line.startswith('solver_node '):
            node = assembly.records(line, 'solver_node ')[0]
            prefix = node['prefix']
            if prefix not in expected:
                continue
            rank = assembly.number(node, 'rank', 0, True)
            assembly.require(observed is not None and rank < ranks, 'Response outside accepted-step interval')
            assembly.require((node['ksp'], node['pc']) == expected[prefix],
                             ('Requested response differs', mode, prefix, rank))
            reason = assembly.number(node, 'ksp_reason', integer=True)
            assembly.require(assembly.number(node, 'pc_reason', integer=True) == 0 and
                             (reason > 0 or (node['ksp'] != 'preonly' and reason == -3)),
                             ('Response solve failed', node))
            assembly.number(node, 'reported_norm', 0)
            observed[prefix][rank] += 1
        elif line.startswith('fsi_step='):
            assembly.require(observed is not None and all(counts == [1] * ranks for counts in observed.values()),
                             ('Requested response was not observed once on every rank/step', mode, observed))
            observed = None
            completed += 1
    assembly.require(completed == steps and observed is None, 'Incomplete response hierarchy trajectory')
    last = assembly.records(text.rsplit('solver_report ', 1)[1], 'solver_node ')
    last = [node for node in last if int(node['rank']) == 0]
    result = dict(last_rank0_operators=last)
    if mode.startswith(('twolevel_', 'aggregate_')):
        basis = assembly.records(text, 'pc_twolevel ')
        assembly.require(basis, ('Missing interpolation evidence', mode))
        dimensions = {int(row['global_modes']) for row in basis}
        assembly.require(len(dimensions) == 1, ('Interpolation dimension changed', dimensions))
        result['first_coarse_dimension'] = dimensions.pop()
        result['aggregate_nodes'] = int(basis[-1]['aggregate_nodes'])
        result['velocity_mg_levels'] = int(basis[-1]['levels'])
        if mode.startswith('aggregate_'):
            prefix = 'fieldsplit_dynamics_fieldsplit_velocity_mg_coarse_'
            coarse = [node for node in last if node['prefix'] == prefix]
            assembly.require(len(coarse) == 1, 'Missing final auxiliary GAMG operator')
            stem = coarse[0]['path'] + '/'
            levels = [node for node in last if node['path'].startswith(stem) and
                      '/' not in node['path'][len(stem):]]
            assembly.require(levels and int(coarse[0]['operator_rows']) ==
                             result['first_coarse_dimension'], 'Inconsistent auxiliary coarse hierarchy')
            result['auxiliary_gamg_levels'] = len(levels)
            result['auxiliary_level_rows'] = [int(node['operator_rows']) for node in levels]
    return result


def solver_kind(mode):
    # The assembly audit verifies the actual outer and velocity response types;
    # hierarchy() additionally checks the aggregate GAMG child on every step.
    return 'direct' if mode == 'direct' else 'hybrid' if mode.startswith('coupled_') else 'twolevel'


def save(result, path):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def rank_placement(log, ranks, steps, minimum_nodes=1):
    """Inspect actual MPI ranks after each accepted solve, never launcher guesses."""
    rows = assembly.records(log, 'solver_rank_report ')
    assembly.require(len(rows) == ranks * steps, 'Missing per-rank placement/resource records')
    hosts, records = None, []
    for step in range(steps):
        group = rows[step*ranks:(step+1)*ranks]
        assembly.require(sorted(int(row['rank']) for row in group) == list(range(ranks)),
                         'Duplicate or missing MPI rank in placement')
        mapping = {int(row['rank']): row['host'] for row in group}
        assembly.require(all(mapping.values()) and (hosts is None or mapping == hosts),
                         'Missing host name or placement changed between accepted solves')
        hosts = mapping
        for row in group:
            for name in ('owned', 'ghosts', 'rss_bytes', 'peak_rss_bytes', 'linear_seconds'):
                assembly.number(row, name, 0)
            assembly.require(float(row['peak_rss_bytes']) >= float(row['rss_bytes']),
                             'Peak rank RSS is below current RSS')
        records.append(group)
    count = len(set(hosts.values()))
    assembly.require(count >= minimum_nodes, ('Observed node count below required minimum', count, minimum_nodes))
    return dict(nodes=count, hosts=hosts, rank_records=records,
                multinode=count > 1,
                peak_rss_max_bytes=max(float(row['peak_rss_bytes']) for row in rows),
                peak_rss_sum_bytes=max(sum(float(row['peak_rss_bytes']) for row in group) for group in records))


def _database(path):
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA cache_size=-8192')
    connection.execute('PRAGMA temp_store=FILE')
    return connection


def spool_fields(output, ranks, database):
    """Validate every final owner/ghost and cell using bounded-memory disk joins."""
    assembly.require(not database.exists(), 'Refusing to overwrite a field evidence database')
    db = _database(database)
    schemas = {}
    try:
        db.executescript('''
          CREATE TABLE support(domain TEXT,node INTEGER,PRIMARY KEY(domain,node));
          CREATE TABLE observations(domain TEXT,node INTEGER,rank INTEGER,owner INTEGER,data BLOB,
                                    PRIMARY KEY(domain,node,rank));
          CREATE TABLE cells(domain TEXT,element INTEGER,tag INTEGER,type INTEGER,nodes BLOB,
                             PRIMARY KEY(domain,element));
          CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT);
        ''')
        for domain in ('', '_solid'):
            for rank in range(ranks):
                suffix = domain + (f'_rank{rank}' if ranks > 1 else '') + '.vtu'
                path = output.with_name(output.stem + suffix)
                piece = ET.parse(path).find('.//Piece')
                assembly.require(piece is not None, ('Missing VTU piece', path))
                count, ncells = int(piece.get('NumberOfPoints')), int(piece.get('NumberOfCells'))
                arrays = {}
                for item in piece.findall('./PointData/DataArray'):
                    name = item.get('Name')
                    assembly.require(name and name not in arrays and item.get('format', 'ascii') == 'ascii',
                                     ('Duplicate/unsupported nodal array', path, name))
                    width = int(item.get('NumberOfComponents', '1'))
                    values = list(map(int if name in ('mesh_node_id', 'owner', 'algebra_node_id') else float,
                                      (item.text or '').split()))
                    assembly.require(width > 0 and len(values) == width*count and all(map(math.isfinite, values)),
                                     ('Invalid nodal array shape/value', path, name))
                    arrays[name] = width, values
                assembly.require('mesh_node_id' in arrays and 'owner' in arrays and
                                 arrays['mesh_node_id'][0] == arrays['owner'][0] == 1,
                                 ('Missing scalar node/owner identities', path))
                xyz = piece.find('./Points/DataArray')
                assembly.require(xyz is not None and xyz.get('format', 'ascii') == 'ascii',
                                 ('Missing ASCII coordinates', path))
                coordinates = list(map(float, (xyz.text or '').split()))
                assembly.require(len(coordinates) == 3*count and all(map(math.isfinite, coordinates)),
                                 ('Invalid coordinates', path))
                arrays['coordinates'] = 3, coordinates
                ids, owners = arrays['mesh_node_id'][1], arrays['owner'][1]
                assembly.require(len(set(ids)) == count and all(0 <= owner < ranks for owner in owners),
                                 ('Duplicate node or invalid owner', path))
                names = sorted(set(arrays) - {'mesh_node_id', 'owner', 'algebra_node_id'})
                schema = [(name, arrays[name][0]) for name in names]
                assembly.require(domain not in schemas or schemas[domain] == schema,
                                 'Nodal field schema differs between MPI ranks')
                schemas[domain] = schema
                pack = struct.Struct('<' + str(sum(width for _, width in schema)) + 'd')

                def observations():
                    for index, (node, owner) in enumerate(zip(ids, owners)):
                        values = [value for name, width in schema
                                  for value in arrays[name][1][width*index:width*(index+1)]]
                        yield domain, node, rank, owner, pack.pack(*values)
                db.executemany('INSERT INTO observations VALUES(?,?,?,?,?)', observations())
                cell_arrays, cell_data = {}, {}
                for group, target in (('Cells', cell_arrays), ('CellData', cell_data)):
                    for item in piece.findall(f'./{group}/DataArray'):
                        name = item.get('Name')
                        assembly.require(name not in target and item.get('format', 'ascii') == 'ascii',
                                         ('Duplicate/unsupported cell array', path, name))
                        target[name] = list(map(int, (item.text or '').split()))
                connectivity = cell_arrays['connectivity']
                offsets, kinds = cell_arrays['offsets'], cell_arrays['types']
                elements, tags = cell_data['mesh_element_id'], cell_data['physical_tag']
                assembly.require(all(len(values) == ncells for values in (offsets, kinds, elements, tags)) and
                                 all(0 <= index < count for index in connectivity), 'Invalid topology array lengths')
                db.executemany('INSERT OR IGNORE INTO support VALUES(?,?)',
                               ((domain, ids[index]) for index in set(connectivity)))
                start = 0
                for end, kind, element, tag in zip(offsets, kinds, elements, tags):
                    assembly.require(start < end <= len(connectivity), 'Invalid cell offsets')
                    nodes = [ids[index] for index in connectivity[start:end]]
                    db.execute('INSERT INTO cells VALUES(?,?,?,?,?)',
                               (domain, element, tag, kind, struct.pack('<' + str(len(nodes)) + 'q', *nodes)))
                    start = end
                assembly.require(start == len(connectivity), 'Trailing topology connectivity')
                db.commit()
        inconsistent = db.execute('''SELECT s.domain,s.node FROM support s
          LEFT JOIN observations o ON s.domain=o.domain AND s.node=o.node
          GROUP BY s.domain,s.node
          HAVING count(DISTINCT o.owner)<>1 OR sum(CASE WHEN o.rank=o.owner THEN 1 ELSE 0 END)<>1 LIMIT 1''').fetchone()
        assembly.require(inconsistent is None, ('Missing/inconsistent unique owner', inconsistent))
        db.executescript('''CREATE TABLE fields AS
          SELECT o.domain,o.node,o.data FROM observations o INNER JOIN support s
          ON o.domain=s.domain AND o.node=s.node WHERE o.rank=o.owner;
          CREATE UNIQUE INDEX fields_identity ON fields(domain,node);
        ''')
        rows = db.execute('SELECT count(*) FROM fields').fetchone()[0]
        assembly.require(rows > 0, 'No supported physical fields were written')
        worst, checked = 0., 0
        for domain, expected, observed in db.execute('''SELECT o.domain,f.data,o.data
          FROM observations o INNER JOIN fields f ON o.domain=f.domain AND o.node=f.node'''):
            width = sum(width for _, width in schemas[domain])
            first, second = struct.unpack('<' + str(width) + 'd', expected), struct.unpack('<' + str(width) + 'd', observed)
            worst = max(worst, max(abs(a-b) for a, b in zip(first, second)))
            checked += width
        assembly.require(worst <= assembly.FIELD_LIMIT, ('Ghost field differs from unique owner', worst))
        db.execute('INSERT INTO metadata VALUES(?,?)', ('schemas', json.dumps(schemas, sort_keys=True)))
        db.executescript('DROP TABLE observations; DROP TABLE support;')
        db.commit()
        return dict(database=str(database), nodes=rows, checked_values=checked,
                    cells=db.execute('SELECT count(*) FROM cells').fetchone()[0],
                    ghost_max_difference=worst, schemas=schemas)
    finally:
        db.close()


def compare_spools(reference, actual):
    """Cross-partition all-node comparison; partition IDs/owner ranks may differ."""
    db = _database(actual)
    try:
        db.execute('ATTACH DATABASE ? AS reference', (str(reference),))
        schema = db.execute("SELECT value FROM metadata WHERE name='schemas'").fetchone()
        assembly.require(schema == db.execute("SELECT value FROM reference.metadata WHERE name='schemas'").fetchone(),
                         'Saved field schema changed')
        for table, columns in (('fields', 'domain,node'), ('cells', 'domain,element,tag,type,nodes')):
            for first, second in ((table, 'reference.'+table), ('reference.'+table, table)):
                mismatch = db.execute(f'SELECT {columns} FROM {first} EXCEPT SELECT {columns} FROM {second} LIMIT 1').fetchone()
                assembly.require(mismatch is None, ('Saved topology/node identity changed', table, mismatch))
        worst = 0.
        for first, second in db.execute('''SELECT a.data,b.data FROM fields a INNER JOIN reference.fields b
                                           ON a.domain=b.domain AND a.node=b.node'''):
            assembly.require(len(first) == len(second) and len(first) % 8 == 0, 'Invalid packed field length')
            fmt = '<' + str(len(first)//8) + 'd'
            worst = max(worst, max(abs(a-b) for a, b in zip(struct.unpack(fmt, first), struct.unpack(fmt, second))))
        assembly.require(worst <= assembly.FIELD_LIMIT, ('Saved physical field mismatch', worst))
        return worst
    finally:
        db.close()


def file_receipts(paths, root):
    """Stream large mesh/partition/output files without copying them into RAM."""
    result = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        result.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size,
                           sha256=digest.hexdigest()))
    return result


def large_campaign(args):
    """Execute explicit strong/weak studies; absent scale is never a pass claim."""
    executable, mpiexec = args.executable.resolve(), args.mpiexec.resolve()
    work = args.work.resolve() / str(time.time_ns())
    work.mkdir(parents=True)
    receipt = work / 'results.json'
    environment = dict(OMP_NUM_THREADS=str(args.omp_threads), OMP_DYNAMIC='FALSE',
                       OMP_PLACES='cores', OMP_PROC_BIND='close',
                       OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    os.environ.update(environment)
    inherited = {name: value for name, value in os.environ.items()
                 if name.startswith(('OMPI_MCA_', 'PRTE_MCA_', 'SLURM_')) and
                 any(token in name for token in ('btl', 'pml', 'rmaps', 'JOB_ID', 'NODELIST', 'NTASKS', 'CPUS'))}
    result = dict(status='running', campaign=args.campaign, build_source=args.build_source,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  executable=str(executable), executable_sha256=assembly.digest(executable),
                  driver_sha256=assembly.digest(__file__), environment=environment,
                  inherited_launcher_environment=inherited, mpi_args=args.mpi_arg,
                  reference_mode=args.reference_mode,
                  reference_kind='direct' if args.reference_mode == 'direct' else 'same-equation iterative',
                  expected_steps=args.steps, timing_repeats=args.timing_repeats,
                  minimum_nodes=args.minimum_nodes, minimum_dofs=args.minimum_dofs,
                  fsi_threads=args.omp_threads,
                  local_job_rss_interval_seconds=args.local_rss_interval,
                  local_job_rss_limit_bytes=args.local_rss_limit_bytes,
                  field_absolute_limit=assembly.FIELD_LIMIT,
                  audit_scope='all accepted histories, final fields and topology, all true linear residuals',
                  cases=[], failures=[], scaling=[])
    save(result, receipt)
    grids = [(n, rank) for n in args.subdivisions for rank in args.ranks] if args.campaign == 'strong' else list(zip(args.subdivisions, args.ranks))
    inputs, references = {}, {}

    def run_command(command, log, row):
        row.update(command=list(map(str, command)), log=str(log))
        save(result, receipt)
        try:
            return block.timed_command(command, log, args.timeout, row,
                                       rss_interval=args.local_rss_interval,
                                       rss_limit=args.local_rss_limit_bytes)
        finally:
            if log.is_file():
                row['log_sha256'] = assembly.digest(log)

    for n, ranks in grids:
        directory = work / f'n{n}-r{ranks}'
        directory.mkdir()
        record = dict(subdivisions=n, ranks=ranks, runs=[], medians={}, status='running')
        result['cases'].append(record)
        try:
            if n not in inputs:
                case = assembly.generate(work / f'n{n}-input', n)
                cfg = json.loads(case.read_text())
                # All histories remain; only the final volume snapshot is
                # written on the large path. This is explicit in audit_scope.
                cfg['fsi'].update(steps=args.steps, output_interval=args.steps)
                case.write_text(json.dumps(cfg, indent=2) + '\n')
                inputs[n] = case, cfg, file_receipts(case.parent.iterdir(), work)
            case, cfg, hashes = inputs[n]
            record.update(input=str(case), input_sha256=hashes, configuration=cfg)
            partition = directory / 'partition'
            prep = {}; record['preparation'] = prep
            run_command([executable, '-case', case, '-prepare', partition, '-parts', ranks], directory/'prepare.log', prep)
            manifest = partition/'manifest.yaml'
            assembly.require(manifest.is_file(), 'Partition preparation did not publish a manifest')
            metadata = dict(re.findall(r'^(version|ranks|global_nodes|global_cells): ([0-9]+)$', manifest.read_text(), re.M))
            assembly.require(int(metadata.get('ranks', '0')) == ranks and
                             int(metadata.get('global_cells', '0')) > 0, 'Invalid partition manifest')
            shards = [p for p in partition.iterdir() if p.suffix in ('.h5', '.hdf5')]
            assembly.require(len(shards) == ranks, 'Partition rank-shard count differs')
            partition_files = file_receipts(partition.iterdir(), work)
            prep.update(metadata=metadata, artifacts=partition_files)
        except Exception as exc:
            record.update(status='failed', error=str(exc))
            result['failures'].append(dict(subdivisions=n, ranks=ranks, phase='prepare', error=str(exc)))
            save(result, receipt)
            continue

        local_reference = None

        def run(mode, label, timing):
            nonlocal local_reference
            run_dir = directory/label; run_dir.mkdir()
            output = run_dir/'solution.vtu'
            row = dict(mode=mode, label=label, timing_sample=timing, status='running')
            record['runs'].append(row)
            try:
                assembly.require(hashes == file_receipts(case.parent.iterdir(), work) and
                                 partition_files == file_receipts(partition.iterdir(), work), 'Inputs changed before run')
                flags = multigrid.flags(mode)
                if '-fsi_assembly_report' not in flags:
                    flags.append('-fsi_assembly_report')
                text = run_command([mpiexec, *args.mpi_arg, '-n', ranks, executable, '-case', case,
                                    '-partition', partition, '-output', output,
                                    '-vtu_format', 'ascii', '-vtu_boundary', 'false', '-solver_rank_report',
                                    '-fsi_threads', args.omp_threads,
                                    *flags], run_dir/'solver.log', row)
                assembly.require(hashes == file_receipts(case.parent.iterdir(), work) and
                                 partition_files == file_receipts(partition.iterdir(), work), 'Inputs changed during run')
                trace = assembly.history(output.with_suffix('.csv'), args.steps, cfg['fsi']['dt'])
                row.update(multigrid.audit(text, trace, ranks, mode))
                execution = assembly.records(text, 'fsi_execution_plan ')
                assembly.require(execution and all(int(plan['threads_requested']) == args.omp_threads
                                                   for plan in execution),
                                 'FSI execution reports a different OpenMP thread count')
                row['placement'] = rank_placement(text, ranks, args.steps, args.minimum_nodes)
                assembly.require(row['dofs'] >= args.minimum_dofs, ('Observed DoFs below required minimum', row['dofs']))
                row['dofs_per_rank'] = row['dofs']/ranks
                row['saved_fields'] = spool_fields(output, ranks, run_dir/'fields.sqlite')
                field_db = run_dir/'fields.sqlite'
                # Also check the last timestep snapshot against the final
                # result, so final writer state cannot silently replace it.
                saved_output = output.with_stem(output.stem + f'_step{args.steps}')
                spool_fields(saved_output, ranks, run_dir/'last-step.sqlite')
                row['final_snapshot_difference'] = compare_spools(field_db, run_dir/'last-step.sqlite')
                if label == 'reference':
                    local_reference = field_db, trace, row['nnz']
                    if n in references:
                        row['cross_partition_field_difference'] = compare_spools(references[n][0], field_db)
                        multigrid.previous.compare_history(references[n][1], trace)
                    else:
                        references[n] = field_db, trace
                assembly.require(local_reference is not None, 'No successful same-equation reference')
                row['field_max_difference'] = compare_spools(local_reference[0], field_db)
                row['history_max_difference'] = multigrid.previous.compare_history(local_reference[1], trace)
                if 'reduced' in multigrid.features(mode) and 'reduced' not in multigrid.features(args.reference_mode):
                    assembly.require(0 < row['nnz'] < local_reference[2], 'Reduced P retained full reference graph')
                    row['preconditioner_nnz_ratio'] = row['nnz']/local_reference[2]
                row['artifacts'] = file_receipts(run_dir.iterdir(), work)
                row['status'] = 'passed'
            except Exception as exc:
                row.update(status='failed', error=str(exc))
                result['failures'].append(dict(subdivisions=n, ranks=ranks, mode=mode, label=label, error=str(exc)))
            save(result, receipt)
            print('fsi_large_scaling_run', json.dumps({key: row[key] for key in
                  ('mode', 'label', 'status', 'wall_seconds', 'dofs', 'outer_iterations', 'error') if key in row}), flush=True)
            return row

        if run(args.reference_mode, 'reference', False)['status'] == 'passed':
            passed = [mode for mode in args.modes if run(mode, 'warmup-'+mode, False)['status'] == 'passed']
            failed = set()
            for repeat in range(args.timing_repeats):
                for mode in (passed if repeat % 2 == 0 else list(reversed(passed))):
                    if mode not in failed and run(mode, f'timing-{repeat+1}-{mode}', True)['status'] != 'passed':
                        failed.add(mode)
            for mode in passed:
                samples = [row for row in record['runs'] if row['mode'] == mode and row['timing_sample']]
                if samples and len(samples) == args.timing_repeats and all(row['status'] == 'passed' for row in samples):
                    record['medians'][mode] = {key: assembly.stats([row[key] for row in samples]) for key in
                        ('wall_seconds', 'linear_seconds', 'solve_seconds', 'assembly_seconds', 'outer_iterations',
                         'iterations_per_correction', 'peak_rss_max_bytes')}
                    rss_key = 'local_job_peak_sampled_rss_bytes'
                    if all(row.get(rss_key) is not None for row in samples):
                        record['medians'][mode][rss_key] = assembly.stats([row[rss_key] for row in samples])
        record['status'] = 'passed' if all(row['status'] == 'passed' for row in record['runs']) else 'failed'
        save(result, receipt)
    for mode in args.modes:
        groups = ([record for record in result['cases'] if record['subdivisions'] == n] for n in args.subdivisions) if args.campaign == 'strong' else [result['cases']]
        for group in groups:
            measured = [record for record in group if mode in record['medians']]
            if not measured:
                continue
            first = measured[0]
            first_wall = first['medians'][mode]['wall_seconds']['median']
            first_run = next(row for row in first['runs'] if row['mode'] == mode and row['timing_sample'])
            for record in measured:
                observed = next(row for row in record['runs'] if row['mode'] == mode and row['timing_sample'])
                wall = record['medians'][mode]['wall_seconds']['median']
                load_ratio = observed['dofs_per_rank']/first_run['dofs_per_rank']
                result['scaling'].append(dict(mode=mode, subdivisions=record['subdivisions'], ranks=record['ranks'],
                    nodes=observed['placement']['nodes'], dofs=observed['dofs'], dofs_per_rank=observed['dofs_per_rank'],
                    workload_per_rank_ratio=load_ratio, throughput_dofs_per_second=observed['dofs']/wall,
                    speedup=first_wall/wall if args.campaign == 'strong' else None,
                    efficiency=(first_wall/wall)/(record['ranks']/first['ranks']) if args.campaign == 'strong' else first_wall/wall,
                    weak_load_comparable=abs(load_ratio-1) <= args.weak_load_tolerance if args.campaign == 'weak' else None,
                    iteration_ratio=record['medians'][mode]['iterations_per_correction']['median'] /
                                    first['medians'][mode]['iterations_per_correction']['median']))
    passed_runs = [row for record in result['cases'] for row in record['runs'] if row['status'] == 'passed']
    result['observed_scale'] = dict(maximum_dofs=max((row['dofs'] for row in passed_runs), default=0),
                                   maximum_nodes=max((row['placement']['nodes'] for row in passed_runs), default=0),
                                   million_dof_multinode_runs=sum(row['dofs'] >= 1000000 and row['placement']['nodes'] > 1 for row in passed_runs))
    assembly.require(assembly.digest(executable) == result['executable_sha256'], 'Executable changed during campaign')
    result['status'] = 'failed' if result['failures'] else 'passed'
    save(result, receipt)
    print('fsi_large_scaling_receipt', receipt, result['status'], flush=True)
    return int(bool(result['failures']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--build-source', required=True,
                        help='Actual source commit used to build this executable')
    parser.add_argument('--mpiexec', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--campaign', choices=('bounded', 'strong', 'weak'), default='bounded')
    parser.add_argument('--subdivisions', type=int, nargs='+', default=[4, 6, 8])
    parser.add_argument('--ranks', type=int, nargs='+', default=[1, 2])
    parser.add_argument('--modes', choices=(*MODES, *multigrid.MODES), nargs='+')
    parser.add_argument('--reference-mode', choices=('direct', *multigrid.MODES), default='mono',
                        help='Large campaign baseline: same-equation iterative mono by default')
    parser.add_argument('--mpi-arg', action='append', default=[],
                        help='One MPI launcher argument, repeat as --mpi-arg=--hostfile --mpi-arg=/path')
    parser.add_argument('--omp-threads', type=int, default=1,
                        help='FSI element threads per rank on strong/weak campaigns; bind MPI ranks to enough cores')
    parser.add_argument('--local-rss-interval', type=float,
                        help='Seconds between local process RSS samples; rank/launcher RSS may double-count shared pages')
    parser.add_argument('--local-rss-limit-gib', type=float,
                        help='Terminate a single-node command if sampled local RSS exceeds this GiB budget')
    parser.add_argument('--minimum-nodes', type=int, default=1,
                        help='Require this many distinct observed MPI host names for every large run')
    parser.add_argument('--minimum-dofs', type=int, default=0,
                        help='Require this many actual constrained solver DoFs for every large run')
    parser.add_argument('--weak-load-tolerance', type=float, default=.1,
                        help='Maximum relative observed DoF/rank drift to label weak loads comparable')
    parser.add_argument('--steps', type=int, default=5)
    parser.add_argument('--timing-repeats', type=int, default=0)
    parser.add_argument('--timeout', type=float, default=180.)
    args = parser.parse_args()
    if args.modes is None:
        args.modes = list(MODES) if args.campaign == 'bounded' else ['mono_mf']
    if (args.subdivisions != sorted(set(args.subdivisions)) or
            any(n < 2 for n in args.subdivisions)):
        parser.error('Use ascending unique subdivisions >= 2')
    if args.ranks != sorted(set(args.ranks)) or any(n < 1 for n in args.ranks):
        parser.error('Use ascending unique positive MPI ranks')
    if args.campaign == 'bounded' and (any(n not in (1, 2, 4) for n in args.ranks) or any(mode not in MODES for mode in args.modes)):
        parser.error('The bounded study uses ranks 1/2/4 and block presets; select --campaign strong/weak for MG/large studies')
    if args.campaign != 'bounded' and any(mode not in multigrid.MODES for mode in args.modes):
        parser.error('Strong/weak studies use the physical multigrid presets')
    if args.campaign == 'weak' and len(args.subdivisions) != len(args.ranks):
        parser.error('Weak scaling requires one ascending subdivision value per rank count')
    if args.minimum_nodes < 1 or args.minimum_dofs < 0 or not math.isfinite(args.weak_load_tolerance) or args.weak_load_tolerance < 0:
        parser.error('Minimum nodes must be positive; DoFs and finite weak-load tolerance must be nonnegative')
    if args.campaign == 'bounded' and (args.mpi_arg or args.minimum_nodes != 1 or args.minimum_dofs != 0):
        parser.error('Cluster launcher/qualification options require --campaign strong or weak')
    if not 1 <= args.omp_threads <= 256:
        parser.error('--omp-threads must be in [1, 256]')
    if args.campaign == 'bounded' and (args.omp_threads != 1 or args.local_rss_interval is not None
                                        or args.local_rss_limit_gib is not None):
        parser.error('OpenMP and local RSS options require --campaign strong or weak')
    args.local_rss_limit_bytes = None
    if args.local_rss_interval is not None and (not math.isfinite(args.local_rss_interval)
                                                or args.local_rss_interval <= 0):
        parser.error('--local-rss-interval must be finite and positive')
    if args.local_rss_limit_gib is not None:
        if (args.minimum_nodes != 1 or not math.isfinite(args.local_rss_limit_gib)
                or not 2**-30 <= args.local_rss_limit_gib < 2**33):
            parser.error('--local-rss-limit-gib must specify a positive byte budget for a single-node job')
        args.local_rss_limit_bytes = int(args.local_rss_limit_gib * 2**30)
        if args.local_rss_interval is None:
            args.local_rss_interval = 0.5
    if (len(set(args.modes)) != len(args.modes) or args.steps < 1 or
            not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error('Modes must be unique and steps/timeout positive')
    if not re.fullmatch('[0-9a-f]{40}', args.build_source):
        parser.error('--build-source must name the actual full 40-character build commit')
    if args.timing_repeats not in (0,) and args.timing_repeats < 3:
        parser.error('Use zero timing repeats or at least three')
    executable, mpiexec = args.executable.resolve(), args.mpiexec.resolve()
    assembly.require(executable.is_file() and mpiexec.is_file(), 'Missing executable or MPI launcher')
    if args.campaign != 'bounded':
        return large_campaign(args)
    environment = dict(OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', OPENBLAS_NUM_THREADS='1',
                       MKL_NUM_THREADS='1', OMPI_MCA_pml='ob1', OMPI_MCA_btl='self,sm,tcp')
    os.environ.update(environment)
    work = args.work.resolve() / str(time.time_ns())
    work.mkdir(parents=True)
    receipt = work / 'results.json'
    result = dict(status='running', output_directory=str(work), build_source=args.build_source,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                        text=True).strip(),
                  executable=str(executable), executable_sha256=assembly.digest(executable),
                  script_sha256=assembly.digest(__file__),
                  helper_sha256={str(path.relative_to(ROOT)): assembly.digest(path) for path in
                                 (ROOT / 'cases/fsi/generate_domains.py',
                                  ROOT / 'scripts/benchmark_fsi_assembly.py',
                                  ROOT / 'tests/verify_fsi_block_efficiency.py')},
                  environment=environment, cpu_affinity=sorted(os.sched_getaffinity(0)),
                  steps=args.steps, timing_repeats=args.timing_repeats,
                  per_command_timeout_seconds=args.timeout, modes=['direct', *args.modes],
                  linear_gate='1e-12 + 1e-10 * rhs_norm',
                  field_absolute_limit=assembly.FIELD_LIMIT, cases=[], failures=[])
    save(result, receipt)

    def run_command(command, log, row):
        row['command'] = list(map(str, command))
        row['log'] = str(log)
        try:
            return block.timed_command(command, log, args.timeout, row)
        finally:
            if log.is_file():
                row['log_sha256'] = assembly.digest(log)

    for n in args.subdivisions:
        case = assembly.generate(work / f'n{n}-input', n)
        config = json.loads(case.read_text())
        config['fsi'].update(steps=args.steps, output_interval=1)
        case.write_text(json.dumps(config, indent=2) + '\n')
        hashes = {path.name: assembly.digest(path) for path in case.parent.iterdir() if path.is_file()}
        for ranks in args.ranks:
            directory = work / f'n{n}-r{ranks}'
            directory.mkdir()
            partition = directory / 'partition'
            record = dict(subdivisions=n, ranks=ranks, input=str(case), config=config,
                          input_sha256=hashes, partition=str(partition), runs=[], medians={})
            result['cases'].append(record)
            preparation = {}
            record['preparation'] = preparation
            try:
                run_command([executable, '-case', case, '-prepare', partition, '-parts', ranks],
                            directory / 'prepare.log', preparation)
                preparation['evidence'] = assembly.partition_evidence(partition, ranks, work)
            except Exception as exc:
                record['status'] = 'failed'
                result['failures'].append(dict(subdivisions=n, ranks=ranks, mode='prepare', error=str(exc)))
                save(result, receipt)
                continue
            reference_fields = reference_history = None

            def run(mode, label, timing):
                nonlocal reference_fields, reference_history
                run_directory = directory / label
                run_directory.mkdir()
                output = run_directory / 'solution.vtu'
                row = dict(mode=mode, label=label, timing_sample=timing, status='running',
                           flags=block.flags(mode, 'rcm'), output=str(output))
                record['runs'].append(row)
                try:
                    assembly.require({path.name: assembly.digest(path) for path in case.parent.iterdir()
                                      if path.is_file()} == hashes, 'Case input changed before a run')
                    assembly.check_partition_unchanged(preparation['evidence'], work)
                    text = run_command([mpiexec, '--map-by', 'core', '--bind-to', 'core',
                                        '-n', ranks, executable, '-case', case, '-partition', partition,
                                        '-output', output, '-solver_report', '-linear_report', '-pc_plan_report',
                                        *row['flags']], run_directory / 'solver.log', row)
                    assembly.require({path.name: assembly.digest(path) for path in case.parent.iterdir()
                                      if path.is_file()} == hashes, 'Case input changed during a run')
                    assembly.check_partition_unchanged(preparation['evidence'], work)
                    checked = assembly.parse_log(text, args.steps, ranks, config['fsi']['dt'],
                                                 solver_kind(mode))
                    row.update(checked)
                    row.update(hierarchy(text, mode, ranks, args.steps))
                    fields = [assembly.physical_fields(output.with_stem(output.stem + f'_step{step}'), ranks)
                              for step in range(1, args.steps + 1)]
                    final = assembly.physical_fields(output, ranks)
                    delta = assembly.compare_fields(fields[-1], final)
                    history = assembly.history(output.with_suffix('.csv'), args.steps, config['fsi']['dt'])
                    # Different preconditioners may change Newton work. Keep
                    # every physical/history scalar at the original 2e-9 gate
                    # and record iteration counts separately as measurements.
                    history = [{key: value for key, value in step.items() if key != 'snes_iterations'}
                               for step in history]
                    if mode == 'direct':
                        reference_fields, reference_history = fields, history
                    assembly.require(reference_fields is not None, 'Direct reference has not passed')
                    row['field_max_delta'] = max(delta, *(assembly.compare_fields(x, y)
                        for x, y in zip(reference_fields, fields)))
                    row['history_max_delta'] = assembly.compare_history(reference_history, history)
                    row['dofs'] = int(checked['steps'][0]['dofs'])
                    row['nnz'] = max(step['nnz'] for step in checked['steps'])
                    row['outer_iterations'] = sum(step['linear_iterations'] for step in checked['steps'])
                    row['newton_iterations'] = sum(step['snes_iterations'] for step in checked['steps'])
                    for name in assembly.TIMERS:
                        row[name] = sum(step[name] for step in checked['steps'])
                    for name in ('peak_rss_max_bytes', 'peak_rss_sum_bytes'):
                        row[name] = max(step[name] for step in checked['steps'])
                    if mode.endswith('_adaptive'):
                        for step in checked['steps']:
                            assembly.require(int(step['pc_refreshes']) + int(step['pc_reuses']) ==
                                             step['linear_completed'], 'Unaccounted adaptive correction')
                        for name in PC_COUNTERS:
                            row[name] = sum(int(step[name]) for step in checked['steps'])
                    row['artifacts'] = [dict(path=str(path), sha256=assembly.digest(path),
                                             bytes=path.stat().st_size)
                                        for path in sorted(run_directory.iterdir()) if path.is_file()]
                    row['status'] = 'passed'
                except Exception as exc:
                    row.update(status='failed', error=str(exc))
                    result['failures'].append(dict(subdivisions=n, ranks=ranks, mode=mode,
                                                   label=label, error=str(exc)))
                save(result, receipt)
                print('fsi_block_scaling_run', json.dumps({key: row[key] for key in
                      ('mode', 'label', 'status', 'wall_seconds', 'dofs', 'outer_iterations',
                       'linear_seconds', 'first_coarse_dimension', 'auxiliary_gamg_levels',
                       'pc_refreshes', 'pc_reuses', 'field_max_delta', 'max_linear_residual_ratio',
                       'error') if key in row}, allow_nan=False), flush=True)
                return row

            if run('direct', 'reference-direct', False)['status'] != 'passed':
                record['status'] = 'failed'
                save(result, receipt)
                continue
            passed = [mode for mode in args.modes if run(mode, 'warmup-' + mode, False)['status'] == 'passed']
            failed_timing = set()
            for repeat in range(args.timing_repeats):
                sequence = passed if repeat % 2 == 0 else list(reversed(passed))
                for mode in sequence:
                    if mode not in failed_timing and run(mode, f'timing-{repeat + 1}-{mode}', True)['status'] != 'passed':
                        failed_timing.add(mode)
            for mode in passed:
                samples = [row for row in record['runs'] if row['mode'] == mode and row['timing_sample']]
                if len(samples) == args.timing_repeats and samples and all(row['status'] == 'passed' for row in samples):
                    record['medians'][mode] = dict(samples=len(samples), **{key: assembly.stats(
                        [row[key] for row in samples]) for key in
                        ('wall_seconds', 'outer_iterations', *assembly.TIMERS,
                         'peak_rss_max_bytes', 'peak_rss_sum_bytes')})
            record['status'] = 'passed' if all(row['status'] == 'passed' for row in record['runs']) else 'failed'
            save(result, receipt)
    if assembly.digest(executable) != result['executable_sha256']:
        result['failures'].append(dict(error='Executable changed during study'))
    result['status'] = 'failed' if result['failures'] else 'passed'
    save(result, receipt)
    print('fsi_block_scaling_summary', json.dumps(dict(status=result['status'], results=str(receipt),
                                                     failures=result['failures'])), flush=True)
    return 1 if result['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
