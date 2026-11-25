"""Regenerate the tube and junction comparison tables and verify their published bytes."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

DATA = Path(__file__).resolve().parents[1]
TUBE = DATA/'fsi-linear-transient-2026-11-24'
JUNCTION = DATA/'fsi-rcr-2026-11-24'
STUDIES = (
    (TUBE, 'compare_arterial_ksp.py', 'arterial-solvers.json.xz', {'--csv': 'arterial-solvers.csv'}),
    (TUBE, 'compare_bipn_residual.py', 'bipn-residual.json.xz', {'--csv': 'bipn-residual.csv'}),
    (TUBE, 'compare_scaled.py', 'scaled-tubes.json.xz', {'--csv': 'scaled-tubes.csv'}),
    (TUBE, 'compare_tet_order.py', 'tet-order.json.xz',
     {'--sv-csv': 'tet-order-svfsi.csv', '--eon-csv': 'tet-order-eonsim.csv'}),
    (TUBE, 'compare_perfusion.py', 'perfused-tube.json.xz',
     {'--meridian-csv': 'perfused-meridian.csv', '--solver-csv': 'perfused-solvers.csv',
      '--pairs-csv': 'perfused-pairs.csv', '--forward-csv': 'perfused-forward.csv'}),
    (TUBE, 'compare_harmonic.py', 'harmonic.json.xz',
     {'--meridian-csv': 'harmonic-meridian.csv', '--eon-csv': 'harmonic-eon.csv'}),
    (TUBE, 'compare_time_scales.py', 'time-scales.json.xz', {'--csv': 'time-scales.csv'}),
    (JUNCTION, 'compare_junction_harmonic.py', 'junction-harmonic.json.xz',
     {'--reference-csv': 'junction-admittance.csv', '--solver-csv': 'junction-periodic.csv',
      '--startup-csv': 'junction-startup.csv'}),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(directory, reader, archive, outputs, env):
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        cmd = [sys.executable, str(directory/reader), '--archive', str(directory/archive)]
        for option, name in outputs.items():
            cmd.extend([option, str(work/name)])
        subprocess.run(cmd, cwd=work, env=env, check=True)
        tables = {}
        for name in outputs.values():
            generated = work/name
            if generated.read_bytes() != (directory/name).read_bytes():
                raise ValueError(f'Regenerated table differs from {directory.name}/{name}')
            with generated.open(newline='') as stream:
                tables[name] = dict(sha256=sha(generated), rows=sum(1 for _ in csv.DictReader(stream)))
        return dict(script=reader, script_sha256=sha(directory/reader), archive=archive,
                    archive_sha256=sha(directory/archive), tables=tables)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, help='Write hashes and row counts for all verified tables')
    args = parser.parse_args()
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    runs = [replay(*study, env) for study in STUDIES]
    count = sum(len(run['tables']) for run in runs)
    rows = sum(table['rows'] for run in runs for table in run['tables'].values())
    if args.receipt:
        result = dict(archives=len(runs), tables=count, rows=rows, runs=runs)
        args.receipt.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(f'{len(runs)} archives, {count} byte-identical tables, {rows} rows')


if __name__ == '__main__':
    main()
