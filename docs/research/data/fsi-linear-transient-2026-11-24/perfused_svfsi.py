"""Run the dimensional perfused quarter-tube in the pinned unmodified svFSI solver."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from harmonic_eon import SurfaceAudit, digest
from audit_reflection import measured_ring_strains
from perfused_eon import periodic_modes
from perfused_tube import AMPLITUDE, C, RD, RP
from scaled_tube import problem, write_mesh
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from svfsi_history import check_convergence


def boundary(name, block):
    return '   Add BC: '+name+' {\n'+''.join('      '+line+'\n' for line in block)+'   }\n'


def deck(helpers, m, n, dt, interval, rigid, moving_outlet=False):
    text = f"""Continue previous simulation: 0
Number of spatial dimensions: 3
Number of time steps: {n}
Time step size: {dt:.17g}
Spectral radius of infinite time step: 0.5
Save results to VTK format: t
Name prefix of saved VTK files: result
Increment in saving VTK files: {interval}
Start saving after time step: 1
Increment in saving restart files: {n}
Verbose: 1
Warning: 1

""" + helpers.mesh_block('lumen',helpers.FLUID_FACES,0)
    fluid = f"""Density: {m.fluid_density:.17g}
      Viscosity: Constant {{ Value: {m.viscosity:.17g} }}
      Backflow stabilization coefficient: 0
"""
    common = """   Coupled: 1
   Min iterations: 2
   Max iterations: 40
   Tolerance: 1e-8
"""
    if rigid:
        text += 'Add equation: fluid {\n'+common+'   '+fluid
    else:
        text += helpers.mesh_block('wall',helpers.SOLID_FACES,1)+"""Add projection: interface_solid {
   Project from face: interface_fluid
}
Add equation: FSI {
""" + common + '   Domain: 0 {\n      Equation: fluid\n      ' + fluid + f"""   }}
   Domain: 1 {{
      Equation: lElas
      Density: {m.solid_density:.17g}
      Elasticity modulus: {m.young:.17g}
      Poisson ratio: {m.poisson:.17g}
   }}
