"""Audit the complete three-mesh periodic study against its error budget.

Temporal estimates use actual dt/2 periodic solutions at all three mesh levels.
They include the default stabilization's dt dependence. Transient estimates are
conditional empirical decay tails, not rigorous error bounds.
"""
import argparse
import csv
import math
import copy
import hashlib
import json
from pathlib import Path
from analyze_fsi_space import validate_cases,cross_mesh_cycles,cycle_distance,cycle_paths,phase_paths,error_budget
from fsi_field_cycles import read_snapshot,pressure_drop,channel_boundary_errors,series
from fsi_cycle_metrics import volume_budget


def physical_config(config):
    result=copy.deepcopy(config);f=result['fsi']
    for key in ('steps','output_interval','checkpoint_interval'):f.pop(key,None)
    for key in ('output','mesh'):result.pop(key,None)
    f['domains'].pop('solid_mesh',None)
    return result


def audit_cycle(work):
    receipt=json.loads((work/'periodic-result.json').read_text())
    definition=json.loads((work/'study-definition.json').read_text())
    if not receipt['converged'] or receipt['metrics'][-1]['consecutive_passes']<3:raise ValueError('Incomplete periodic convergence')
    last=receipt['metrics'][-1]['cycle'];pressure={}
    steps=round(.1/receipt['config']['fsi']['dt']);rows=[]
    for cycle in range(1,last+1):
        stem=f'cycle{cycle}'+(f'_restart{(cycle-1)*steps}' if cycle>1 else '')
        with (work/(stem+'.csv')).open() as stream:rows.extend({k:float(v) for k,v in row.items()} for row in csv.DictReader(stream))
    mass=volume_budget(rows)
    if abs(rows[-1]['time']-last*.1)>1e-10 or any(not math.isfinite(v) for row in rows for v in row.values()):raise ValueError('Incomplete/nonfinite accepted history')
    balance=dict(stage_mass=max(abs(r['stage_mass_residual']) for r in rows),
                 surface_divergence=max(abs(r['stage_mass_residual']+r['stage_divergence']) for r in rows),
                 inlet_flow=max(abs(r['endpoint_inlet_flow']-r['target_endpoint_flow']) for r in rows),
                 minimum_j=min(v for r in rows for k,v in r.items() if k.endswith('_j')))
    if balance['stage_mass']>1e-9 or balance['surface_divergence']>1e-12 or balance['inlet_flow']>1e-12 or balance['minimum_j']<=0:raise ValueError('Accepted flow/geometry gate failed')
    for cycle in range(last-3,last+1):
        pressure[cycle]=[pressure_drop(read_snapshot(path,False,True))['pressure_drop'] for path in cycle_paths(work,cycle)]
    pressure_checks={}
    for cycle in range(last-2,last+1):
        delta=[b-a for a,b in zip(pressure[cycle-1],pressure[cycle])]
        pressure_checks[cycle]=dict(relative_max=max(map(abs,delta))/.1,relative_mean_drift=abs(sum(delta)/len(delta))/.1)
    if any(v['relative_max']>definition['tolerance'] for v in pressure_checks.values()):raise ValueError('Pressure-drop periodic gate failed')
    boundaries=[channel_boundary_errors(read_snapshot(a),read_snapshot(b,True)) for a,b in zip(cycle_paths(work,last),cycle_paths(work,last,True))]
    boundary={k:max(v[k] for v in boundaries) for k in boundaries[0]}
    if max(boundary.values())>1e-12:raise ValueError('No-slip/interface compatibility failed')
    return dict(last_cycle=last,pressure_checks=pressure_checks,boundary_errors=boundary,mass_budget=mass,flow_balance=balance,accepted_rows=len(rows))


def attached_estimate(path,source,kind):
    result=json.loads(path.read_text());definition=result['definition']
    saved=json.loads((source/'periodic-result.json').read_text())
    # A restored archive may live at another path. Its identity is the complete
    # physical checkpoint, mesh and study definition, not the former hostname.
    if definition['source_checkpoint']!=saved['checkpoint_generation'] or definition['source_definition']!=json.loads((source/'study-definition.json').read_text()):
        raise ValueError('Error estimate is attached to a different periodic state')
    checkpoint=source/'checkpoint'/saved['checkpoint_generation']
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.iterdir() if p.is_file()}
    meshes={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('fluid.msh','solid.msh')}
    if not actual or actual!=definition['source_files_sha256'] or meshes!=definition['mesh_sha256']:
        raise ValueError('Error estimate source checkpoint or mesh checksum mismatch')
    if kind=='transient':return {k:v['remaining_at_source'] for k,v in result['estimate'].items()}
    if not result.get('dense_periodic_check'):raise ValueError('Dense periodic sampling check missing or failed')
    return result['errors']


def dense_cycles(receipt_path,source,phases=100):
    # Validate the source association before using a waveform from its continuation.
    attached_estimate(receipt_path,source,'sampling')
    result=json.loads(receipt_path.read_text());start=result['start_cycle'];end=result['end_cycle']
    cfg=json.loads((source/'periodic-result.json').read_text())['config'];steps=round(.1/cfg['fsi']['dt'])
    return {solid:phase_paths(series(receipt_path.parent/(f'dense_restart{start*steps}'+('_solid' if solid else '')+'.pvd')),end,phases) for solid in (False,True)}


