"""Complex dynamic area compliance for the same two-ended, small-amplitude elastic tube."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import splu
from axisymmetric import MeridianTube, TubeParameters


def pair(value):
    return [float(np.real(value)),float(np.imag(value))]


def harmonic(tube, hz):
    """Use Re(p̂ exp(iωt)) at both caps with p̂=1 Pa."""
    omega=2*math.pi*hz
    matrix=(tube.operator+1j*omega*tube.mass).tocsc()
    state=splu(matrix).solve(tube.load)
    residual=float(np.linalg.norm(matrix@state-tube.load,np.inf))
    # Imaginary/real parts of the same linear area observation.
    compliance=np.array(tube.sections(state.real))+1j*np.array(tube.sections(state.imag))
    velocity=state[:tube.nv]
    wall_d=state[tube.solid_d]
    flux=tube.load[:tube.nv]@velocity
    wall_flux=tube.wall_load[:tube.nv]@velocity
    kinetic=np.vdot(velocity,tube.kinetic_mass@velocity).real
    elastic=np.vdot(wall_d,tube.elastic@wall_d).real
    viscous=np.vdot(velocity,tube.viscous@velocity).real
    # Multiply momentum by the conjugate velocity. Static elastic power is reactive.
    work=flux.conjugate()
    mechanical=viscous+1j*omega*(kinetic-elastic)
    power_error=abs(work-mechanical)/max(abs(work),abs(mechanical))
    mass_error=abs(flux-wall_flux)/abs(flux)
    kinematic_error=np.max(abs(velocity[tube.solid_v]-1j*omega*wall_d))
    if (not np.isfinite(state).all() or residual>2e-9 or mass_error>1e-7 or power_error>1e-7 or
            kinematic_error>1e-8*max(1.,np.max(abs(velocity))) or viscous<0):
        raise ValueError(f'Harmonic balance failed: residual={residual}, power={power_error}, mass={mass_error}, kinematics={kinematic_error}')
    return dict(frequency_hz=hz,area_strain_per_pa=[pair(z) for z in compliance],
                inward_flux_per_radian_per_pa=pair(flux),mass_defect_over_flux=float(mass_error),
                complex_power_defect_fraction=float(power_error),stage_equation_residual=residual,
                wall_velocity_kinematics_defect=float(kinematic_error),
                mean_viscous_and_wall_damping_power_per_radian_watts=float(viscous/2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh',type=int,nargs=3,required=True)
    parser.add_argument('--corner-levels',type=int,default=4)
    parser.add_argument('--sections',type=int,default=97)
    parser.add_argument('--support',type=float,nargs=2,default=(0.,0.))
    parser.add_argument('--full-length',action='store_true')
    parser.add_argument('--hz',type=float,nargs='+',default=(.001,.0625,.125,.25,.5,1.,2.))
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if min(a.mesh)<1 or a.sections<3 or a.sections%2==0 or a.corner_levels<0 or not all(
            math.isfinite(v) and v>0 for v in a.hz) or not all(math.isfinite(v) and v>=0 for v in a.support):
        parser.error('Invalid mesh, frequency, support or stations')
    material=TubeParameters(support_stiffness=a.support[0],support_damping=a.support[1])
    tube=MeridianTube(*a.mesh,5,material,a.corner_levels,a.full_length,a.sections)
    report=dict(parameters=asdict(material),mesh=a.mesh,corner_levels=a.corner_levels,full_length=a.full_length,
                unknowns=tube.size,sections=tube.positions,static_area_strain_per_pa=material.lame_area_strain(1),
                static_check=tube.hydrostatic_check(),frequencies=[])
    for hz in a.hz:
        result=harmonic(tube,hz)
        report['frequencies'].append(result)
        a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(hz,result['area_strain_per_pa'][0],result['complex_power_defect_fraction'],flush=True)


if __name__=='__main__':main()
