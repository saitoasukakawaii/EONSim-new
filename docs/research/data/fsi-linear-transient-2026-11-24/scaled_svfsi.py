"""Run a dimensioned two-ended pressure ramp in svFSI on the EONSim mesh."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
from scaled_tube import SurfaceAudit, digest, problem, write_mesh
from audit_reflection import measured_ring_strains

SMOOTH = Path(__file__).resolve().parents[1] / 'fsi-smooth-load-2026-11-24'
sys.path.insert(0, str(SMOOTH))
from audit_study import external_loads
from run_study import eon_stage, external_input, smooth_pressure
from space_study import solve
from svfsi_history import check_convergence


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unrecognized or ambiguous template input: ' + old)
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('case', 'work', 'executable', 'libs', 'reference-scripts'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--steps', type=int, required=True)
    parser.add_argument('--problem', choices=('artificial', 'similar', 'arterial'), required=True)
    args = parser.parse_args()
    n = args.steps
    if n < 8 or n % 8:
        parser.error('Expected eight equally spaced observations')
    sys.path.insert(0, str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as external
    from study_rigid_tube import read_mesh

    m, duration, peak = problem(args.problem)
    work = args.work.resolve()
    template = work / 'template'
    template.mkdir(parents=True, exist_ok=False)
    for domain, tags, name in [('lumen', external.FLUID_FACES, 'fluid.msh'),
                               ('wall', external.SOLID_FACES, 'solid.msh')]:
        write_mesh(args.case / 'reference' / name, work / name, m)
        external.export_mesh(work / name, template, domain, tags)
    deck = (args.case / 'sv-input/svFSI.inp').read_text()
    for old, new in [
        ('Equation: fluid\n      Density: 1\n', f'Equation: fluid\n      Density: {m.fluid_density:.17g}\n'),
        ('Viscosity: Constant { Value: 1 }', f'Viscosity: Constant {{ Value: {m.viscosity:.17g} }}'),
        ('Equation: lElas\n      Density: 1\n', f'Equation: lElas\n      Density: {m.solid_density:.17g}\n'),
        ('Elasticity modulus: 100\n      Poisson ratio: 0.3',
         f'Elasticity modulus: {m.young:.17g}\n      Poisson ratio: {m.poisson:.17g}'),
        ('Increment in saving VTK files: 1\n', f'Increment in saving VTK files: {n // 8}\n'),
    ]:
        deck = replace_once(deck, old, new)
    if deck.count('   Max iterations: 12\n') != 2:
        raise ValueError('Missing FS/MS iteration budgets')
    deck = deck.replace('   Max iterations: 12\n', '   Max iterations: 40\n')
    (template / 'svFSI.inp').write_text(deck)
    dt = duration / n
    external_input(template, work, n, dt, 'matched', 1e-23, peak, duration)
    solve(args.executable, ['svFSI.inp'], work, args.libs)
    hist = (work / '1-procs/histor.dat').read_text()
    convergence = {eq: check_convergence(hist, n, eq) for eq in ('FS', 'MS')}
    trace = external_loads(work, n, 'matched', peak, duration)
    if trace.keys() != {(i, tag) for i in range(1, n + 1) for tag in (1, 2)}:
        raise ValueError('Missing accepted load on a pressure port')
    load_error = max(abs(row[k] - smooth_pressure(eon_stage(i, dt) / duration, peak))
                     for (i, _), row in trace.items() for k in ('min_pressure', 'max_pressure'))
    meshes = [read_mesh(work / name) for name in ('fluid.msh', 'solid.msh')]
    audit = SurfaceAudit(meshes[0])
    initial = audit.volume(np.zeros((len(audit.ids), 7)))
    samples = []
    for step in range(n // 8, n + 1, n // 8):
        path = work / f'1-procs/result_{step:03d}.vtu'
        state = external.external_fields(path, meshes)
        positions, strain = measured_ring_strains(meshes[1],state[1])
        measured = audit.array(state[0])
        ports = audit.observe(measured, smooth_pressure(step / n, peak))
        samples.append(dict(phase=step / n, time=step * dt, strains=strain,
                            outward_flow=[ports[k]['outward_flow'] for k in (1, 2)],
                            relative_volume_change=audit.volume(measured) / initial - 1,
                            vtu_sha256=digest(path)))
    result = dict(problem=args.problem, steps=n, parameters=asdict(m), pressure=peak, duration=duration,
                  static_area_strain=m.lame_area_strain(peak), xs=positions, load_error=load_error,
                  convergence=convergence, executable_sha256=digest(args.executable),
                  input_sha256={k: digest(work / k) for k in ('fluid.msh', 'solid.msh', 'svFSI.inp',
                                                              'fluid_in.dat', 'fluid_out.dat')},
                  history_sha256=digest(work / '1-procs/histor.dat'), samples=samples)
    (work / 'result.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
    print(args.problem, n, 100 * samples[-1]['strains'][0], result['convergence'], flush=True)


if __name__ == '__main__':
    main()
