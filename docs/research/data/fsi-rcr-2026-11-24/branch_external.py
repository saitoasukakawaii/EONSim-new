"""Compare the same linear-elastic three-dimensional T-junction and two RCR loads in EONSim and svFSI."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'cases/fsi'),str(ROOT/'tests')]
from compare_svfsi_womersley_fields import read_svfsi_state
from generate_branched import generate
from study_rigid_tube import cross, determinant, read_mesh, sub
from svfsi_history import check_convergence
from svfsi_mesh import export_mesh
from verify_fsi_inlet import Runner, check_rcr_history

FLUID={1:'inlet',2:'positive_y',3:'negative_y',4:'interface_fluid'}
SOLID={11:'wall_in',12:'positive_wall',13:'negative_wall',14:'interface_solid',15:'outside'}


def prepare(source, target, cfg, helpers, rigid):
    target.mkdir()
    meshes=[read_mesh(source/name) for name in ('fluid.msh','solid.msh')]
    export_mesh(source/'fluid.msh',target,'lumen',FLUID)
    if not rigid:
        export_mesh(source/'solid.msh',target,'wall',SOLID)
    nodes,_,faces=meshes[0]
    inlet=sorted({n for tag,face in faces if tag==1 for n in face})
    # Only the normalized nodal shape matters when Impose flux is active.
    (target/'profile.dat').write_text(''.join(f'{n} {max(0.,1-(nodes[n][1]/.25)**2)*max(0.,1-(nodes[n][2]/.25)**2):.17g}\n' for n in inlet))
    f=cfg['fsi']
    q=f['inlet']['flow_rate']
    (target/'flow.fcs').write_text(f"0\n{q['period']:.17g}\n0\n0\n2\n0 0\n0 {q['amplitude']:.17g}\n")
    deck=f"""Continue previous simulation: 0
Number of spatial dimensions: 3
Number of time steps: {f['steps']}
Time step size: {f['dt']:.17g}
Spectral radius of infinite time step: {cfg['time']['rho_infinity']}
Save results to VTK format: t
Name prefix of saved VTK files: result
Increment in saving VTK files: {f['output_interval']}
Start saving after time step: 1
Increment in saving restart files: {f['steps']}
Verbose: 1
Warning: 1

