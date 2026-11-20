"""Compare a Womersley VTU endpoint with the circular velocity and pressure fields."""
import argparse
import cmath
from functools import lru_cache
from itertools import combinations
import json
import math
from pathlib import Path

from audit_rigid_tube_fields import element_metrics
import study_rigid_tube as tube
import study_womersley as study


def bessel_j0(radius_squared):
    """J0(z*r/R) for z² = -i alpha² and the fixed alpha=2 of the study."""
    argument = 1j*study.ALPHA**2*radius_squared/(4*tube.RADIUS**2)
    term = total = 1.+0j
    for k in range(1,32):
        term *= argument/(k*k)
        total += term
        if abs(term) < 1e-18:
            break
    return total


WALL_J0 = bessel_j0(tube.RADIUS**2)


@lru_cache(maxsize=32768)
def axial_velocity(radius_squared):
    return (tube.DROP/(1j*study.OMEGA*tube.DENSITY*tube.LENGTH)
            * (1-bessel_j0(radius_squared)/WALL_J0))


def quadrature(order):
    """Positive, volume-normalized tetrahedral rule from Gauss points on [0,1]."""
    if order==3:
        offset = math.sqrt(3/5)/2
        rule = ((.5-offset,5/18), (.5,4/9), (.5+offset,5/18))
    elif order==4:
        offset = math.sqrt(6/5)
        outer,inner = (math.sqrt((3+sign*2*offset)/7)/2 for sign in (1,-1))
        light,heavy = (18-math.sqrt(30))/72, (18+math.sqrt(30))/72
        rule = ((.5-outer,light), (.5-inner,heavy), (.5+inner,heavy), (.5+outer,light))
    else:
        raise ValueError('Expected a three- or four-point Gauss rule per axis')
    return [(((1-u)*(1-v)*(1-w), u, (1-u)*v, (1-u)*(1-v)*w),
             6*wu*wv*ww*(1-u)**2*(1-v))
            for u,wu in rule for v,wv in rule for w,ww in rule]


def axial_sections(nodes, cells, state, geometry, drop):
    """Integrate each complete mesh layer once, with axial flow positive along x."""
    axial,sectors = geometry['axial'],geometry['sectors']
    planes = sorted({xyz[0] for xyz in nodes.values()})
    if len(planes)!=axial+1 or any(not math.isclose(x,i*tube.LENGTH/axial,abs_tol=1e-13)
                                   for i,x in enumerate(planes)):
        raise ValueError('Expected the axial planes of the generated tube')
    faces = {}
    for tet in cells:
        for a,b,c in combinations(tet,3):
            if nodes[a][0]==nodes[b][0]==nodes[c][0]:
                face = tuple(sorted((a,b,c)))
                faces[face] = faces.get(face,0)+1
    sums = {x:[0.,0.,0.] for x in planes}
    for face,count in faces.items():
        a,b,c = (nodes[n] for n in face)
        x = a[0]
        if count!=(1 if x in (planes[0],planes[-1]) else 2):
            raise ValueError('Invalid axial triangle incidence')
        area = abs((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]))/2
        totals = sums[x]
        totals[0] += area
        totals[1] += area*sum(state[n][0] for n in face)/3
        totals[2] += area*sum(state[n][3] for n in face)/3
    expected = sectors*tube.RADIUS**2*math.sin(2*math.pi/sectors)/2
    levels = []
    for x,(area,flux,p) in sums.items():
        if not math.isclose(area,expected,rel_tol=1e-11):
            raise ValueError('Incomplete axial cross section')
        levels.append(dict(x=x,axial_flow=flux,mean_pressure=p/area,
                           reference_pressure=drop*(1-x/tube.LENGTH)))
    return levels


def verified_endpoint_flux(nodes,faces,state,samples,expected_time):
    """Align a VTU endpoint with the time and all integral boundary observations."""
    if nodes.keys()!=state.keys() or set(samples)!={1,2,3}:
        raise ValueError('Endpoint mesh IDs or boundary tags differ')
    flux,area,pressure = tube.surface_integrals(nodes,faces,state)
    for tag,row in samples.items():
        if (not math.isclose(row.time,expected_time,rel_tol=2e-13,abs_tol=1e-14)
                or not math.isclose(area[tag],row.area,rel_tol=2e-11)
                or abs(flux[tag]-row.flow)>1e-11
                or abs(pressure[tag]/area[tag]-row.pressure)>1e-10):
            raise ValueError(f'VTU and accepted boundary history disagree at tag {tag}')
    return flux


