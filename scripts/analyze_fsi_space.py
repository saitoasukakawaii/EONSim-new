"""Compare complete periodic cycles on nested structured reference meshes."""
import argparse
import copy
import json
import math
from pathlib import Path
from fsi_field_cycles import read_snapshot,series,pressure_drop,difference,channel_boundary_errors
from fsi_space_metrics import interpolation,distance


def cycle_paths(work,cycle,solid=False,phases=20):
    """Read exact physical phases of one archived complete cycle; never extrapolate."""
    receipt=json.loads((work/'periodic-result.json').read_text())
    steps=round(.1/receipt['config']['fsi']['dt'])
    stem=f'cycle{cycle}'+(f'_restart{(cycle-1)*steps}' if cycle>1 else '')+('_solid' if solid else '')
    return phase_paths(series(work/(stem+'.pvd')),cycle,phases)


def phase_paths(entries,cycle,phases=20):
    result=[]
    for j in range(1,phases+1):
        time=(cycle-1)*.1+j*.1/phases
        found=[path for t,path in entries if abs(t-time)<1e-10]
        if len(found)!=1:raise ValueError('Missing complete common phase grid')
        result.append(found[0])
    return result


def last_cycle(work,solid):
    receipt=json.loads((work/'periodic-result.json').read_text())
    if not receipt['converged']:raise ValueError('Spatial comparison requires converged periodic receipt')
    return cycle_paths(work,receipt['metrics'][-1]['cycle'],solid)


def same_mesh_cycles(left,left_cycle,right,right_cycle,phases=20):
    """Dimensional phase-RMS field changes; compare physical phases, not step IDs."""
    return cycle_distance({solid:cycle_paths(left,left_cycle,solid,phases) for solid in (False,True)},
                          {solid:cycle_paths(right,right_cycle,solid,phases) for solid in (False,True)})


def cycle_distance(left,right):
    result={}
    for solid in (False,True):
        if not left[solid] or len(left[solid])!=len(right[solid]):raise ValueError('Incompatible phase grids')
        scales={name:1. for name in (('velocity','displacement') if solid else ('velocity','pressure','mesh_displacement'))}
        values=[difference(read_snapshot(a,solid),read_snapshot(b,solid),scales) for a,b in zip(left[solid],right[solid])]
        for field in scales:result[('solid_' if solid else 'fluid_')+field]=math.sqrt(sum(v[field]**2 for v in values)/len(values))
    return result


def error_budget(spatial,temporal,transient,sampling):
    """Reject missing fields or nonfinite estimates; each contamination must be <10%."""
    ratios={}
    if not spatial or any(not math.isfinite(v) or v<=0 for v in spatial.values()):raise ValueError('Invalid spatial reference differences')
    for name,estimate in [('temporal',temporal),('transient',transient),('sampling',sampling)]:
        if estimate.keys()!=spatial.keys():raise ValueError('Incomplete field error budget')
        if any(not math.isfinite(v) or v<0 for v in estimate.values()):raise ValueError('Invalid contamination estimate')
        ratios[name]={k:estimate[k]/spatial[k] for k in spatial}
    return dict(ratios=ratios,passed=all(v<.1 for r in ratios.values() for v in r.values()))


def compare(coarse,fine,n):
    result={}
    for solid in (False,True):
        a=last_cycle(coarse,solid);b=last_cycle(fine,solid)
        fields=['velocity','displacement'] if solid else ['velocity','pressure','mesh_displacement']
        stencil=interpolation(read_snapshot(a[0],solid,True),read_snapshot(b[0],solid),n)
        values=[]
        for left,right in zip(a,b):
            values.append(distance(read_snapshot(left,solid,True),read_snapshot(right,solid),stencil,fields))
        for field in fields:result[('solid_' if solid else 'fluid_')+field]=math.sqrt(sum(r[field]**2 for r in values)/len(values))
    return result


def validate_cases(workdirs,policy):
    expected=None;definitions=[]
    for work,n in zip(workdirs,(2,4,8)):
        definition=json.loads((work/'study-definition.json').read_text())
        if definition['n']!=n:raise ValueError('Unexpected spatial mesh level')
        cfg=copy.deepcopy(json.loads((work/'periodic-result.json').read_text())['config'])
        f=cfg['fsi'];tau=f.get('stabilization_tau')
        if policy=='automatic' and tau is not None:raise ValueError('Mixed stabilization policies')
        if policy=='viscous' and (tau is None or abs(tau*4*f.get('viscosity',1.)*n*n-1)>1e-12):raise ValueError('Expected viscous h-squared stabilization')
        if policy=='fixed' and tau is None:raise ValueError('Expected fixed stabilization')
        if policy!='fixed':f.pop('stabilization_tau',None)
        f.pop('steps');f.pop('output_interval');f.pop('checkpoint_interval',None);cfg.pop('output');cfg.pop('mesh');f['domains'].pop('solid_mesh')
        if expected is not None and cfg!=expected:raise ValueError('Spatial cases differ beyond mesh/stabilization resolution')
        expected=cfg;definitions.append(definition)
    return definitions


def main():
    p=argparse.ArgumentParser();p.add_argument('--coarse',type=Path,required=True);p.add_argument('--medium',type=Path,required=True);p.add_argument('--fine',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--policy',choices=['automatic','fixed','viscous'],default='automatic');a=p.parse_args()
    definitions=validate_cases((a.coarse,a.medium,a.fine),a.policy)
    first=compare(a.coarse,a.medium,2);last=compare(a.medium,a.fine,4)
    result=dict(stabilization_policy=a.policy,definitions=definitions,difference_2_4=first,difference_4_8=last,observed_orders={k:math.log(first[k]/last[k],2) for k in first})
    result['boundary_errors']={}
    for work in (a.coarse,a.medium,a.fine):
        errors=[channel_boundary_errors(read_snapshot(fluid),read_snapshot(solid,True)) for fluid,solid in zip(last_cycle(work,False),last_cycle(work,True))]
        result['boundary_errors'][str(work)]={k:max(e[k] for e in errors) for k in errors[0]}
    result['pressure_cycles']={str(work):[pressure_drop(read_snapshot(path,False,True)) for path in last_cycle(work,False)] for work in (a.coarse,a.medium,a.fine)}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if any(v>1e-10 for errors in result['boundary_errors'].values() for v in errors.values()):raise RuntimeError('No-slip/interface compatibility failed')
    if any(last[k]>=first[k] for k in first):raise RuntimeError('Spatial differences are not decreasing')


if __name__=='__main__':main()
