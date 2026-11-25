"""Record the executable and MPI launcher exit statuses independently in a new directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def record_rank(directory, command):
    # The wrapper is an ordinary rank-local parent. A solver that calls MPI_Abort
    # may terminate its parent before the latter can write an exit record.
    rank = int(os.environ.get('OMPI_COMM_WORLD_RANK', '0'))
    code = subprocess.run(command).returncode
    target = directory / f'rank-{rank}.json'
    with target.open('x') as stream:
        json.dump(dict(rank=rank, exit_code=code), stream)
    return code if code >= 0 else 128 - code


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.argv[1:2] == ['rank']:
        return record_rank(Path(sys.argv[2]), sys.argv[3:])
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work', type=Path, required=True)
    cli.add_argument('--mpiexec', type=Path, help='Omit for a singleton process')
    cli.add_argument('--ranks', type=int, default=1)
    cli.add_argument('command', nargs=argparse.REMAINDER, help='Use -- followed by the solver and its arguments')
    args = cli.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.ranks < 1 or (not args.mpiexec and args.ranks != 1):
        cli.error('Specify an executable and a positive rank count supported by this launch')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    executable = Path(command[0]).resolve(strict=True)
    rank_command = [sys.executable, str(Path(__file__).resolve()), 'rank', str(work),
                    str(executable), *command[1:]]
    launcher = []
    if args.mpiexec:
        launcher = [str(args.mpiexec.resolve(strict=True)), '--map-by', 'core', '--bind-to', 'core',
                    '--report-bindings', '-n', str(args.ranks)]
    started = time.monotonic()
    with (work / 'solve.log').open('w') as stream:
        process = subprocess.run(launcher + rank_command, stdout=stream, stderr=stream)
    ranks = [json.loads(p.read_text()) for p in sorted(work.glob('rank-*.json'))]
    ranks.sort(key=lambda row: row['rank'])
    if any(not 0 <= row['rank'] < args.ranks for row in ranks):
        raise ValueError('Exit marker belongs to an unexpected rank')
    log = (work / 'solve.log').read_text(errors='replace').splitlines()
    all_ranks = [row['rank'] for row in ranks] == list(range(args.ranks))
    passed = process.returncode == 0 and all_ranks and all(row['exit_code'] == 0 for row in ranks)
    result = dict(launcher_exit=process.returncode, ranks=ranks, expected_ranks=args.ranks,
                  application_reported_success='status=success' in log, elapsed_seconds=time.monotonic()-started,
                  accepted_steps=sum(line.startswith('fsi_step=') for line in log), clean_exit=passed,
                  executable_sha256=digest(executable), log_sha256=digest(work / 'solve.log'))
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
