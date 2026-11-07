"""Audit pressure and elementwise incompressibility in existing Tet4 tube fields.

This is postprocessing, not a solver or an additional acceptance gate. Pressure
is compared with the circular reference on the actual polygon domain, without
removing its constant offset (the end traction fixes the pressure level).
"""
import argparse
import json
import math
from itertools import combinations
from pathlib import Path

import study_rigid_tube as tube


# Degree-four tetrahedron rule; weights are normalized to unit total volume.
# Its moments are checked independently against simplex monomial integrals.
QUADRATURE = [((.25,)*4, -148/1875)]
QUADRATURE += [(tuple(11/14 if i == j else 1/14 for i in range(4)), 343/7500)
               for j in range(4)]
_a = (1+math.sqrt(5/14))/4
_b = (1-math.sqrt(5/14))/4
QUADRATURE += [(tuple(_a if i in pair else _b for i in range(4)), 56/375)
               for pair in combinations(range(4), 2)]


def velocity_integrals(points, values, volume):
    """Integrate squared P1-vs-parabolic velocity error exactly (degree four)."""
    error = reference = 0.
    coefficient = tube.DROP/(4*tube.VISCOSITY*tube.LENGTH)
    for bary, weight in QUADRATURE:
        y, z = (sum(bary[n]*points[n][i] for n in range(4)) for i in (1, 2))
        exact = coefficient*(tube.RADIUS**2-y*y-z*z)
        velocity = [sum(bary[n]*values[n][i] for n in range(4)) for i in range(3)]
        error += weight*((velocity[0]-exact)**2+velocity[1]**2+velocity[2]**2)
        reference += weight*exact*exact
    if error < -1e-14*reference or reference <= 0:
        raise ValueError('Invalid velocity squared integral')
    return volume*max(0., error), volume*reference


def element_metrics(points, values):
    """Exact P1 pressure-error integral and constant velocity divergence."""
    a, b, c = [tube.sub(p, points[0]) for p in points[1:]]
    cofactors = (tube.cross(b, c), tube.cross(c, a), tube.cross(a, b))
    det = sum(x*y for x, y in zip(a, cofactors[0]))
    if not math.isfinite(det) or det <= 0:
        raise ValueError('Expected positive finite tetrahedron')
    if not all(math.isfinite(x) for v in values for x in v):
        raise ValueError('Nonfinite field')
    divergence = sum((values[j+1][i]-values[0][i])*cofactors[j][i]
                     for i in range(3) for j in range(3))/det
    errors = [v[3]-tube.DROP*(1-p[0]/tube.LENGTH) for p, v in zip(points, values)]
    volume = det/6
    # int(N_i N_j) = V(1 + delta_ij)/20 for a tetrahedron.
    pressure_error_squared = volume*(sum(errors)**2+sum(e*e for e in errors))/20
    return volume, divergence, pressure_error_squared, volume*sum(errors)/4


def audit(directory, sectors, level, ranks=1):
    reference = tube.analyze(directory, sectors, level, ranks)
    nodes, cells, _ = tube.read_mesh(directory/'fluid.msh')
    state = tube.fields(directory, ranks)
    volume = div2 = signed_div = absolute_div = pressure2 = pressure_bias = 0.
    maximum_div = velocity_error2 = velocity_reference2 = 0.
    for tet in cells:
        points, values = [nodes[n] for n in tet], [state[n] for n in tet]
        v, d, p2, bias = element_metrics(points, values)
        e2, r2 = velocity_integrals(points, values, v)
        velocity_error2 += e2
        velocity_reference2 += r2
        volume += v
        div2 += v*d*d
        signed_div += v*d
        absolute_div += v*abs(d)
        maximum_div = max(maximum_div, abs(d))
        pressure2 += p2
        pressure_bias += bias
    speed_scale = tube.Q_EXACT/(math.pi*tube.RADIUS**2)
    metrics = dict(velocity_relative_l2_error=math.sqrt(velocity_error2/velocity_reference2),
                   pressure_rms_error=math.sqrt(pressure2/volume),
                   pressure_rms_error_over_drop=math.sqrt(pressure2/volume)/tube.DROP,
                   pressure_mean_error=pressure_bias/volume,
                   divergence_rms=math.sqrt(div2/volume),
                   divergence_rms_over_mean_speed_per_radius=math.sqrt(div2/volume)*tube.RADIUS/speed_scale,
                   divergence_maximum=maximum_div,
                   divergence_volume_integral=signed_div,
                   divergence_absolute_volume_integral=absolute_div,
                   divergence_theorem_absolute_defect=abs(signed_div-reference['net_outward_flux']))
    if not all(math.isfinite(x) for x in metrics.values()):
        raise ValueError('Nonfinite audit metric')
    return dict(reference=reference, fields=metrics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--case', type=int, nargs=2, action='append', required=True,
                        metavar=('SECTORS', 'LEVEL'))
    parser.add_argument('--ranks', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.ranks < 1 or any(s < 6 or l < 0 for s, l in args.case):
        parser.error('Require ranks >=1, sectors >=6, level >=0')
    results = []
    for sectors, level in args.case:
        result = audit(args.work/f's{sectors}-l{level}', sectors, level, args.ranks)
        results.append(result)
        print(json.dumps(result, allow_nan=False), flush=True)
    args.output.write_text(json.dumps(dict(schema=1, scope='diagnostic only; no new qualification',
                                          states=results), indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
