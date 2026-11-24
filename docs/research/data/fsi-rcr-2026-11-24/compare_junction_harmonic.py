"""Audit rigid spatial references and periodic 3D port exchange for an occluded T inlet."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import sys

import numpy as np

from junction_harmonic import generalized_alpha_symbol
from junction_startup import compare as startup_errors
from junction_periodic import fourier
from branch_external import observations
from study_rigid_tube import read_mesh
from verify_fsi_inlet import Runner,check_rcr_history


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cp(z):
    return complex(*z)


def verify_case(cfg,hz,samples,steps,tau,elastic):
    f=cfg['fsi']
    inlet=f['inlet']
    if (cfg['time']!={'scheme':'generalized_alpha','rho_infinity':.5} or f['material']!='linear'
            or (inlet['tag'],inlet['ramp_time'])!=(1,0.)
            or any(inlet['flow_rate'][k]!=0. for k in ('mean','amplitude'))
            or inlet['flow_rate']['period']!=1/hz or f['dt']!=1/(samples*hz)
            or f['steps']!=steps or f.get('stabilization_tau')!=tau):
        raise ValueError('Physical input differs from recorded parameters')
    dom=f['domains']
    clamped={b['tag'] for b in dom['solid_constraints'] if sorted(b['components'])==[0,1,2]}
    if clamped!=({11,12,13} if elastic else {11,12,13,14,15}):
        raise ValueError('Unexpected wall constraints')
    ports=dom['rcr_outlets']
    if [p['tag'] for p in ports]!=[2,3] or sorted(dom['pressure_tags'])!=[2,3]:
        raise ValueError('Missing or reordered circuit tag')
    for port,rp,rd,c,pd in zip(ports,(3.,12.),(8.,32.),(.025,.0125),(.02,-.02)):
        if ((port['proximal_resistance'],port['distal_resistance'],port['compliance'])!=(rp,rd,c)
                or port['distal_pressure']!=0. or port['initial_capacitor_pressure']!=0.
                or port['distal_pressure_time']!=dict(amplitude=pd,period=1/hz)):
            raise ValueError('Unexpected RCR or prescribed forcing')
    return ports


def pack(root,exe,readers):
    sys.path.append(str(readers.resolve()))
    from study_hydrostatic_fsi import recovered_state
    refs=[]
    meshes={}
    for path in sorted((root/'junction-harmonic').glob('g*.json')):
        r=json.loads(path.read_text())
        mesh=root/'junction-harmonic'/f"g{r['refinement']}"/'fluid.msh'
        if sha(mesh)!=r['fluid_sha256']:raise ValueError('Changed reference mesh')
        meshes[r['refinement']]=r['fluid_sha256']
        refs.append(r)
    all_runs=[]
    for path in sorted((root/'junction-periodic').glob('g*/result.json')):
        r=json.loads(path.read_text())
        case=path.parent
        for f,digest in r['input_output_sha256'].items():
            if sha(case/f)!=digest:raise ValueError('Changed '+str(case/f))
        if sha(exe)!=r['executable_sha256'] or meshes[r['refinement']]!=sha(case/'fluid.msh'):
            raise ValueError('Mismatched executable or lumen')
        cfg=json.loads((case/'coupled.json').read_text())
        geo=json.loads((case/'geometry.json').read_text())
        f=cfg['fsi']
        models=verify_case(cfg,r['frequency_hz'],r['samples'],r['cycles']*r['samples'],r.get('fixed_pspg',.01),r['elastic'])
        with (case/'coupled.csv').open() as stream:
            rows=[{k:float(v) for k,v in rec.items()} for rec in csv.DictReader(stream)]
        n=r['samples']
        if (len(rows)!=r['cycles']*n or any(row['step']!=j or abs(row['time']-j*f['dt'])>2e-11
                                            for j,row in enumerate(rows,1))):
            raise ValueError('Missing or displaced accepted time')
        audit=Runner(exe,'mpiexec',case,interface_area=geo['interface_area'],singleton=True)
        closure=max(check_rcr_history(audit,'coupled',m,rows,sole_pressure=False) for m in models)
        mesh=read_mesh(case/'fluid.msh')
        state=recovered_state(case,'coupled',mesh,False,1)
        checked=observations(mesh,state)
        if (abs(closure-r['stage_closure'])>1e-15 or abs(checked['volume_gain']-r['last_vtu']['volume_gain'])>1e-12
                or max(abs(a-b) for a,b in zip(checked['flux'],r['last_vtu']['flux']))>1e-15):
            raise ValueError('Independent VTU or stage balance differs')
        cols=['time']+[f'endpoint_{s}_{t}' for t in (2,3) for s in ('rcr_flow','rcr_pressure','capacitor_pressure','distal_pressure')]
        all_runs.append(dict(case=case.name,report=r,previous_and_last_cycles=[{k:row[k] for k in cols} for row in rows[-2*n:]]))
    startups=[]
    for path in sorted((root/'junction-startup').glob('*/result.json')):
        case=path.parent
        r=json.loads(path.read_text())
        if sha(exe)!=r['executable_sha256'] or meshes[r['grid']]!=sha(case/'fluid.msh'):
            raise ValueError('Mismatched startup executable or mesh')
        for name,digest in r['sha256'].items():
            if sha(case/name)!=digest:raise ValueError('Changed startup field, history or input')
        cfg=json.loads((case/'startup.json').read_text())
        geo=json.loads((case/'geometry.json').read_text())
        ports=verify_case(cfg,r['hz'],r['samples'],r['steps'],r['tau'],False)
        with (case/'startup.csv').open() as stream:
            full=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
        rows=[{k:row[k] for k in r['three_dimensional'][0]} for row in full]
        if rows!=r['three_dimensional'] or [row['step'] for row in rows]!=list(range(1,r['steps']+1)):
            raise ValueError('Incomplete raw startup trace')
        audit=Runner(exe,'mpiexec',case,interface_area=geo['interface_area'],singleton=True)
        closure=max(check_rcr_history(audit,'startup',m,full,sole_pressure=False) for m in ports)
        if abs(closure-r['circuit_residual'])>1e-15:
            raise ValueError('Independent startup circuit closure differs')
        mesh=read_mesh(case/'fluid.msh')
        field=recovered_state(case,'startup',mesh,False,1)
        check=observations(mesh,field)
        if (max(abs(a-b) for a,b in zip(check['flux'],r['deformed_cap']['flux']))>1e-15
                or abs(check['volume_gain']-r['deformed_cap']['volume_gain'])>1e-12):
            raise ValueError('Independent startup cap flux changed')
        startups.append(dict(case=case.name,report=r))
    return dict(references=refs,three_dimensional=all_runs,startups=startups)


def reference_rows(refs):
    rows=[]
    lookup={}
    for ref in refs:
        for r in ref['runs']:
            hz,n=r['hz'],r.get('steps_per_cycle',0)
            rate,forcing=generalized_alpha_symbol(hz,n)
            y=np.array([[cp(z) for z in row] for row in r['admittance']])
            lumen=cp(r['differential_lumen_impedance'])
            rp,rd,c=np.array(r['resistances_capacitance']).T
            h=1/(1+rate*rd*c)
            z=rp+rd*h
            p=np.array(r['prescribed_reservoir_pressures'])*forcing
            q=-(p[0]*h[0]-p[1]*h[1])/(lumen+sum(z))
            q2,q3=map(cp,r['outlet_flows'])
            pb=np.array([cp(v) for v in r['port_pressures']])
            pc=np.array([cp(v) for v in r['capacitor_pressures']])
            if max(abs(q-q2),abs(q2+q3),max(abs(y@pb-[q2,q3])))>1e-10*abs(q2):
                raise ValueError('Independent scalar network and admittance do not give observed port flows')
            if max(abs(pb-rp*np.array([q2,q3])-pc))>1e-12:raise ValueError('Terminal pressure loss differs')
            key=ref['refinement'],ref['order'],ref['fixed_pspg'],hz,n
            if key in lookup:
                old=lookup[key]
                if max(abs(old[0]/q2-1),abs(old[1]/q3-1),max(abs(old[2]/pb-1)),max(abs(old[3]/pc-1)))>1e-8:
                    raise ValueError(f'Independent factorizations differ at {key}')
            else:
                lookup[key]=(q2,q3,pb,pc)
            rows.append(dict(grid=key[0],order=key[1],tau=key[2],hz=hz,steps_per_cycle=n,solver=r.get('solver','direct'),krylov_max=max(r.get('iterations',[]) or [0]),tets=ref['tets'],
                             unknowns=ref['unknowns'],lumen_resistance=lumen.real,lumen_reactance=lumen.imag,
                             flow2_amplitude=abs(q2),flow2_phase_deg=np.angle(q2,deg=True),
                             flow3_amplitude=abs(q3),flow3_phase_deg=np.angle(q3,deg=True),
                             port2_amplitude=abs(pb[0]),port3_amplitude=abs(pb[1]),
                             common_pressure_error=r['common_flow_pressure_error'],mass_error=r['mass_defect'],
                             power_error=r['physical_power_defect'],stabilized_power_defect=r['stabilized_power_defect'],
                             pressure_gradient_work_over_port_power=r['pressure_gradient_work_over_port_power'],weak_error=r['weak_defect']))
    return sorted(rows,key=lambda r:(r['grid'],r['order'],r['tau'] or 0,r['hz'],r['steps_per_cycle'])),lookup


def tables(data):
    refs,lookup=reference_rows(data['references'])
    results=[]
    for run in data['three_dimensional']:
        r=run['report']
        g,hz,n,tau=r['refinement'],r['frequency_hz'],r['samples'],r.get('fixed_pspg',.01)
        samples=run['previous_and_last_cycles']
        if len(samples)!=2*n:raise ValueError('Missing measured cycles')
        def pick(order,coefficient,steps):
            return lookup.get((g,order,coefficient,hz,steps))
        continuous=pick(1,tau,0)
        discrete=pick(1,tau,n)
        taylor=pick(2,None,0)
        if not r['elastic'] and (continuous is None or discrete is None):raise ValueError('Missing like-for-like flow reference')
        for idx,port in enumerate(r['ports']):
            tag=idx+2
            drift=0.
            for field,stored in port.items():
                k=f'endpoint_{field}_{tag}'
                z=fourier(samples[-n:],k,hz)
                prev=fourier(samples[:n],k,hz)
                drift=max(drift,max(abs(a[k]-b[k]) for a,b in zip(samples[:n],samples[n:]))/abs(z))
                if (abs(z-cp(stored['phasor']))>1e-12*abs(z)
                        or abs(abs(z-prev)/abs(z)-stored['cycle_change'])>1e-12
                        or min(s[k] for s in samples[-n:])!=stored['minimum'] or max(s[k] for s in samples[-n:])!=stored['maximum']):
                    raise ValueError('Port harmonic, cycle change or reversal differs')
            flow=cp(port['rcr_flow']['phasor'])
            pressure=cp(port['rcr_pressure']['phasor'])
            def error(ref,quantity):
                if ref is None or r['elastic']:return None
                target=ref[idx] if quantity=='flow' else ref[2][idx]
                return 100*abs((flow if quantity=='flow' else pressure)/target-1)
            results.append(dict(case=run['case'],grid=g,hz=hz,steps=n,cycles=r['cycles'],elastic=r['elastic'],tag=tag,tau=tau,
                                amplitude=abs(flow),phase_deg=np.angle(flow,deg=True),mean=port['rcr_flow']['mean'],
                                minimum_flow=port['rcr_flow']['minimum'],maximum_flow=port['rcr_flow']['maximum'],
                                cycle_change_pct=100*port['rcr_flow']['cycle_change'],worst_cycle_waveform_change_pct=100*drift,
                                periodic_within_0p1_pct=drift<1e-3,terminal_amplitude=abs(pressure),
                                continuous_p1_flow_gap_pct=error(continuous,'flow'),discrete_p1_flow_gap_pct=error(discrete,'flow'),
                                continuous_p2_flow_gap_pct=error(taylor,'flow'),discrete_p1_pressure_gap_pct=error(discrete,'pressure'),
                                max_net_outflow_over_amplitude=r['max_net_outflow_over_amplitude'],
                                max_volume_change=r['max_volume_change'],max_stage_defect=r['stage_closure'],vtu_flux_error=r['history_vtu_flow_error']))
    startup=[]
    for case in data['startups']:
        r=case['report']
        metrics=startup_errors(r['reference'],r['three_dimensional'])
        if metrics!=r['relative_error']:raise ValueError('Startup comparison differs')
        startup.append(dict(case=case['case'],grid=r['grid'],steps=r['steps'],steps_per_cycle=r['samples'],tau=r['tau'],
                            initial_tau=r.get('initial_tau',r['tau']),later_tau=r.get('later_tau',r['tau']),frequency_hz=r['hz'],mixed_unknowns=r['unknowns'],**metrics,circuit_defect=r['circuit_residual']))
    return refs,results,startup


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    src=cli.add_mutually_exclusive_group(required=True)
    src.add_argument('--runs',type=Path)
    src.add_argument('--archive',type=Path)
    cli.add_argument('--write-archive',type=Path)
    cli.add_argument('--executable',type=Path)
    cli.add_argument('--reference-scripts',type=Path)
    cli.add_argument('--reference-csv',type=Path,required=True)
    cli.add_argument('--solver-csv',type=Path,required=True)
    cli.add_argument('--startup-csv',type=Path,required=True)
    a=cli.parse_args()
    if a.runs and not (a.executable and a.reference_scripts):cli.error('Raw verification requires executable and pinned field readers')
    data=pack(a.runs,a.executable,a.reference_scripts) if a.runs else json.loads(lzma.decompress(a.archive.read_bytes()))
    refs,solves,startup=tables(data)
    for path,rows in ((a.reference_csv,refs),(a.solver_csv,solves),(a.startup_csv,startup)):
        if not rows:raise ValueError('No complete samples')
        with path.open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n')
            w.writeheader()
            w.writerows(rows)
    if a.write_archive:
        a.write_archive.write_bytes(lzma.compress(json.dumps(data,allow_nan=False,separators=(',',':')).encode()))
    print(len(refs),'complex operators and',len(solves)//2,'forced trajectories and',len(startup),'startup trajectories')


if __name__=='__main__':
    main()
