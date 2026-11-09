"""Prespecified elastic-tube observable comparison, never full qualification.

Both inputs must be audit_pressure_tube reports for the same physical case and
mesh. The reference amplitude is the denominator. Phase differences are wrapped
to [-180,180), without fitting a time shift. Undefined small-amplitude phases
cannot pass a phase gate. Space/time/tail/sampling budgets remain separate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_pressure_tube import harmonic

FIELDS={
    'mid_radial_displacement':(.05,None),
    'mid_ring_projected_area':(.05,None),
    'mid_pressure':(.02,1.),
    'outward_flow_left':(.05,2.),
    'outward_flow_right':(.05,2.),
}
QUALITY={'kinematics':1e-12,'stage_mass':1e-9,'stage_divergence_theorem':1e-12}
FIELD_NAMES={'fluid_velocity','fluid_pressure','fluid_mesh_displacement',
             'solid_velocity','solid_displacement'}


def finite(value):
    if isinstance(value,dict):
        for child in value.values():finite(child)
    elif isinstance(value,list):
        for child in value:finite(child)
    elif isinstance(value,(int,float)) and not math.isfinite(value):
        raise ValueError('Nonfinite audit value')


def validate(report,solver):
    finite(report)
    if report['solver']!=solver:raise ValueError('Wrong solver identity')
    n=report['samples_per_cycle'];steps=report['steps'];period=report['period']
    if (type(n) is not int or type(steps) is not int or n<4 or steps<3*n or
            steps%n or period<=0 or len(report['rows'])!=steps):
        raise ValueError('Incomplete complete-cycle history')
    for step,row in enumerate(report['rows'],1):
        if row['step']!=step or abs(row['time']-step*period/n)>1e-9*period:
            raise ValueError('Unexpected accepted time grid')
    for name,limit in QUALITY.items():
        item=report['quality_gates'][name]
        if (item['limit']!=limit or item['maximum']<0 or
                item['passed']!=(item['maximum']<limit)):
            raise ValueError('Changed or inconsistent quality gate')
    last=steps//n;periodic=True
    for cycle in (last-1,last):
        values=report['cycle_differences'][str(cycle)]
        if set(values)!=FIELD_NAMES:raise ValueError('Incomplete periodic field audit')
        for value in values.values():
            if value['relative_max']<0 or value['relative_rms']<0:
                raise ValueError('Negative periodic norm')
            if value['relative_rms']>value['relative_max']*(1+1e-12)+1e-15:
                raise ValueError('Periodic RMS exceeds maximum')
            periodic=periodic and value['relative_max']<1e-5
    if report['periodic']!=periodic:raise ValueError('Inconsistent periodic acceptance')
    for name in FIELDS:
        actual=harmonic(report['rows'][-n:],name,period)
        stored=report['harmonics'][name]
        for key,value in actual.items():
            if abs(value-stored[key])>1e-12*max(abs(value),abs(stored[key]),1e-12):
                raise ValueError('Stored harmonic differs from accepted samples')
    return dict(periodic=periodic,
        positive_geometry=min(report['minimum_fluid_jacobian'],report['minimum_solid_jacobian'])>0,
        quality=all(report['quality_gates'][k]['passed'] for k in QUALITY))


def difference(left,right,scale,amplitude_limit,phase_limit):
    if not math.isfinite(scale) or scale<=0:raise ValueError('Invalid observable scale')
    floor=1e-12*scale
    amplitude_defined=right['amplitude']>floor
    phase_defined=amplitude_defined and left['amplitude']>floor
    amplitude_error=abs(left['amplitude']-right['amplitude'])/right['amplitude'] if amplitude_defined else None
    phase_error=(left['phase_degrees']-right['phase_degrees']+180)%360-180 if phase_defined else None
    amp_pass=amplitude_defined and amplitude_error<amplitude_limit
    phase_pass=phase_defined and abs(phase_error)<phase_limit if phase_limit is not None else None
    return dict(eonsim=left,svfsi=right,reference_amplitude_denominator=right['amplitude'],
        physical_scale=scale,unresolved_amplitude_floor=floor,
        relative_amplitude_difference=amplitude_error,amplitude_limit=amplitude_limit,
        amplitude_passed=amp_pass,phase_difference_degrees=phase_error,
        phase_limit_degrees=phase_limit,phase_passed=phase_pass,
        mean_difference=left['mean']-right['mean'],
        passed=amp_pass and (phase_limit is None or phase_pass))


def compare(left,right):
    prerequisites={'EONSim':validate(left,'EONSim'),'svFSI':validate(right,'svFSI')}
    for key in ('physical_definition','period','scales','case_sha256','reference_meshes','analysis_script_sha256'):
        if left[key]!=right[key]:raise ValueError('Different comparison input: '+key)
    if left['samples_per_cycle']!=right['samples_per_cycle'] or left['steps']!=right['steps']:
        raise ValueError('Cross-solver comparison requires matching sampling and cycle count')
    d=left['physical_definition'];r=d['radius'];length=d['length']
    displacement=left['scales'][1]['displacement'];omega=2*math.pi/left['period']
    scales={'mid_radial_displacement':displacement,'mid_ring_projected_area':2*math.pi*r*displacement,
            'mid_pressure':abs(d['pressure_time']['amplitude']),
            'outward_flow_left':math.pi*r*length*omega*displacement,
            'outward_flow_right':math.pi*r*length*omega*displacement}
    values={name:difference(left['harmonics'][name],right['harmonics'][name],scales[name],*limits)
            for name,limits in FIELDS.items()}
    lame={}
    for report in (left,right):
        exact=report['infinite_plane_strain_compliance']*d['pressure']
        if abs(exact)<=1e-12*displacement:raise ValueError('Zero Lame mean reference')
        actual=report['harmonics']['mid_radial_displacement']['mean']
        error=abs(actual-exact)/abs(exact)
        lame[report['solver']]=dict(numerical_mean=actual,infinite_circular_plane_strain_mean=exact,
            relative_difference=error,limit=.02,within_limit=error<.02,
            scope='Diagnostic only until polygon geometry and finite-end effects are bounded')
    synthetic=bool(left.get('synthetic_fixture_not_a_solver_result') or right.get('synthetic_fixture_not_a_solver_result'))
    eligible=not synthetic and all(all(v.values()) for v in prerequisites.values())
    return dict(prerequisites=prerequisites,synthetic_input=synthetic,comparison_eligible=eligible,
        observables=values,observable_gates_passed=eligible and all(v['passed'] for v in values.values()),
        lame_mean_diagnostics=lame,
        qualification='Incomplete: independent space/time/tail/sampling, geometry, MPI and restart evidence remains required',
        scope='Same-mesh cross-solver observables only; endpoint values, fixed absolute phase, svFSI amplitude denominator')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eonsim',type=Path,required=True)
    parser.add_argument('--svfsi',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    left=json.loads(a.eonsim.read_text());right=json.loads(a.svfsi.read_text())
    result=compare(left,right)
    result['input_files']={name:dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                           for name,path in (('eonsim',a.eonsim),('svfsi',a.svfsi))}
    result['helper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x') as file:file.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':main()
