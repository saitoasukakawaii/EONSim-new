"""Exercise the historical comparison and direct self-comparison on an isolated A fixture."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('binary',type=Path)
    cli.add_argument('reference',type=Path)
    cli.add_argument('output',type=Path)
    args = cli.parse_args()
    gate = args.output/'fixture'
    gate.mkdir(parents=True,exist_ok=False)
    original = Path.home()/'workspace/fsi-scalable-02-runs/A20-batch'
    for name in ('0-eon','prepared/eon'):
        shutil.copytree(original/name,gate/name)
    shutil.copyfile(original/'summary.json',gate/'summary.json')
    # Only the copied, unaudited historical trajectory is perturbed.
    path = gate/'0-eon/tube.csv'
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    rows[-1]['stage_rcr_pressure'] = str(float(rows[-1]['stage_rcr_pressure'])+1)
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    root = args.output/'screen'
    script = Path(__file__).resolve().parents[1]/'fsi-scalable-02/screen_tube.py'
    subprocess.run([sys.executable,str(script),'--gate',str(gate),'--root',str(root),'--binary',
                    str(args.binary),'--ranks','4','--mpiexec','/opt/software/openmpi-4.1.8-gcc-11.5.0/bin/mpiexec',
                    '--audited-direct-reference',str(args.reference),'--modes','direct','asm'],check=True)
    result = json.loads((root/'summary.json').read_text())
    if (not result['passed'] or 'historical_comparison_error' not in result['reference']
            or [r['status'] for r in result['runs']] != ['diagnostic_same_solver','passed']):
        raise RuntimeError('Incorrect strict-reference or self-comparison status')
    print('reference regression passed job='+os.environ['SLURM_JOB_ID'])


if __name__=='__main__':
    main()