"""
    text += """   LS type: GMRES {
      Tolerance: 1e-10
      Absolute tolerance: 1e-23
      Max iterations: 20
      Krylov space dimension: 450
   }
   Output: Spatial {
      Velocity: t
      Pressure: t
"""
    text += ('   }\n' if rigid else '      Displacement: t\n   }\n   Output: Alias {\n      Displacement: FS_Displacement\n   }\n')
    text += boundary('fluid_in',['Type: Dir','Time dependence: Unsteady','Fourier coefficients file path: flow.fcs',
                                 'Impose flux: t','Zero out perimeter: f','Profile: User_defined','Spatial profile file path: profile.dat'])
    text += boundary('fluid_out',['Type: Neu','Time dependence: RCR',f'RCR values: ({4*RP:g}, {C/4:.17g}, {4*RD:g})',
                                  'Distal pressure: 0','Initial pressure: 0'])
    for name, direction in (('fluid_y','(0,1,0)'),('fluid_z','(0,0,1)')):
        text += helpers.roller(name,direction)
    if rigid:
        return text+helpers.roller('interface_fluid','(1,1,1)')+'}\n'
    for name,direction,integral in [('wall_in','(1,1,1)',True),('wall_out','(1,0,0)' if moving_outlet else '(1,1,1)',True),
                                    ('wall_y','(0,1,0)',False),('wall_z','(0,0,1)',False)]:
        text += helpers.roller(name,direction,integral)
    text += '}\nAdd equation: mesh {\n'+common+"""   Poisson ratio: 0.3
   LS type: CG {
      Tolerance: 1e-10
      Absolute tolerance: 1e-23
      Max iterations: 2000
   }
   Output: Spatial {
      Displacement: t
   }
"""
    for name, direction in [('fluid_in','(1,1,1)'),('fluid_out','(1,0,0)' if moving_outlet else '(1,1,1)'),('fluid_y','(0,1,0)'),('fluid_z','(0,0,1)')]:
        text += helpers.roller(name,direction)
    return text+'}\n'


def read_native_fields(snapshot, mesh, rigid):
    from compare_svfsi_wall import external_fields
    from compare_svfsi_womersley_fields import read_svfsi_state
    from study_hydrostatic_fsi import PointState

    if not rigid:
        return external_fields(snapshot, mesh)
    raw = read_svfsi_state(snapshot, mesh[0][0], mesh[0][1])
    fluid = {i:PointState((0.,0.,0.), v[:3], v[3]) for i,v in raw.items()}
    wall = {i:PointState((0.,0.,0.), (0.,0.,0.), 0.) for i in mesh[1][0]}
    return [fluid, wall]


def observed_loads(log, native, load, period, n, pressure_scale, old_pressures=None):
    rows = {}
    for line in log.splitlines():
        tokens = line.split()
        if tokens[:2] != ['pressure_observer', 'fluid_out']:
            continue
        if len(tokens) != 8:
            raise ValueError('Invalid native traction observer')
        step, iteration = map(int, tokens[2:4])
        time, alpha, lo, hi = map(float, tokens[4:])
        if (abs(time - step*period/n) > 1e-11*period or abs(alpha - 2/3) > 1e-13
                or abs(lo-hi) > 1e-12*pressure_scale or iteration <= rows.get(step, [0])[0]):
            raise ValueError('Nonuniform load, wrong stage or repeated observer correction')
        rows[step] = [iteration, alpha, .5*(lo+hi)]
    if load == 'native' and not rows:
        return None
    if sorted(rows) != list(range(1,len(native)+1)):
        raise ValueError('Missing native traction observation')
    previous, max_error = 0., 0.
    for step, (_, _, endpoint, _) in enumerate(native, 1):
        _, alpha, measured = rows[step]
        old = previous if old_pressures is None else old_pressures[step-1]
        expected = alpha*endpoint + (1-alpha)*old if load=='stage' else endpoint
        max_error = max(max_error, abs(measured-expected)/pressure_scale)
        previous = endpoint
    if max_error > 2e-6:
        raise ValueError(f'Actual native traction differs from declared time level by {max_error}')
    return dict(max_error_over_RQ=max_error, final_correction_pressure_pa=[v[2] for _,v in sorted(rows.items())])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('work','case','executable','libs','reference-scripts'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--hz',type=float,default=1.)
    p.add_argument('--steps-per-cycle',type=int,default=32)
    p.add_argument('--cycles',type=int,default=6)
    p.add_argument('--samples',type=int,default=8)
    p.add_argument('--rigid',action='store_true')
    p.add_argument('--audit-only',action='store_true')
    p.add_argument('--moving-outlet',action='store_true')
    p.add_argument('--load',choices=('native','endpoint-observer','stage'),default='native',
                   help='Executable variant; observed variants must print the applied residual traction')
    args=p.parse_args()
    n,hz,peak=args.steps_per_cycle,args.hz,AMPLITUDE
    if min(n,hz,peak)<=0 or args.samples<8 or n%args.samples or args.cycles<4:
        p.error('Need paired complete cycles and at least eight equally spaced fields per cycle')
    sys.path.append(str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as helpers
    from study_rigid_tube import read_mesh
    work=args.work.resolve()
    m=problem('arterial')[0]
    period=1/hz
    dt=period/n
    total=args.cycles*n
    interval=n//args.samples
    inp=deck(helpers,m,total,dt,1 if args.moving_outlet else interval,args.rigid,args.moving_outlet)
    if not args.audit_only:
        work.mkdir(parents=True,exist_ok=False)
        for domain, tags, name in [('lumen',helpers.FLUID_FACES,'fluid.msh'),('wall',helpers.SOLID_FACES,'solid.msh')]:
            write_mesh(args.case/name,work/name,m)
            if not args.rigid or domain=='lumen':
                helpers.export_mesh(work/name,work,domain,tags)
        from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
        reader=vtkXMLPolyDataReader()
        reader.SetFileName(str(work/'fluid_in.vtp'))
        reader.Update()
        face=reader.GetOutput()
        ids=face.GetPointData().GetArray('GlobalNodeID')
        if reader.GetErrorCode() or ids is None or ids.GetNumberOfTuples()!=face.GetNumberOfPoints():
            raise ValueError('Missing exported parent IDs for the actual native inlet')
        profile={}
        for j in range(face.GetNumberOfPoints()):
            node=int(ids.GetTuple1(j))
            x,y,z=face.GetPoint(j)
            if node<=0 or node in profile or abs(x)>1e-13*m.length:
                raise ValueError('Invalid native inlet node or position')
            profile[node]=max(0.,1-(y*y+z*z)/m.radius**2)
        (work/'profile.dat').write_text(''.join(f'{i} {v:.17g}\n' for i,v in sorted(profile.items())))
        (work/'flow.fcs').write_text(f'0\n{period:.17g}\n0\n0\n2\n0 0\n0 {peak/4:.17g}\n')
        (work/'svFSI.inp').write_text(inp)
        (work/'executable.sha256').write_text(digest(args.executable)+'\n')
        env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                 OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp')
        with (work/'solve.log').open('w') as stream:
            subprocess.run([args.executable.resolve(),'svFSI.inp'],cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=14400)
    if inp!=(work/'svFSI.inp').read_text() or digest(args.executable)!=(work/'executable.sha256').read_text().strip():
        raise ValueError('Different native equation or binary')
    data=work/'1-procs'
    logs=(data/'histor.dat').read_text()
    conv={eq:check_convergence(logs,total,eq) for eq in (('NS',) if args.rigid else ('FS','MS'))}
    mesh=[read_mesh(work/k) for k in ('fluid.msh','solid.msh')]
    audit=SurfaceAudit(mesh[0],(1,2,3))
    native=[list(map(float,row.split())) for row in (data/'RCR.dat').read_text().splitlines()]
    if len(native)!=total or any(len(row)!=4 or not all(map(math.isfinite,row)) for row in native):
        raise ValueError('Incomplete single-port terminal history')
    pc_prev,oldq=0.,0.
    decay=-math.expm1(-dt/(RD*C))
    pscale=peak*(RD+RP)
    checks=dict(relative_port_pressure=0.,relative_capacitor_recurrence=0.,inlet_flux_relative=0.,outlet_vtu_relative=0.)
    samples=[]
    # Native IntegV calls GNNB, which forms the surface from x + Do. Both old and
    # new velocities in this step use that old geometry. Retain both physical traces.
    old_pressures=[] if args.moving_outlet else None
    previous_field=np.zeros((len(audit.ids),7)) if args.moving_outlet else None
    previous_endpoint_q=0.
    previous_printed_pc=0.
    maximum_geometry_effect=0.
    for step,(t,pc,pout,q) in enumerate(native,1):
        if abs(t-step*dt)>6e-7*max(1,abs(t)):raise ValueError('Incorrect native circuit time')
        state=None
        snapshot=data/f'result_{step:03d}.vtu'
        if args.moving_outlet:
            state=read_native_fields(snapshot,mesh,args.rigid)
            field=audit.array(state[0])
            lagged=field.copy()
            lagged[:,:3]=previous_field[:,:3]
            old_area_q=audit.observe(lagged,0.,m.viscosity)[2]['outward_flow']
            current_q=audit.observe(field,0.,m.viscosity)[2]['outward_flow']
            checks['outlet_vtu_relative']=max(checks['outlet_vtu_relative'],4*abs(old_area_q-q)/peak)
            maximum_geometry_effect=max(maximum_geometry_effect,4*abs(current_q-old_area_q)/peak)
            oldq=previous_endpoint_q
            old_pressures.append(previous_printed_pc+4*RP*oldq)
            previous_endpoint_q=current_q
            previous_field=field
            previous_printed_pc=pc
        pc_prev=(1-decay)*pc_prev+4*RD*(oldq*decay+(q-oldq)*(1-RD*C*decay/dt))
        oldq=q
        checks['relative_port_pressure']=max(checks['relative_port_pressure'],abs(pout-pc-4*RP*q)/pscale)
        checks['relative_capacitor_recurrence']=max(checks['relative_capacitor_recurrence'],abs(pc-pc_prev)/pscale)
        if step<=total-2*n or step%interval:
            continue
        if state is None:
            state=read_native_fields(snapshot,mesh,args.rigid)
        time=step*dt
        src=audit.array(state[0])
        ports=audit.observe(src,pout,m.viscosity)
        pos,area=measured_ring_strains(mesh[1],state[1])
        qi,qo=-4*ports[1]['outward_flow'],4*ports[2]['outward_flow']
        checks['inlet_flux_relative']=max(checks['inlet_flux_relative'],abs(qi/peak-math.sin(2*np.pi*hz*time)))
        if not args.moving_outlet:
            checks['outlet_vtu_relative']=max(checks['outlet_vtu_relative'],abs(qo-4*q)/peak)
        samples.append(dict(step=step,time=time,full_inlet=qi,full_outlet=qo,full_wall_flux=4*ports[3]['outward_flow'],
                            full_volume=4*audit.volume(src),inlet_mean_pressure=ports[1]['mean_pressure'],
                            outlet_mean_pressure=ports[2]['mean_pressure'],circuit_pressure=pout,capacitor_pressure=pc,
                            area_strain=area,file_sha256=digest(snapshot)))
    if max(checks.values())>2e-6 or len(samples)!=2*args.samples:
        raise ValueError('Native capacitor, imposed inlet or field flux differs: '+str(checks))
    modes,change=periodic_modes(samples,hz,peak,pscale,m.lame_area_strain(pscale))
    report=dict(parameters=asdict(m),frequency_hz=hz,steps_per_cycle=n,cycles=args.cycles,samples_per_cycle=args.samples,
                rigid=args.rigid,model=args.load,outlet_tangential_motion=args.moving_outlet,full_amplitude=peak,full_rcr_si=[RP,RD,C],quarter_fraction=.25,
                sections=pos,observations=samples,phasors=modes,checks=checks,last_cycle_change=change,
                periodic_pass=max(change.values())<1e-3,convergence=conv,executable_sha256=digest(args.executable),
                files={k:digest(work/k) for k in ('fluid.msh','solid.msh','svFSI.inp','flow.fcs','profile.dat','1-procs/histor.dat','1-procs/RCR.dat')})
    report['applied_load'] = observed_loads((work/'solve.log').read_text(), native, args.load, period, n, pscale,old_pressures)
    if args.moving_outlet:
        report['previous_port_pressures_pa']=old_pressures
        report['maximum_geometry_flux_change_over_inlet']=maximum_geometry_effect
    report['files']['solve.log'] = digest(work/'solve.log')
    (work/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(hz,n,args.rigid,report['periodic_pass'],checks,change,flush=True)


if __name__=='__main__':
    main()