"""+helpers.mesh_block('lumen',FLUID,0)
    if rigid:
        deck+="""Add equation: fluid {
   Coupled: 1
   Min iterations: 2
   Max iterations: 40
   Tolerance: 1e-10
   Density: 1
   Viscosity: Constant { Value: 1 }
   Backflow stabilization coefficient: 0
"""
    else:
        deck+=helpers.mesh_block('wall',SOLID,1)+"""
Add projection: interface_solid {
   Project from face: interface_fluid
}
Add equation: FSI {
   Coupled: 1
   Min iterations: 2
   Max iterations: 40
   Tolerance: 1e-10
   Domain: 0 {
      Equation: fluid
      Density: 1
      Viscosity: Constant { Value: 1 }
      Backflow stabilization coefficient: 0
   }
   Domain: 1 {
      Equation: lElas
      Density: 1
      Elasticity modulus: 100
      Poisson ratio: 0.3
   }
"""
    deck+="""   LS type: GMRES {
      Tolerance: 1e-11
      Absolute tolerance: 1e-23
      Max iterations: 20
      Krylov space dimension: 450
   }
   Output: Spatial {
"""
    if not rigid:
        deck+="      Displacement: t\n"
    deck+="""      Velocity: t
      Pressure: t
   }
"""
    if not rigid:
        deck+="""   Output: Alias {
      Displacement: FS_Displacement
   }
"""
    deck+="""   Add BC: inlet {
      Type: Dir
      Time dependence: Unsteady
      Fourier coefficients file path: flow.fcs
      Impose flux: t
      Profile: User_defined
      Spatial profile file path: profile.dat
   }
"""
    for model in f['domains']['rcr_outlets']:
        deck+=f"""   Add BC: {FLUID[model['tag']]} {{
      Type: Neu
      Time dependence: RCR
      RCR values: ({model['proximal_resistance']},{model['compliance']},{model['distal_resistance']})
      Distal pressure: {model['distal_pressure']}
      Initial pressure: 0
   }}
"""
    if rigid:
        deck+=helpers.roller(FLUID[4],'(1,1,1)')
        (target/'svFSI.inp').write_text(deck+'}\n')
        return meshes
    for constraint in f['domains']['solid_constraints']:
        if sorted(constraint['components'])!=[0,1,2]:
            raise ValueError('Expected componentwise clamping on the selected wall tags')
        deck+=helpers.roller(SOLID[constraint['tag']],'(1,1,1)',True)
    deck+="""
}
Add equation: mesh {
   Coupled: 1
   Min iterations: 2
   Max iterations: 40
   Tolerance: 1e-10
   Poisson ratio: 0.3
   LS type: CG {
      Tolerance: 1e-11
      Absolute tolerance: 1e-23
      Max iterations: 2000
   }
   Output: Spatial {
      Displacement: t
   }
"""
    for tag in (1,2,3):
        deck+=helpers.roller(FLUID[tag],'(1,1,1)')
    (target/'svFSI.inp').write_text(deck+'}\n')
    return meshes


def observations(mesh, state):
    nodes,cells,faces=mesh
    current={i:tuple(x+d for x,d in zip(p,state[i].displacement)) for i,p in nodes.items()}
    ref_volume=math.fsum(determinant(nodes,tet) for tet in cells)/6
    volume=math.fsum(determinant(current,tet) for tet in cells)/6
    flux=[0.,0.,0.]
    for tag,ids in faces:
        if tag not in (1,2,3):continue
        a,b,c=(current[i] for i in ids)
        normal=cross(sub(b,a),sub(c,a))
        axis=(0,1,1)[tag-1]
        area=math.sqrt(sum(v*v for v in normal))/2
        if abs(abs(normal[axis])-2*area)>1e-12 or max(abs(v) for i in ids for v in state[i].displacement)>1e-12:
            raise ValueError('Port moved or rotated from its reference position')
        sign=-1 if tag==3 else 1  # inward x at inlet, outward +/-y at outlets
        flux[tag-1]+=sign*area*sum(state[i].velocity[axis] for i in ids)/3
    return dict(flux=flux,volume_gain=volume-ref_volume)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('work','eon','svfsi','mpiexec','svfsi-libs','reference-scripts'):
        cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--refinement',type=int,default=1)
    cli.add_argument('--samples',type=int,default=32)
    cli.add_argument('--cycles',type=int,default=1)
    cli.add_argument('--amplitude',type=float,default=.0002)
    cli.add_argument('--period',type=float,default=.20)
    cli.add_argument('--unequal',action='store_true')
    cli.add_argument('--clamped',action='store_true',help='Clamp the inner and outer solid surfaces as a rigid-lumen control')
    cli.add_argument('--rigid-reference',action='store_true',help='Solve only the fixed lumen in native svFSI for the clamped-wall control')
    cli.add_argument('--sv-variant',choices=('native','grad-div-off'),default='native')
    args=cli.parse_args()
    os.environ.setdefault('OMPI_MCA_pml','ob1')
    os.environ.setdefault('OMPI_MCA_btl','self,sm,tcp')
    if args.samples<8 or args.samples%8 or args.cycles<1 or args.amplitude<=0 or args.period<=0:
        cli.error('Use positive amplitude and period, whole cycles and a multiple of eight samples per period')
    if args.rigid_reference and not args.clamped:
        cli.error('The native rigid-fluid control requires an EONSim clamped interface')
    sys.path.append(str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as wall
    from study_hydrostatic_fsi import PointState, recovered_state
    work=args.work.resolve()
    work.mkdir(parents=True,exist_ok=False)
    eon=work/'eon';sv=work/'sv'
    cfg=json.loads(generate(eon,args.refinement).read_text())
    f=cfg['fsi']; models=f['domains']['rcr_outlets']
    if args.unequal:models[0].update(proximal_resistance=12.,distal_resistance=32.,compliance=.00625)
    f['inlet']['ramp_time']=0.
    f['inlet']['flow_rate'].update(mean=0.,amplitude=args.amplitude,period=args.period)
    period=f['inlet']['flow_rate']['period']
    f.update(material='linear',dt=period/args.samples,steps=args.samples*args.cycles,output_interval=args.samples//8)
    del f['stabilization_tau']
    if args.clamped:
        f['domains']['solid_constraints'].extend(dict(tag=t,components=[0,1,2]) for t in (14,15))
    geometry=json.loads((eon/'geometry.json').read_text())
    run=Runner(args.eon,str(args.mpiexec.resolve()),eon,timeout=14400,interface_area=geometry['interface_area'])
    _,rows,_=run.solve('junction',cfg)
    for model in models:check_rcr_history(run,'junction',model,rows,sole_pressure=False)
    meshes=prepare(eon,sv,cfg,wall,args.rigid_reference)
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.svfsi_libs.resolve()),OMP_NUM_THREADS='1',
             OPENBLAS_NUM_THREADS='1',OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp')
    with (sv/'solve.log').open('w') as log:
        subprocess.run([args.svfsi.resolve(),'svFSI.inp'],cwd=sv,env=env,stdout=log,stderr=subprocess.STDOUT,
                       timeout=14400,check=True)
    data=sv/'1-procs'
    history=(data/'histor.dat').read_text()
    equations=('NS',) if args.rigid_reference else ('FS','MS')
    convergence={eq:check_convergence(history,len(rows),eq) for eq in equations}
    native=[list(map(float,l.split())) for l in (data/'RCR.dat').read_text().splitlines()]
    if len(native)!=len(rows) or any(len(r)!=7 or not all(map(math.isfinite,r)) for r in native):
        raise ValueError('Incomplete two-port native RCR history')
    max_flow=[0.,0.];max_pressure=[0.,0.];ode=[0.,0.];cap=[0.,0.];old_q=[0.,0.]
    peak_sv=[0.,0.];peak_eon=[0.,0.];samples=[];times=[]
    for i,(r,printed) in enumerate(zip(rows,native),1):
        t,pc2,pb2,pc3,pb3,q2,q3=printed
        if abs(t-r['time'])>1e-7*max(1.,abs(t)):raise ValueError('Time histories differ')
        times.append([r['time']])
        for k,(model,pb,pc,q) in enumerate(zip(models,(pb2,pb3),(pc2,pc3),(q2,q3))):
            tag=model['tag'];rp=model['proximal_resistance'];rd=model['distal_resistance'];tau=rd*model['compliance']
            weight=-math.expm1(-f['dt']/tau)
            cap[k]=(1-weight)*cap[k]+rd*(old_q[k]*weight+(q-old_q[k])*(1-tau*weight/f['dt']))
            old_q[k]=q
            # Three native values are rounded separately to seven significant digits.
            if abs(pb-pc-rp*q)>2e-6*max(1e-7,abs(pb),abs(pc),rp*abs(q)):
                raise ValueError('Native port pressure has the wrong flow sign or tag')
            ode[k]=max(ode[k],abs(cap[k]-pc))
            eq=r[f'endpoint_rcr_flow_{tag}'];ep=r[f'endpoint_rcr_pressure_{tag}']
            max_flow[k]=max(max_flow[k],abs(eq-q));max_pressure[k]=max(max_pressure[k],abs(ep-pb))
            peak_sv[k]=max(peak_sv[k],abs(q));peak_eon[k]=max(peak_eon[k],abs(eq))
            times[-1].extend([eq,q,ep,pb])
        if i%f['output_interval']==0:
            frame=data/f'result_{i:03d}.vtu'
            if args.rigid_reference:
                fluid=read_svfsi_state(frame,meshes[0][0],meshes[0][1])
                native_state=[{n:PointState((0.,0.,0.),v[:3],v[3]) for n,v in fluid.items()},None]
            else:
                native_state=wall.external_fields(frame,meshes)
            local_state=[recovered_state(eon,f'junction_step{i}'+('_solid' if k else ''),m,bool(k),1) for k,m in enumerate(meshes)]
            one,two=(observations(meshes[0],s[0]) for s in (local_state,native_state))
            prescribed=args.amplitude*math.sin(2*math.pi*t/period)
            for label,fld,circuit in [('EONSim',one,[r['endpoint_rcr_flow_2'],r['endpoint_rcr_flow_3']]),
                                      ('svFSI',two,[q2,q3])]:
                if abs(fld['flux'][0]-prescribed)>2e-8*args.amplitude or any(
                        abs(a-b)>2e-6*max(args.amplitude*1e-3,abs(b)) for a,b in zip(fld['flux'][1:],circuit)):
                    raise ValueError(f'{label} reconstructed cap flux differs at {i}: {fld["flux"]} {prescribed,circuit}')
            wall_rms=[math.sqrt(sum(sum(v*v for v in node.displacement) for node in s[1].values())/len(s[1]))
                      if s[1] is not None else None for s in (local_state,native_state)]
            if args.clamped and (max(v for v in wall_rms if v is not None)>1e-12 or max(abs(v['volume_gain']) for v in (one,two))>1e-12 or
                    any(abs(v['flux'][0]-sum(v['flux'][1:]))>1e-8*args.amplitude for v in (one,two))):
                raise ValueError('The clamped control moved or stored fluid volume')
            samples.append(dict(time=r['time'],eonsim=one,svfsi=two,wall_rms_displacement=wall_rms))
    if max(ode)>2e-6*max(max(peak_sv)*44.,1e-8):
        raise ValueError('Native RCR capacitor does not follow the measured flux')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    result=dict(refinement=args.refinement,steps=f['steps'],dt=f['dt'],period=period,amplitude=args.amplitude,models=models,
                eon_binary=digest(args.eon),sv_binary=digest(args.svfsi),sv_revision=wall.SVFSI_REVISION,
                sv_variant=args.sv_variant,native_equations=list(equations),wall_condition='clamped' if args.clamped else 'elastic',
                mesh_sha256=[digest(eon/p) for p in ('fluid.msh','solid.msh')],sv_deck=digest(sv/'svFSI.inp'),
                sv_convergence=convergence,peak_eon_outlet_flow=peak_eon,peak_sv_outlet_flow=peak_sv,
                max_outlet_flow_difference=max_flow,max_outlet_pressure_difference=max_pressure,
                native_capacitor_recurrence_error=ode,fields=samples)
    with (work/'paired.csv').open('w',newline='') as out:
        writer=csv.writer(out);writer.writerow(['time','eon_q2','sv_q2','eon_p2','sv_p2','eon_q3','sv_q3','eon_p3','sv_p3']);writer.writerows(times)
    (work/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(max_flow,max_pressure,convergence,flush=True)


if __name__=='__main__':main()
