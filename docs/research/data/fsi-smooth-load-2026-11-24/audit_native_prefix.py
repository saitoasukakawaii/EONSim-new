"""Audit a saved native field and its finite, converged history before a later failed solve."""
import argparse
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys

from audit_reflection import measured_ring_strains
from audit_study import eon_loads,external_loads
from audit_vertex_order import read_states
from svfsi_history import check_convergence,equation_iterations


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def history_through(raw,end):
    return '\n'.join(line for line in raw.splitlines() if (m:=re.match(r'^\s*(?:FS|MS)\s+(\d+)-',line)) and int(m[1])<=end)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('case','dae','reference-scripts','output'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--step',type=int,required=True)
    a=p.parse_args()
    sys.path.append(str(a.reference_scripts.resolve()))
    import compare_svfsi_wall as wall
    import study_hydrostatic_fsi as fsi
    from study_rigid_tube import read_mesh
    cfg=json.loads((a.case/'eon/case.json').read_text())['fsi']
    n,dt,peak=cfg['steps'],cfg['dt'],cfg['pressure']
    if a.step<=0 or a.step>=n or dt!=1/n:raise ValueError('Expected an interior snapshot of a one-second ramp')
    t=a.step*dt
    native=a.case/'matched'
    raw=(native/'1-procs/histor.dat').read_text()
    # Stop at the first failed linear correction after the snapshot. Bound parsing
    # to that time so a later overflow cannot invalidate the earlier raw observations.
    first=None
    for eq in ('FS','MS'):
        history=raw if first is None else history_through(raw,first['step'])
        for row in equation_iterations(history,eq):
            if row.linear_failed and (row.linear_iterations or row.residual>1e-8):
                if first is None or (row.step,row.number)<(first['step'],first['number']):
                    first=dict(equation=eq,**row._asdict())
                break
    if first is None or first['step']<=a.step:raise ValueError('Need a separate failed correction after the saved field')
    end=first['step']-1
    prefix=history_through(raw,end)
    limits={eq:check_convergence(prefix,end,eq) for eq in ('FS','MS')}
    load=external_loads(native,n,'matched',peak,through_step=end)
    base=eon_loads(a.case/'eon',n,peak)
    mismatch=max(abs(value['min_pressure']-base[key]['min_pressure']) for key,value in load.items())
    if len(load)!=2*end or mismatch>3e-15:raise ValueError('Mismatched pressure load in retained history')
    ref=json.loads(lzma.decompress(a.dae.read_bytes()))
    meshfile=[a.case/'reference'/(domain+'.msh') for domain in ('fluid','solid')]
    for file in meshfile:
        if digest(file)!=ref['input_sha256'][file.name]:raise ValueError('Independent operator and snapshot meshes differ')
    if digest(native/'lumen.vtu')!=ref['lumen_vtu_sha256']:raise ValueError('Native and DAE fluid VTK meshes differ')
    meshes=[read_mesh(file) for file in meshfile]
    fields=read_states(a.case,meshes,a.step,wall,fsi)
    discrete=[s for r in ref['runs'] if r['source_steps']==n and r['mode']=='native' for h in r['time_study']
              if h['steps']==512 for s in h['samples'] if s['time']==t]
    if len(discrete)!=1:raise ValueError('Missing independent DAE snapshot')
    stations=ref['sections']
    strains={'native_dae':discrete[0]['section_area_strain']}
    peak_fields={}
    for name,(fluid,solid) in fields.items():
        pos,v=measured_ring_strains(meshes[1],solid)
        if pos!=stations:raise ValueError('Observed VTU sections differ from independent DAE')
        strains[name]=v
        peak_fields[name]=dict(fluid_pressure=max(abs(x.pressure) for x in fluid.values()),
                               fluid_speed=max(math.hypot(*x.velocity) for x in fluid.values()),
                               wall_displacement=max(math.hypot(*x.displacement) for x in solid.values()))
    static=2*(1+.3)*((1-2*.3)+1.2**2)/(100*(1.2**2-1))*peak
    def gap(a,b):return 100*max(abs(u-v) for u,v in zip(strains[a],strains[b]))/static
    bad=history_through(raw,first['step']).splitlines()
    corrections={eq:[r._asdict() for r in equation_iterations('\n'.join(bad),eq) if r.step==first['step'] and r.number<=first['number']] for eq in ('FS','MS')}
    files=[*meshfile,native/'svFSI.inp',native/'lumen.vtu',native/f'1-procs/result_{a.step:03d}.vtu',
           a.case/'eon/case.json',a.case/'eon'/f'tube_step{a.step}.vtu',a.case/'eon'/f'tube_step{a.step}_solid.vtu']
    result=dict(planned_steps=n,dt=dt,sample_time=t,sample_step=a.step,last_wholly_converged_step=end,
                first_failed_linear=first,first_failed_time=first['step']*dt,corrections_at_failure=corrections,
                strict_fs_ms_through_prefix=limits,prefix_history_sha256=hashlib.sha256(prefix.encode()).hexdigest(),
                prefix_port_observations=len(load),max_applied_pressure_difference=mismatch,stations=stations,static_area_strain=static,
                area_strains=strains,peak_fields=peak_fields,eon_native_max_gap_pct_static=gap('eonsim','svfsi'),
                dae_native_max_gap_pct_static=gap('native_dae','svfsi'),sha256={str(v.relative_to(a.case)):digest(v) for v in files},
                executable_sha256={k:(a.case/k/'executable.sha256').read_text().strip() for k in ('matched','eon')},
                dae_sha256=digest(a.dae))
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(t,'s;',end,'fully checked steps;',first,'; native area increase (%)',100*strains['svfsi'][0])


if __name__=='__main__':main()