def main():
    p=argparse.ArgumentParser()
    for name in ('space-cases','time-cases','transient-results','sampling-results','time-transient-results','time-sampling-results'):
        p.add_argument('--'+name,nargs=3,type=Path,required=True)
    p.add_argument('--policy',choices=['automatic','fixed'],default='automatic')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    definitions=validate_cases(a.space_cases,a.policy);validate_cases(a.time_cases,a.policy)
    space_fields=[dense_cycles(p,w) for p,w in zip(a.sampling_results,a.space_cases)]
    time_fields=[dense_cycles(p,w) for p,w in zip(a.time_sampling_results,a.time_cases)]
    half=lambda fields:{solid:paths[1::2] for solid,paths in fields.items()}
    first=cross_mesh_cycles(space_fields[0],space_fields[1],2);last=cross_mesh_cycles(space_fields[1],space_fields[2],4)
    first50=cross_mesh_cycles(half(space_fields[0]),half(space_fields[1]),2)
    last50=cross_mesh_cycles(half(space_fields[1]),half(space_fields[2]),4)
    sampling_changes=[{k:abs(first[k]-first50[k]) for k in last},{k:abs(last[k]-last50[k]) for k in last}]
    if any(last[k]>=first[k] for k in first):raise ValueError('Spatial field differences must decrease')
    checks={str(work):audit_cycle(work) for work in (*a.space_cases,*a.time_cases)}
    dense_boundaries={};pressure_cycles={}
    for work,fields in zip((*a.space_cases,*a.time_cases),(*space_fields,*time_fields)):
        boundaries=[];pressures=[]
        for fluid,solid in zip(fields[False],fields[True]):
            f=read_snapshot(fluid,False,True);s=read_snapshot(solid,True)
            boundaries.append(channel_boundary_errors(f,s));pressures.append(pressure_drop(f))
        dense_boundaries[str(work)]={k:max(v[k] for v in boundaries) for k in boundaries[0]}
        pressure_cycles[str(work)]=pressures
        if max(dense_boundaries[str(work)].values())>1e-12:raise ValueError('Dense no-slip/interface compatibility failed')
    temporal=[];transient=[];sampling=[];time_transient=[];time_sampling=[]
    for i,(coarse,fine,tail,sample,time_tail,time_sample) in enumerate(zip(a.space_cases,a.time_cases,a.transient_results,a.sampling_results,a.time_transient_results,a.time_sampling_results)):
        left=json.loads((coarse/'periodic-result.json').read_text());right=json.loads((fine/'periodic-result.json').read_text())
        c=physical_config(left['config']);d=physical_config(right['config'])
        if abs(2*d['fsi']['dt']-c['fsi']['dt'])>1e-14:raise ValueError('Expected dt/2 comparison')
        d['fsi']['dt']=c['fsi']['dt']
        if c!=d:raise ValueError('Temporal cases differ beyond time step')
        for name in ('fluid.msh','solid.msh'):
            if hashlib.sha256((coarse/name).read_bytes()).digest()!=hashlib.sha256((fine/name).read_bytes()).digest():raise ValueError('Temporal mesh changed')
        delta=cycle_distance(space_fields[i],time_fields[i]);temporal.append(delta)
        delta50=cycle_distance(half(space_fields[i]),half(time_fields[i]))
        sampling_changes.append({k:abs(delta[k]-delta50[k]) for k in last})
        transient.append(attached_estimate(tail,coarse,'transient'))
        sampling.append(attached_estimate(sample,coarse,'sampling'))
        time_transient.append(attached_estimate(time_tail,fine,'transient'))
        time_sampling.append(attached_estimate(time_sample,fine,'sampling'))
    # Use every mesh's estimate, and the sum for the pair defining the last
    # spatial difference; avoid cancellation of two independently uncertain runs.
    temporal_estimate=[{k:t[k]+a[k]+b[k] for k in last} for t,a,b in zip(temporal,transient,time_transient)]
    estimates={name:{k:max(values[0][k],values[1][k]+values[2][k]) for k in last}
               for name,values in [('temporal',temporal_estimate),('transient',transient)]}
    estimates['sampling']={k:max(v[k] for v in sampling_changes) for k in last}
    budget=error_budget(last,**estimates)
    result=dict(observed_spatial_orders={k:math.log(first[k]/last[k],2) for k in first},norm="Reference-volume-normalized lumped nodal L2; phase RMS",phases=100,sampling_metric="Change in reported phase-RMS differences from 50 to 100 actual samples",sampling_changes=sampling_changes,definitions=definitions,difference_2_4=first,difference_4_8=last,checks=checks,dense_boundary_errors=dense_boundaries,pressure_cycles=pressure_cycles,
                temporal_by_mesh=temporal,transient_by_mesh=transient,sampling_by_mesh=sampling,
                time_transient_by_mesh=time_transient,time_sampling_by_mesh=time_sampling,estimates=estimates,budget=budget,
                limitation='Measured dt refinement and empirical contraction estimates; not rigorous continuum-error bounds')
    result['stabilization_policy']=a.policy
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if not budget['passed']:raise RuntimeError('The complete 10% error budget has not passed')


if __name__=='__main__':main()