def audit(directory, snapshot, ranks=1, order=3):
    config, geometry, _, _ = study.study_parameters(directory)
    fluid = config['fluid']
    rows = study.boundary_history((snapshot/'solve.log').read_text())
    if not rows:
        raise ValueError('Missing accepted endpoint')
    step = max(rows)
    if not 1 <= step <= fluid['steps'] or set(rows[step])!={1,2,3}:
        raise ValueError('Invalid endpoint step or tags')
    time = rows[step][1].time
    phase = cmath.exp(1j*study.OMEGA*time)
    drop = tube.DROP*phase.imag
    nodes,cells,faces = tube.read_mesh(directory/config['mesh'])
    s,r,a = (geometry[key] for key in ('sectors','radial','axial'))
    if len(nodes)!=(a+1)*(1+s*r) or len(cells)!=3*a*s*(2*r-1):
        raise ValueError('Resolution metadata differs from the generated tube mesh')
    state = tube.fields(snapshot,ranks)
    flux = verified_endpoint_flux(nodes,faces,state,rows[step],step*fluid['dt'])
    volume = velocity_error2 = reference2 = pressure2 = divergence2 = axial_integral = 0.
    rule = quadrature(order)
    for tet in cells:
        points = [nodes[n] for n in tet]
        values = [state[n] for n in tet]
        v, divergence, p2, _ = element_metrics(points,values,drop)
        volume += v
        pressure2 += p2
        divergence2 += v*divergence**2
        axial_integral += v*sum(u[0] for u in values)/4
        for bary,weight in rule:
            y = sum(l*p[1] for l,p in zip(bary,points))
            z = sum(l*p[2] for l,p in zip(bary,points))
            exact = (axial_velocity(y*y+z*z)*phase).imag
            ux,uy,uz = (sum(l*u[c] for l,u in zip(bary,values)) for c in range(3))
            velocity_error2 += v*weight*((ux-exact)**2+uy**2+uz**2)
            reference2 += v*weight*exact**2
    sectors = geometry['sectors']
    expected_volume = sectors*tube.RADIUS**2*math.sin(2*math.pi/sectors)*tube.LENGTH/2
    if not math.isclose(volume,expected_volume,rel_tol=1e-10):
        raise ValueError('Unexpected polygon volume')
    q = study.reference_flow()
    wall_nodes = {n for tag,face in faces if tag==3 for n in face}
    metrics = dict(velocity_relative_l2=math.sqrt(velocity_error2/reference2),
                   pressure_rms_over_drop_amplitude=math.sqrt(pressure2/volume)/tube.DROP,
                   divergence_rms=math.sqrt(divergence2/volume),
                   max_wall_speed=max(math.hypot(*state[n][:3]) for n in wall_nodes),
                   volume_mean_flow=axial_integral/tube.LENGTH,
                   end_flow=(flux[2]-flux[1])/2, circular_flow=(q*phase).imag)
    if not all(map(math.isfinite,metrics.values())):
        raise ValueError('Nonfinite Womersley field diagnostic')
    return dict(step=step, time=time, ranks=ranks, nodes=len(nodes), tetrahedra=len(cells),
                gauss_points_per_axis=order, axial_sections=axial_sections(nodes,cells,state,geometry,drop),
                **metrics)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True,help='Study case and mesh directory')
    parser.add_argument('--snapshot',type=Path,help='Directory containing matching solution VTU and solve.log')
    parser.add_argument('--ranks',type=int,default=1)
    parser.add_argument('--quadrature',type=int,choices=(3,4),default=3)
    args=parser.parse_args()
    print(json.dumps(audit(args.work,args.snapshot or args.work,args.ranks,args.quadrature),
                     indent=2,allow_nan=False))


if __name__=='__main__':
    main()
