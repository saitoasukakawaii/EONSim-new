"""Compare circular-tube seed meshes without tuning equations or tolerances.

Each seed is (sectors, radial subdivisions, axial subdivisions). No red
refinement is applied. Results are diagnostics, not a production acceptance.
Use a fresh work directory to preserve earlier experiments and failure logs.
"""
import argparse
import hashlib
import json
from pathlib import Path

import study_rigid_tube as tube
from audit_rigid_tube_fields import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--seed', type=int, nargs=3, action='append', required=True,
                        metavar=('SECTORS', 'RADIAL', 'AXIAL'))
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    if not args.analyze_only and args.executable is None:
        parser.error('--executable is required for solves')
    if any(s < 6 or r < 1 or a < 2 for s, r, a in args.seed):
        parser.error('Require sectors >=6, radial >=1, axial >=2')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    results = []
    for sectors, radial, axial in args.seed:
        directory = work/f's{sectors}-r{radial}-a{axial}'
        if not args.analyze_only:
            directory.mkdir()  # Never overwrite an existing solve or failed attempt.
            tube.generate(directory/'base', sectors=sectors, radial=radial, axial=axial,
                          radius=tube.RADIUS, length=tube.LENGTH)
            tube.write_mesh(directory/'fluid.msh', *tube.read_mesh(directory/'base/fluid.msh'))
            (directory/'case.json').write_text(json.dumps(tube.case_config(), indent=2)+'\n')
            tube.run([args.executable.resolve(), '-case', 'case.json'], directory, 'solve.log')
        geometry = json.loads((directory/'base/geometry.json').read_text())
        if any(geometry[key] != value for key, value in
               (('sectors', sectors), ('radial', radial), ('axial', axial),
                ('radius', tube.RADIUS), ('length', tube.LENGTH))):
            raise ValueError('Seed metadata differs from requested geometry')
        result = audit(directory, sectors, 0)
        result['seed'] = dict(sectors=sectors, radial=radial, axial=axial, red_refinements=0)
        results.append(result)
        print(json.dumps(result, allow_nan=False), flush=True)
        report = dict(schema=1, scope='seed-mesh diagnostics only', states=results)
        if not args.analyze_only:
            report['executable_sha256'] = hashlib.sha256(args.executable.read_bytes()).hexdigest()
        (work/('recomputed.json' if args.analyze_only else 'summary.json')).write_text(
            json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
