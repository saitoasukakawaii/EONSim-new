"""Compare temporal resolution or MPI decompositions of the same rigid tube."""
import argparse
import cmath
import hashlib
import json
import math
from pathlib import Path

from audit_womersley_fields import verified_endpoint_flux
import study_rigid_tube as tube
import study_womersley as study


def mesh_digest(directory):
    config,_,_,_ = study.study_parameters(directory)
    return hashlib.sha256((directory/config['mesh']).read_bytes()).hexdigest()


def bdf2_stabilization(nodes, cells, state, dt, density, viscosity, prescribed=None):
    """Reconstruct the coefficient for the next equal step from an accepted P1 velocity."""
    # For equal steps after BDF2 startup, the effective step in the momentum
    # operator is 2*dt/3. The Tet4 Jacobian determinant equals six times its volume.
    temporal = 3*density/dt
    minimum, maximum = math.inf, 0.
    weighted = volume = max_advective_fraction = 0.
    for tet in cells:
        jacobian = tube.determinant(nodes,tet)
        if not math.isfinite(jacobian) or jacobian<=0:
            raise ValueError('Expected a positive Tet4 determinant')
        h = jacobian**(1/3)
        velocity = [sum(state[n][j] for n in tet)/4 for j in range(3)]
        advective = 2*density*math.hypot(*velocity)/h
        viscous = 4*viscosity/h**2
        inverse = math.hypot(temporal,advective,viscous)
        tau = 1/inverse if prescribed is None else prescribed
        minimum,maximum = min(minimum,tau),max(maximum,tau)
        weighted += jacobian*tau
        volume += jacobian
        max_advective_fraction = max(max_advective_fraction,(advective/inverse)**2)
    if not cells:
        raise ValueError('Expected a nonempty tetrahedral mesh')
    return dict(minimum=minimum,maximum=maximum,volume_weighted_mean=weighted/volume,
                max_advective_fraction_of_default_inverse_tau_squared=max_advective_fraction)


def endpoint_stabilization(directory):
    config,_,samples,_ = study.study_parameters(directory)
    if config['time']['scheme']!='bdf2':
        raise ValueError('Endpoint stabilization reconstruction requires uniform-step BDF2')
    # Validate the endpoint history and the complete field before reconstructing tau.
    study.analyze(directory)
    fluid = config['fluid']
    nodes,cells,faces = tube.read_mesh(directory/config['mesh'])
    state = tube.fields(directory,1)
    step = fluid['steps']
    samples_at_end = study.boundary_history((directory/'solve.log').read_text())[step]
    verified_endpoint_flux(nodes,faces,state,samples_at_end,step*fluid['dt'])
    prescribed = fluid.get('stabilization_tau')
    return dict(samples_per_cycle=samples,prescribed=prescribed,
                **bdf2_stabilization(nodes,cells,state,fluid['dt'],fluid['density'],fluid['viscosity'],prescribed))


def time_refinement(directories):
    if len({mesh_digest(d) for d in directories})>1:
        raise ValueError('Temporal comparisons require identical tetrahedra and coordinates')
    return phasor_refinement([study.analyze(d) for d in directories])


def phasor_refinement(rows):
    """Self-differences use the complex flow, preserving both amplitude and phase."""
    if len(rows)<3:
        raise ValueError('At least three time resolutions are required')
    keys = ('sectors','radial','axial','cycles','scheme','rho_infinity','stabilization_tau')
    if any(any(row.get(k)!=rows[0].get(k) for k in keys) for row in rows[1:]):
        raise ValueError('Only time resolution may vary within a temporal comparison')
    pairs = []
    for coarse,fine in zip(rows,rows[1:]):
        n = coarse['samples_per_cycle']
        if fine['samples_per_cycle']!=2*n:
            raise ValueError('Time resolutions must increase by factors of two')
        q0,q1 = (cmath.rect(r['flow_amplitude'],math.radians(r['flow_phase_degrees']))
                 for r in (coarse,fine))
        difference = abs(q0-q1)/abs(study.reference_flow())
        pairs.append(dict(coarse_samples=n, fine_samples=2*n, relative_phasor_change=difference,
                          max_cycle_change=max(r['cycle_max_change_relative'] for r in (coarse,fine))))
    orders = [math.log2(a['relative_phasor_change']/b['relative_phasor_change'])
              if min(a['relative_phasor_change'],b['relative_phasor_change'])>0 else None
              for a,b in zip(pairs,pairs[1:])]
    return dict(scheme=rows[0]['scheme'],stabilization_tau=rows[0].get('stabilization_tau'),
                cycles=rows[0]['cycles'],successive_pairs=pairs,observed_orders=orders)


def mpi_comparison(serial, parallel, ranks):
    if ranks<2:
        raise ValueError('The parallel state requires at least two ranks')
    if mesh_digest(serial)!=mesh_digest(parallel) or study.study_parameters(serial)!=study.study_parameters(parallel):
        raise ValueError('MPI comparisons require identical meshes and case settings')
    # Full history validation precedes matching the individual channels.
    for directory in (serial,parallel):
        study.analyze(directory)
    one,many = (study.boundary_history((d/'solve.log').read_text()) for d in (serial,parallel))
    states = [tube.fields(serial,1),tube.fields(parallel,ranks)]
    config,_,_,_ = study.study_parameters(serial)
    nodes,_,_ = tube.read_mesh(serial/config['mesh'])
    if any(s.keys()!=nodes.keys() for s in states):
        raise ValueError('MPI fields do not cover the global mesh IDs')
    max_velocity = max(abs(a-b) for n in nodes for a,b in zip(states[0][n][:3],states[1][n][:3]))
    max_pressure = max(abs(states[0][n][3]-states[1][n][3]) for n in nodes)
    diffs = {field:max(abs(getattr(row,field)-getattr(many[step][tag],field))
                       for step,tags in one.items() for tag,row in tags.items())
             for field in study.BoundarySample._fields}
    return dict(ranks=ranks,nodes=len(nodes),steps=len(one),max_velocity_difference=max_velocity,
                max_pressure_difference=max_pressure,max_boundary_differences=diffs,
                passed=(max(max_velocity,max_pressure)<tube.LIMITS['mpi_absolute']
                        and max(diffs.values())<2e-10))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='operation',required=True)
    time = modes.add_parser('time',help='Use successively doubled cycle resolutions')
    time.add_argument('cases',nargs='+',type=Path)
    mpi = modes.add_parser('mpi',help='Compare a serial state with one parallel decomposition')
    mpi.add_argument('serial',type=Path)
    mpi.add_argument('parallel',type=Path)
    mpi.add_argument('--ranks',type=int,required=True)
    tau = modes.add_parser('tau',help='Reconstruct the next equal BDF2 step coefficient from a serial endpoint')
    tau.add_argument('case',type=Path)
    args = parser.parse_args()
    if args.operation=='time':
        result = time_refinement(args.cases)
    elif args.operation=='mpi':
        result = mpi_comparison(args.serial,args.parallel,args.ranks)
    else:
        result = endpoint_stabilization(args.case)
    print(json.dumps(result,indent=2,allow_nan=False))
    if result.get('passed') is False:
        raise SystemExit('MPI field or history tolerance exceeded')


if __name__=='__main__':
    main()
