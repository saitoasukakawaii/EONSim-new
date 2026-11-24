"""Compare the two-rank periodic signal's field prefix with three completed replays."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(directory, steps):
    return {
        name: sha(directory / name)
        for step in steps
        for solid in ('', '_solid')
        for rank in range(2)
        for boundary in ('', '_boundary')
        for name in [f'direct_step{step}{solid}_rank{rank}{boundary}.vtu']
    }


def manifest_sha(mapping):
    data = json.dumps(mapping, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('failed', 'replays', 'status-log', 'executable', 'ctest', 'output'):
        cli.add_argument('--' + name, type=Path, required=True)
    args = cli.parse_args()
    original = (args.failed / 'direct.log').read_text(errors='replace')
    if 'signal number 11 SEGV' not in original:
        raise ValueError('The recorded failure is not the two-rank signal 11')
    prefix = [int(v) for v in re.findall(r'^fsi_step=(\d+) ', original, re.M)]
    if not prefix or prefix != list(range(1, prefix[-1] + 1)) or prefix[-1] >= 80:
        raise ValueError('The original history does not have a proper contiguous prefix')
    original_fields = fields(args.failed, prefix)
    history = (args.failed / 'direct.csv').read_bytes()
    statuses = dict(re.findall(r' (\S+) rc=(\d+)', args.status_log.read_text()))
    trials = []
    final_digest = None
    for name, code in sorted(statuses.items()):
        directory = args.replays / name
        log = (directory / 'solve.log').read_text(errors='replace')
        cores = dict(re.findall(r'Rank (\d+) bound to .*?core:(\d+)\]', log))
        if cores != {'0': '0', '1': '1'}:
            raise ValueError('Unexpected logical core placement')
        result = dict(name=name, exit_code=int(code), solve_log_sha256=sha(directory / 'solve.log'))
        if name.startswith('sm-'):
            steps = [int(v) for v in re.findall(r'^fsi_step=(\d+) ', log, re.M)]
            if code != '0' or steps != list(range(1, 81)) or 'status=success' not in log:
                raise ValueError('Shared-memory replay was incomplete')
            complete = fields(directory, steps)
            replay_history = (directory / 'direct.csv').read_bytes()
            if (any(complete[k] != v for k, v in original_fields.items())
                    or not replay_history.startswith(history)):
                raise ValueError('A computed field or accepted history differs before the original signal')
            receipt = dict(all_field_sha256=manifest_sha(complete),
                           accepted_history_sha256=sha(directory / 'direct.csv'))
            if final_digest is not None and final_digest != receipt:
                raise ValueError('Completed replays have different fields or histories')
            final_digest = receipt
            result.update(accepted_steps=80, **receipt)
        else:
            if code == '0' or 'MPI_INIT has failed' not in log or 'unreachable' not in log.lower() or 'fsi_step=' in log:
                raise ValueError('Unexpected TCP-only transport result')
            result.update(accepted_steps=0, detail='MPI initialization reported unreachable peer')
        trials.append(result)
    if set(statuses) != {f'{transport}-{suffix}' for transport in ('sm', 'tcp') for suffix in 'abc'}:
        raise ValueError('Missing transport control')
    summary = json.loads(args.ctest.read_text())
    if (summary['status'] != 'passed' or summary['selected_tests'] != ['fsi_periodic']
            or len(summary['tests']) != 1 or summary['tests'][0]['exit_code'] != 0):
        raise ValueError('Targeted CTest did not complete')
    result = dict(problem='fsi_periodic, physical-continuous, direct monolithic solve, 2 ranks',
                  last_accepted_before_signal=prefix[-1], original_signal=11, original_rank=0,
                  original_log_sha256=sha(args.failed / 'direct.log'), executable_sha256=sha(args.executable),
                  case_sha256=sha(args.failed / 'direct.json'),
                  partition_sha256={f.name:sha(f) for f in sorted((args.failed / 'part-2').iterdir()) if f.is_file()},
                  matching_prefix_field_files=len(original_fields), prefix_field_sha256=manifest_sha(original_fields),
                  original_history_prefix_bytes=len(history), original_history_prefix_sha256=hashlib.sha256(history).hexdigest(),
                  replays=trials, final_targeted_ctest=summary['tests'][0], targeted_summary_sha256=sha(args.ctest))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
