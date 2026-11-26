"""Paired offline partition and isolated VTU-mode measurements.

Run only after this driver and solver sources have been pushed. HDF5 datasets,
topology/IDs and all saved fields are correctness gates; timing is evidence.
One warmup precedes three alternating measured pairs. Keep every raw output.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'cases/poisson'), str(ROOT / 'tests')]
from generate_mesh import write_mesh
from verify_poisson import read_piece, compare_piece_arrays, compare_boundary, compare_boundary_arrays


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    return dict(median=statistics.median(values), minimum=min(values), maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'mpiexec', 'h5diff', 'work'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('baseline', 'candidate'):
        parser.add_argument('--'+name+'-commit', required=True)
    parser.add_argument('--subdivisions', type=int, default=24)
    parser.add_argument('--parts', type=int, nargs='+', default=[2, 8, 32])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--stage', choices=('all', 'partition', 'output'), default='all',
                        help='Select an independent stage; preserve earlier evidence when fixing an output-only validator')
    args = parser.parse_args()
    require(args.repeats >= 3 and args.subdivisions >= 4, 'Need three pairs and a nontrivial grid')
    require(args.parts == sorted(set(args.parts)) and 2 in args.parts and
            all(2 <= n <= 128 for n in args.parts), 'Parts must be unique, ascending, include 2, and be <=128')
    require(all(re.fullmatch('[0-9a-f]{40}', getattr(args, m+'_commit')) for m in ('baseline', 'candidate')),
            'Build source commits must be full SHAs')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    binaries = {m: getattr(args, m).resolve() for m in ('baseline', 'candidate')}
    require(all(p.is_file() for p in binaries.values()), 'Missing executable')
    result = dict(status='running', driver_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), driver_sha256=sha(__file__),
        driver_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        binaries={m: dict(path=str(p), source=getattr(args, m+'_commit'), sha256=sha(p))
                  for m, p in binaries.items()}, subdivisions=args.subdivisions,
        nodes=(args.subdivisions+1)**3, cells=6*args.subdivisions**3, repeats=args.repeats, stage=args.stage,
        commands=[], partition_runs=[], output_runs=[], partition_pairs=[], output_pairs=[],
        method='One warmup, alternating measured pairs; blocking wait with independent watchdog. '
               'Output timer is maximum-rank application write time; wall includes solve/startup/shutdown. '
               'Output modes share the candidate binary and identical partition/physics/solver options.')
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')

    def save():
        (work/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')

    def run(command, label, success=True, timeout=300):
        record = dict(command=list(map(str, command)), log=label+'.log', returncode=None, timeout=False)
        result['commands'].append(record)
        begin = time.perf_counter()
        expired = threading.Event()
        with (work/record['log']).open('w') as stream:
            process = subprocess.Popen(record['command'], env=env, cwd=ROOT, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)

            def terminate():
                if process.poll() is not None:
                    return
                expired.set()
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            watchdog = threading.Timer(timeout, terminate)
            watchdog.daemon = True
            watchdog.start()
            try:
                record['returncode'] = process.wait()
            except BaseException:
                terminate()
                process.wait()
                raise
            finally:
                watchdog.cancel()
                watchdog.join()
                record['seconds'] = time.perf_counter()-begin
                record['timeout'] = expired.is_set()
                save()
        text = (work/record['log']).read_text()
        require(record['returncode'] == 0 and not record['timeout'], ('Command failed', record))
        if success:
            require(text.splitlines().count('status=success') == 1, ('Missing unique success', label))
        return record['seconds'], text

    try:
        for name, command in [('mpi', [args.mpiexec, '--version']),
                              ('hdf5', [args.h5diff, '--version']), ('host', ['uname', '-a'])]:
            run(command, name, success=False)
        result['cpu_affinity'] = sorted(os.sched_getaffinity(0))
        result['cgroup'] = Path('/proc/self/cgroup').read_text()
        result['limits'] = {n: (Path('/sys/fs/cgroup')/n).read_text().strip()
                            for n in ('cpu.max', 'memory.max') if (Path('/sys/fs/cgroup')/n).exists()}
        mesh, case = work/'cube.msh', work/'case.yaml'
        write_mesh(mesh, args.subdivisions, warp=True, id_offset=5_000_000_000)
        case.write_text((ROOT/'cases/poisson/case.yaml').read_text().replace('mesh: cube.msh', 'mesh: '+str(mesh)))
        result['inputs'] = {p.name: sha(p) for p in (case, mesh)}
        shared_partition = None
        for parts in (args.parts if args.stage != 'output' else []):
            for repeat in range(-1, args.repeats):
                pair = {}
                for mode in (('baseline', 'candidate') if repeat % 2 else ('candidate', 'baseline')):
                    label = f'prepare-p{parts}-sample{repeat}-{mode}'
                    directory = work/label
                    wall, _ = run([binaries[mode], '-case', case, '-prepare', directory, '-parts', parts], label)
                    row = dict(parts=parts, repeat=repeat, mode=mode, wall_seconds=wall, directory=label,
                               bytes=sum(p.stat().st_size for p in directory.iterdir() if p.is_file()))
                    result['partition_runs'].append(row)
                    pair[mode] = row
                first, second = (work/pair[m]['directory'] for m in ('baseline', 'candidate'))
                files = sorted(p.name for p in first.iterdir() if p.is_file())
                require(files == sorted(p.name for p in second.iterdir() if p.is_file()), 'Partition file sets differ')
                for filename in files:
                    if filename.endswith('.h5'):
                        run([args.h5diff, first/filename, second/filename],
                            f'h5diff-p{parts}-sample{repeat}-{filename}', success=False)
                    else:
                        require((first/filename).read_bytes() == (second/filename).read_bytes(),
                                ('Partition metadata changed', filename))
                if parts == 2 and shared_partition is None:
                    shared_partition = first
                if repeat >= 0:
                    result['partition_pairs'].append(dict(parts=parts, repeat=repeat,
                        relative_wall_change=pair['candidate']['wall_seconds']/pair['baseline']['wall_seconds']-1))
                save()
            run([binaries['candidate'], '-case', case, '-prepare', work/f'profile-p{parts}',
                 '-parts', parts, '-partition_report'], f'profile-p{parts}')
        formats = {
            'ascii_full': ['-vtu_compact_boundary', 'false'],
            'ascii_compact': [],
            'binary_compact': ['-vtu_format', 'binary'],
            'binary_volume': ['-vtu_format', 'binary', '-vtu_boundary', 'false'],
        }
        if args.stage == 'output':
            # One setup-only shared prepare supplies the two-rank output comparison;
            # do not repeat the already completed partition timing campaign.
            shared_partition = work/'output-partition'
            run([binaries['baseline'], '-case', case, '-prepare', shared_partition, '-parts', 2],
                'output-prepare')
        for ranks in ((1, 2) if args.stage != 'partition' else []):
            reference = None
            boundary_reference = None
            for repeat in range(-1, args.repeats):
                pair = {}
                order = list(formats)
                if repeat % 2 == 0:
                    order.reverse()
                for mode in order:
                    label = f'output-r{ranks}-sample{repeat}-{mode}'
                    output = work/(label+'.vtu')
                    command = [args.mpiexec, '-n', ranks, binaries['candidate'], '-case', case, '-output', output]
                    if ranks > 1:
                        command += ['-partition', shared_partition]
                    wall, text = run([*command, *formats[mode]], label)
                    values = {k: float(v) for k, v in re.findall(r'\b([a-z][a-z0-9_]*)=([-+0-9.eE]+)(?=\s|$)', text)}
                    require(all(math.isfinite(v) for v in values.values()), 'Nonfinite output metric')
                    require(values['true_residual'] <= max(values['atol'], values['rtol']*values['rhs_norm']),
                            'Output mode changed numerical acceptance')
                    reasons = re.findall(r'\bksp=\S+ pc=\S+ reason=(\S+) iterations=\d+', text)
                    require(len(reasons) == 1 and reasons[0].startswith('CONVERGED_'),
                            'Missing or nonconverged Poisson KSP reason')
                    require(values['nodes'] == result['nodes'] and
                            values['cells'] == result['cells'], 'Invalid solved size/convergence')
                    pieces, boundaries = [], []
                    for rank in range(ranks):
                        path = output if ranks == 1 else output.with_stem(output.stem+f'_rank{rank}')
                        piece = read_piece(path)
                        require(piece['binary'] == mode.startswith('binary'), 'Requested encoding not used')
                        pieces.append(piece)
                        boundary_path = path.with_stem(path.stem+'_boundary')
                        if mode == 'binary_volume':
                            require(not boundary_path.exists(), 'Disabled boundary piece exists')
                        else:
                            boundary = read_piece(boundary_path)
                            require(boundary['binary'] == piece['binary'], 'Boundary encoding differs')
                            compare_boundary(piece, boundary, compact=mode != 'ascii_full')
                            boundaries.append(boundary)
                    if reference is None:
                        reference = pieces
                    for first, second in zip(reference, pieces):
                        compare_piece_arrays(first, second)
                    if boundaries:
                        if boundary_reference is None:
                            boundary_reference = boundaries
                        for first, second in zip(boundary_reference, boundaries):
                            compare_boundary_arrays(first, second)
                    if ranks > 1:
                        require(output.with_suffix('.pvtu').is_file(), 'Missing volume index')
                        require(output.with_stem(output.stem+'_boundary').with_suffix('.pvtu').exists() ==
                                (mode != 'binary_volume'), 'Boundary index disagrees with mode')
                    files = sorted(p for p in work.glob(label+'*') if p.suffix in ('.vtu', '.pvtu'))
                    row = dict(ranks=ranks, repeat=repeat, mode=mode, wall_seconds=wall,
                        output_seconds=values['output'], iterations=values['iterations'],
                        convergence_reason=reasons[0],
                        true_residual=values['true_residual'], bytes=sum(p.stat().st_size for p in files),
                        files=[dict(path=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in files])
                    pair[mode] = row
                    result['output_runs'].append(row)
                    save()
                if repeat >= 0:
                    for mode in formats:
                        if mode == 'ascii_full':
                            continue
                        result['output_pairs'].append(dict(ranks=ranks, repeat=repeat, mode=mode,
                            relative_change={k: pair[mode][k]/pair['ascii_full'][k]-1
                                             for k in ('wall_seconds', 'output_seconds', 'bytes')}))
                save()
        result['partition_summary'] = [dict(parts=p,
            modes={m: stats([r['wall_seconds'] for r in result['partition_runs']
                            if r['parts'] == p and r['mode'] == m and r['repeat'] >= 0]) for m in binaries},
            relative_wall_change=stats([r['relative_wall_change'] for r in result['partition_pairs'] if r['parts'] == p]))
            for p in sorted({r['parts'] for r in result['partition_runs']})]
        result['output_summary'] = [dict(ranks=r, mode=m,
            absolute={k: stats([x[k] for x in result['output_runs'] if x['ranks'] == r and
                                x['mode'] == m and x['repeat'] >= 0]) for k in ('wall_seconds', 'output_seconds', 'bytes')},
            relative_change={k: stats([x['relative_change'][k] for x in result['output_pairs'] if
                                      x['ranks'] == r and x['mode'] == m]) for k in ('wall_seconds', 'output_seconds', 'bytes')})
            for r in sorted({x['ranks'] for x in result['output_runs']}) for m in formats if m != 'ascii_full']
        require(all(sha(p) == result['binaries'][m]['sha256'] for m,p in binaries.items()), 'Binary changed during campaign')
        result['status'] = 'passed'
        print(json.dumps({k: result[k] for k in ('status', 'partition_summary', 'output_summary')}, indent=2))
    except BaseException as error:
        result['status'], result['error'] = 'failed', str(error)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
