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
    parser.add_argument('--ranks', type=int, choices=(1,2,4), default=1)
    parser.add_argument('--mpiexec', default='mpiexec')
    parser.add_argument('--schur', action='store_true', help='Use existing Schur/GAMG instead of direct LU')
    parser.add_argument('--timeout', type=float, default=900, help='Timeout per solver command, seconds')
    parser.add_argument('--krylov-restart',type=int,default=30)
    parser.add_argument('--krylov-iterations',type=int,default=500)
    args = parser.parse_args()
    if not args.analyze_only and args.executable is None:
        parser.error('--executable is required for solves')
    if not 0 < args.timeout <= 86400:
        parser.error('--timeout must be in (0,86400] seconds')
    if min(args.krylov_restart,args.krylov_iterations)<=0:
        parser.error('Krylov budgets must be positive')
    if not args.schur and (args.krylov_restart,args.krylov_iterations)!=(30,500):
        parser.error('Krylov budgets require --schur')
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
            command = [args.executable.resolve(), '-case', 'case.json']
            if args.ranks > 1:
                tube.run(command+['-prepare','parts','-parts',args.ranks],directory,'prepare.log',args.timeout)
                command = [args.mpiexec,'-n',args.ranks]+command+['-partition','parts']
            if args.schur:
                command += ['-schur_pc','-ksp_converged_reason','-ksp_gmres_restart',args.krylov_restart,
                            '-ksp_max_it',args.krylov_iterations]
            (directory/'run.json').write_text(json.dumps(dict(ranks=args.ranks,schur=args.schur,
                krylov_restart=args.krylov_restart,krylov_iterations=args.krylov_iterations,
                command=list(map(str,command)),timeout=args.timeout),indent=2)+'\n')
            tube.run(command, directory, 'solve.log' if args.ranks==1 else 'solve-mpi.log', args.timeout)
        geometry = json.loads((directory/'base/geometry.json').read_text())
        if any(geometry[key] != value for key, value in
               (('sectors', sectors), ('radial', radial), ('axial', axial),
                ('radius', tube.RADIUS), ('length', tube.LENGTH))):
            raise ValueError('Seed metadata differs from requested geometry')
        if (directory/'run.json').exists():
            saved = json.loads((directory/'run.json').read_text())
            if (saved['ranks'],saved['schur']) != (args.ranks,args.schur):
                raise ValueError('Solver/rank selection differs from saved run')
            if (saved.get('krylov_restart',30),saved.get('krylov_iterations',500)) != (args.krylov_restart,args.krylov_iterations):
                raise ValueError('Krylov budgets differ from saved run')
        elif args.ranks != 1 or args.schur:
            raise ValueError('Missing solver/rank receipt')
        result = audit(directory, sectors, 0, args.ranks)
        result['seed'] = dict(sectors=sectors, radial=radial, axial=axial, red_refinements=0)
        results.append(result)
        print(json.dumps(result, allow_nan=False), flush=True)
        report = dict(schema=1, scope='seed-mesh diagnostics only', states=results,
                      solver=dict(ranks=args.ranks,schur=args.schur,krylov_restart=args.krylov_restart,
                                  krylov_iterations=args.krylov_iterations))
        if not args.analyze_only:
            report['executable_sha256'] = hashlib.sha256(args.executable.read_bytes()).hexdigest()
        (work/('recomputed.json' if args.analyze_only else 'summary.json')).write_text(
            json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
