"""Pressure-driven Womersley flow on a rigid polygonal tube, in synthetic SI units."""
import argparse
import cmath
import json
import math
from pathlib import Path
from typing import NamedTuple

import study_rigid_tube as tube


ALPHA = 2.
OMEGA = ALPHA**2 * tube.VISCOSITY / (tube.DENSITY * tube.RADIUS**2)
PERIOD = 2 * math.pi / OMEGA
LIMITS = dict(amplitude_relative_error=.02, phase_error_degrees=2.,
              waveform_relative_rms_error=.03, cycle_max_change_relative=.001,
              max_net_outward_flux=1e-10)


def case_config(samples, cycles, scheme):
    config = tube.case_config()
    config['mesh'] = 'mesh/fluid.msh'
    config['time'] = dict(scheme=scheme)
    config['fluid'].update(mode='transient', dt=PERIOD/samples, steps=samples*cycles)
    inlet = next(b for b in config['fluid']['boundaries'] if b['tag']==1 and b['type']=='pressure')
    inlet.update(value=0., pressure_time=dict(amplitude=tube.DROP, period=PERIOD))
    return config


def solve(directory, executable, mpiexec, ranks, sectors, radial, axial, samples, cycles, scheme):
    directory.mkdir(parents=True)  # Preserve prior runs, including a failed solve.
    tube.generate(directory/'mesh', sectors=sectors, radial=radial, axial=axial,
                  radius=tube.RADIUS, length=tube.LENGTH)
    config = case_config(samples, cycles, scheme)
    (directory/'case.json').write_text(json.dumps(config, indent=2)+'\n')
    command = [executable.resolve(), '-case', 'case.json', '-fluid_boundary_history']
    if ranks > 1:
        tube.run([executable.resolve(), '-case', 'case.json', '-prepare', 'parts', '-parts', ranks],
                 directory, 'prepare.log')
        command = [mpiexec, '-n', ranks, *command, '-partition', 'parts']
    tube.run(command, directory, 'solve.log', timeout=None)


def reference_flow():
    """Complex Q for a sine drop: Q(t) = Im(Q_hat * exp(i omega t)).

    z^2 = -i alpha^2. The coefficient of degree k in 2 J1(z)/z equals
    the corresponding J0(z) series term divided by k+1 (DLMF 10.2.2).
    This series is evaluated only at the fixed, modest alpha of this case.
    """
    term = j0 = 1.+0j
    difference = 0j
    for k in range(1, 32):
        term *= 1j*ALPHA**2/(4*k*k)
        j0 += term
        difference += term*k/(k+1)
    return (math.pi*tube.RADIUS**2*tube.DROP/(1j*OMEGA*tube.DENSITY*tube.LENGTH)
            * difference/j0)


class BoundarySample(NamedTuple):
    time: float
    area: float
    flow: float
    pressure: float


def boundary_history(log):
    """Read accepted, globally reduced tag samples from a successful solver log."""
    lines = log.splitlines()
    if not lines or lines[-1] != 'status=success':
        raise ValueError('Missing successful solver endpoint')
    history = {}
    for line in lines:
        if not line.startswith('fluid_boundary_step='):
            continue
        row = dict(field.split('=', 1) for field in line.split())
        step, tag = int(row['fluid_boundary_step']), int(row['tag'])
        sample = BoundarySample(*(float(row[k]) for k in ('time','area','outward_flow','mean_pressure')))
        if not all(map(math.isfinite, sample)) or sample.area <= 0:
            raise ValueError(f'Invalid boundary sample at step {step}, tag {tag}')
        tags = history.setdefault(step, {})
        if tag in tags:
            raise ValueError(f'Duplicate boundary sample at step {step}, tag {tag}')
        tags[tag] = sample
    return history


def harmonic(values, phases):
    """Sine-referenced first harmonic on a complete, uniformly sampled cycle."""
    return 2/len(values)*sum(value*complex(math.sin(t), math.cos(t))
                             for value, t in zip(values, phases))


def study_parameters(directory):
    config = json.loads((directory/'case.json').read_text())
    fluid = config['fluid']
    samples = round(PERIOD/fluid['dt'])
    if samples < 8:
        raise ValueError('At least eight phase samples per cycle are required')
    cycles, remainder = divmod(fluid['steps'], samples)
    scheme = config['time']['scheme']
    if (cycles < 2 or remainder or scheme not in ('be','bdf2','generalized_alpha')
            or config != case_config(samples, cycles, scheme)):
        raise ValueError('Case differs from the declared Womersley study')
    geometry = json.loads((directory/'mesh/geometry.json').read_text())
    sectors = geometry['sectors']
    if (geometry['radius'] != tube.RADIUS or geometry['length'] != tube.LENGTH
            or sectors < 6 or geometry['radial'] < 1 or geometry['axial'] < 2):
        raise ValueError('Geometry differs from the declared Womersley study')
    return config, geometry, samples, cycles


