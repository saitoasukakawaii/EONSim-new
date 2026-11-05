import json
from pathlib import Path
import subprocess
import sys
import time

root = Path.cwd()
work = Path('/home/tfblab633/EONSim-next03-20261105')
logs = root / 'build/resume-20261105'
common = ['--executable', str(root / 'build/cloud-3.23.7-release/eonsim'),
          '--mpiexec', '/home/tfblab633/EONSim/.cloud/petsc-3.23.7/bin/mpiexec']
records = []

def run(label, script, args):
    command = [sys.executable, str(root / 'scripts' / script), *args]
    log = logs / (label + '.log')
    if log.exists():
        raise RuntimeError('Preserve the earlier attempt before retrying: ' + str(log))
    print('START ' + label, flush=True)
    start = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    records.append(dict(label=label, command=command, exit_code=result.returncode,
                        seconds=time.monotonic()-start, log=str(log)))
    temporary = logs / 'matrix-status.tmp'
    temporary.write_text(json.dumps(records, indent=2) + '\n')
    temporary.replace(logs / 'matrix-status.json')
    print('END ' + label + ' exit=' + str(result.returncode), flush=True)
    if result.returncode:
        raise RuntimeError('Study failed; preserved evidence: ' + str(log))

run('replay-restored-n2', 'study_fsi_checkpoint_replay.py',
    [*common, '--source', str(work/'fixed-n2-dt001'), '--work', str(work/'replay-n2')])

cases = []
for n in (2, 4, 8):
    for dt, suffix in (('.001', '001'), ('.0005', '0005')):
        label = f'fixed-n{n}-dt{suffix}'
        source = work / label
        if n != 2:
            run(label, 'study_fsi_periodic.py',
                [*common, '--work', str(source), '--n', str(n), '--dt', dt, '--cycles', '240'])
        receipt = json.loads((source/'periodic-result.json').read_text())
        if not receipt['converged']:
            raise RuntimeError('Missing converged periodic state: ' + label)
        for kind, script in [('tail', 'study_fsi_transient_tail.py'),
                             ('sampling', 'study_fsi_phase_sampling.py')]:
            run(kind+'-'+label, script, [*common, '--source', str(source),
                '--work', str(work/(kind+'-'+label))])
        run('archive-'+label, 'archive_fsi_periodic.py',
            ['--work', str(source), '--output', str(logs/(label+'.tar.gz'))])
        cases.append(source)

arguments = ['--policy', 'fixed', '--output', str(logs/'fixed-budget.json')]
for name, suffix, kind, receipt in [
    ('space-cases','001','',None), ('time-cases','0005','',None),
    ('transient-results','001','tail-','transient-result.json'),
    ('sampling-results','001','sampling-','sampling-result.json'),
    ('time-transient-results','0005','tail-','transient-result.json'),
    ('time-sampling-results','0005','sampling-','sampling-result.json')]:
    paths = [work / (kind+f'fixed-n{n}-dt{suffix}') for n in (2,4,8)]
    arguments += ['--'+name, *[str(p/receipt if receipt else p) for p in paths]]
run('fixed-budget','analyze_fsi_error_budget.py', arguments)
