"""Harmonic through-flow in a clamped-end elastic SI tube with an independent three-element terminal."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from axisymmetric import MeridianTube
from scaled_tube import problem

# Full circular lumen parameters in SI. The pressure-area comparison uses an independent radius/length scale.
RP, RD, C = 2e7, 8e7, 2.5e-9
AMPLITUDE = 2e-7


def pair(z):
    return [float(z.real), float(z.imag)]


def mean_pressure(tube, state, end):
    """Exact area average of the Q1 end-face pressure on the original circle."""
    r = tube.radial_nodes[:tube.bore+1:2]
    nx = len(tube.x_bounds)
    values = state[tube.pressure.reshape(nx, len(r))[end]]
    dr = np.diff(r)
    left = dr * (r[:-1]/2 + dr/6)
    right = dr * (r[:-1]/2 + dr/3)
    return 2*(left@values[:-1] + right@values[1:])/r[-1]**2


def harmonic(tube, hz, rigid=False, amplitude=AMPLITUDE, resistances=(RP, RD, C), moving_outlet=False):
    if not tube.full_length:
        raise ValueError('Perfusion requires two distinct ends')
    omega = 2*np.pi*hz
    rp, rd, compliance = resistances
    z = rp + rd/(1+1j*omega*rd*compliance)
    v = tube.velocity
    r = tube.radial_nodes
    bore = tube.bore
    given = np.zeros(tube.size, dtype=complex)
    prescribed = np.zeros(tube.size, dtype=bool)

    def fix(ids):
        prescribed[ids[ids>=0]] = True

    for end in (0, -1):
        velocities, displacements = v[end,bore:], tube.displacement[end,bore:]
        if end==-1 and moving_outlet:
            # Axial roller. Radial motion of the annulus changes the outlet area.
            fix(velocities[:,0])
            fix(displacements[:,0])
        else:
            fix(velocities)
            fix(displacements)
    if rigid:
        fix(tube.solid_v)
        fix(tube.solid_d)
    fix(v[0, :bore+1])
    axial = v[0, :bore, 0]
    if min(axial) < 0:
        raise ValueError('Missing prescribed inlet velocity degrees of freedom')
    given[axial] = 2*amplitude/(np.pi*r[bore]**2)*(1-(r[:bore]/r[bore])**2)
    inlet = np.zeros(tube.size)
    outlet = np.zeros(tube.size)
    for weights, end, sign in ((inlet, 0, 1), (outlet, -1, -1)):
        idx = v[end, :bore+1, 0]
        idx = idx[idx>=0]
        weights[idx] = sign*tube.load[idx]
    full_circle = 2*np.pi
    qin = full_circle*inlet@given
    if abs(qin/amplitude-1) > 1e-12:
        raise ValueError('Parabolic inlet quadrature changed the prescribed volume rate')

    # The meridian weak form is per radian. Only the flux seen by the terminal is integrated over 2π.
    op = (tube.operator + 1j*omega*tube.mass).tocsc()
    free = ~prescribed
    b = sparse.csc_matrix(outlet[free, None])
    augmented = sparse.bmat([[op[free][:, free], b], [-full_circle*z*b.T, sparse.csc_matrix([[1.]])]],format='csc')
    rhs = np.r_[-(op@given)[free], full_circle*z*(outlet@given)]
    lu = splu(augmented)
    solution = lu.solve(rhs)
    solution += lu.solve(rhs-augmented@solution)
    state = given.copy()
    state[free] = solution[:-1]
    pout = solution[-1]
    qout = full_circle*(outlet@state)
    residual = op@state + outlet*pout
    pressure_scale = amplitude * abs(z)
    # Mean inlet nodal reaction work includes the nonuniform prescribed test/trial profile.
    inlet_work = full_circle*np.vdot(given, residual)
    vel = state[:tube.nv]
    d = state[tube.solid_d]
    wall_flux = full_circle*(tube.wall_load[:tube.nv]@vel)
    kinetic = full_circle*np.vdot(vel,tube.kinetic_mass@vel).real
    elastic = full_circle*np.vdot(d,tube.elastic@d).real
    dissipation = full_circle*np.vdot(vel,tube.viscous@vel).real
    power = dissipation + 1j*omega*(kinetic-elastic) + pout*qout.conjugate()
    pc = pout - rp*qout
    terminal_power = rp*abs(qout)**2 + abs(pc)**2/rd - 1j*omega*compliance*abs(pc)**2
    checks = dict(relative_flux_balance=abs(qin-qout-wall_flux)/amplitude,
                  relative_complex_power=abs(inlet_work-power)/max(abs(power),amplitude*pressure_scale),
                  relative_terminal_power=abs(pout*qout.conjugate()-terminal_power)/(amplitude*pressure_scale),
                  relative_circuit_pressure=abs(pout-z*qout)/pressure_scale,
                  max_free_row_residual=float(np.max(abs(residual[free]))),
                  kinematic_error=float(np.max(abs(vel[tube.solid_v]-1j*omega*d))))
    if (not np.isfinite(solution).all() or dissipation < 0 or max(checks.values()) > 3e-8
            or (rigid and (abs(qout/amplitude-1)>1e-9 or abs(wall_flux)>1e-15))):
        raise ValueError('Perfusion balance failed: '+str(checks))
    area = np.array(tube.sections(state.real))+1j*np.array(tube.sections(state.imag))
    if abs(area[0])>1e-14 or (not moving_outlet and abs(area[-1])>1e-14):
        raise ValueError('Clamped end hoop displacement changed')
    return dict(frequency_hz=hz, inlet_phasor_m3_s=pair(qin), outlet_phasor_m3_s=pair(qout),
                wall_phasor_m3_s=pair(wall_flux), outlet_load_pa=pair(pout), capacitor_pa=pair(pc),
                inlet_mean_pressure_pa=pair(mean_pressure(tube,state,0)), outlet_mean_pressure_pa=pair(mean_pressure(tube,state,-1)),
                inlet_work_pressure_pa=pair(inlet_work/qin.conjugate()), dissipative_watts=dissipation/2,
                area_strain=[pair(x) for x in area], **checks)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mesh',type=int,nargs=3,required=True,help='Axial cells per half, fluid and wall radial cells before grading')
    p.add_argument('--corner-levels',type=int,default=2)
    p.add_argument('--hz',type=float,nargs='+',default=(.5,1.,2.))
    p.add_argument('--steady-only',action='store_true',help='Solve the zero-frequency pressure, steady flow and elastic displacement')
    p.add_argument('--rigid',action='store_true')
    p.add_argument('--moving-outlet',action='store_true',help='Allow radial wall displacement at the fixed axial outlet plane')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if min(args.mesh)<1 or args.corner_levels<0 or not all(math.isfinite(v) and v>0 for v in args.hz):
        p.error('Expected positive mesh counts and frequencies')
    m, _, _=problem('arterial')
    tube=MeridianTube(*args.mesh,5,m,args.corner_levels,True,97)
    raw=dict(parameters=asdict(m), mesh=args.mesh, corner_levels=args.corner_levels, rigid=args.rigid,
             unknowns=tube.size, sections=tube.positions, outlet_tangential_motion=args.moving_outlet, amplitude_m3_s=AMPLITUDE, full_rcr_si=[RP,RD,C], runs=[])
    for hz in ([0.] if args.steady_only else args.hz):
        row=harmonic(tube,hz,args.rigid,moving_outlet=args.moving_outlet)
        raw['runs'].append(row)
        print(hz, row['inlet_mean_pressure_pa'], row['outlet_load_pa'], row['relative_complex_power'],flush=True)
    args.output.write_text(json.dumps(raw,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