def analyze(directory):
    config, geometry, samples, cycles = study_parameters(directory)
    fluid = config['fluid']
    sectors = geometry['sectors']
    area = sectors*tube.RADIUS**2*math.sin(2*math.pi/sectors)/2
    wall_area = 2*sectors*tube.RADIUS*tube.LENGTH*math.sin(math.pi/sectors)
    history = boundary_history((directory/'solve.log').read_text())
    if set(history) != set(range(1, fluid['steps']+1)):
        raise ValueError('Incomplete accepted-step history')
    times, flows, drops = [], [], []
    max_net = 0.
    for step in range(1, fluid['steps']+1):
        rows = history[step]
        if set(rows) != {1, 2, 3}:
            raise ValueError(f'Incomplete tube tags at step {step}')
        for tag, row in rows.items():
            if not math.isclose(row.time, step*fluid['dt'], rel_tol=2e-13, abs_tol=1e-14):
                raise ValueError(f'Unexpected phase time at step {step}')
            if not math.isclose(row.area, wall_area if tag==3 else area, rel_tol=2e-11):
                raise ValueError(f'Unexpected boundary area at tag {tag}')
        times.append(rows[1].time)
        flows.append((rows[2].flow-rows[1].flow)/2)
        drops.append(rows[1].pressure-rows[2].pressure)
        max_net = max(max_net, abs(sum(row.flow for row in rows.values())))
    phases = [OMEGA*t for t in times[-samples:]]
    q = reference_flow()
    end = flows[-samples:]
    previous = flows[-2*samples:-samples]
    observed = harmonic(end, phases)
    exact = [(q*cmath.exp(1j*t)).imag for t in phases]
    p = harmonic(drops[-samples:], phases)
    metrics = dict(
        amplitude_relative_error=abs(abs(observed)/abs(q)-1),
        phase_error_degrees=abs(math.degrees(cmath.phase(observed/q))),
        waveform_relative_rms_error=math.sqrt(sum((v-w)**2 for v,w in zip(end, exact))
                                               /sum(w*w for w in exact)),
        cycle_max_change_relative=max(abs(x-y) for x,y in zip(previous, end))/abs(q),
        max_net_outward_flux=max_net)
    if not all(map(math.isfinite, metrics.values())):
        raise ValueError('Nonfinite Womersley metric')
    return dict(scheme=config['time']['scheme'], samples_per_cycle=samples, cycles=cycles, dt=fluid['dt'],
                sectors=sectors, radial=geometry['radial'], axial=geometry['axial'],
                flow_amplitude=abs(observed), flow_phase_degrees=math.degrees(cmath.phase(observed)),
                reference_amplitude=abs(q), reference_phase_degrees=math.degrees(cmath.phase(q)),
                mean_flow=sum(end)/samples, pressure_drop_amplitude=abs(p),
                pressure_drop_phase_degrees=math.degrees(cmath.phase(p)), **metrics,
                passed=all(value<LIMITS[name] for name,value in metrics.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--mpiexec', default='mpiexec')
    parser.add_argument('--ranks', type=int, default=1)
    parser.add_argument('--mesh', type=int, nargs=3, metavar=('SECTORS','RADIAL','AXIAL'),
                        default=(32,6,6))
    parser.add_argument('--samples', type=int, default=64, help='Equal steps per forcing cycle')
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--scheme', choices=('be','bdf2','generalized_alpha'), default='bdf2')
    parser.add_argument('--analyze-only', action='store_true', help='Replay the recorded case and log')
    parser.add_argument('--check', action='store_true', help='Exit nonzero if a flow target is missed')
    args = parser.parse_args()
    if not args.analyze_only:
        if args.executable is None:
            parser.error('--executable is required for solves')
        if args.samples < 8 or args.cycles < 2 or args.ranks < 1:
            parser.error('Require samples >=8, cycles >=2, ranks >=1')
        solve(args.work, args.executable, args.mpiexec, args.ranks, *args.mesh,
              args.samples, args.cycles, args.scheme)
    result = analyze(args.work)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
    if args.check and not result['passed']:
        raise SystemExit('Missed Womersley flow targets: '+', '.join(
            name for name,limit in LIMITS.items() if result[name]>=limit))


if __name__ == '__main__':
    main()
