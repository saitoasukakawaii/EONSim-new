"""Replay a fixed, clamped circular outlet against the pinned native svFSI RCR implementation."""
import argparse
import cmath
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'cases/fsi'),str(ROOT/'tests')]
from compare_svfsi_womersley import FACE_NAMES, SVFSI_REVISION, input_text
from generate_tube import generate
from study_rigid_tube import read_mesh
from svfsi_history import check_convergence
from svfsi_mesh import export_mesh
from verify_fsi_inlet import Runner


def circuit_exact(t):
    angle=2*math.pi*t
    z=3+8/(1+2j*math.pi*.2)
    return .03+.01*(z.real*math.sin(angle)+z.imag*math.cos(angle))


def metrics(time, flow, pressure):
    delta=max(abs(pb-circuit_exact(t)) for t,pb in zip(time,pressure))
    def coefficient(values):
        return sum(v*cmath.exp(-2j*math.pi*t) for t,v in zip(time,values))
    impedance=coefficient(pressure)/coefficient(flow)
    ratio=impedance/(3+8/(1+2j*math.pi*.2))
    return dict(max_pressure_error_pa=delta,complex_impedance=[impedance.real,impedance.imag],
                magnitude_error_fraction=abs(ratio)-1,phase_error_degrees=math.degrees(cmath.phase(ratio)))


def prepare_sv(source,dest,n):
    export_mesh(source/'fluid.msh',dest,'fluid',FACE_NAMES)
    coords,_,faces=read_mesh(source/'fluid.msh')
    inlet=sorted({i for tag,face in faces if tag==1 for i in face})
    (dest/'profile.dat').write_text(''.join(f'{i} {max(0.,1-coords[i][1]**2-coords[i][2]**2):.17g}\n' for i in inlet))
    # The signed Fourier coefficient gives inward flow at x=0. Verify the integrated flux in the output.
    (dest/'flow.fcs').write_text('0\n1\n0\n0\n2\n0 0\n0 0.01\n')
    base=input_text(dict(fluid=dict(dt=1/n,steps=n,density=1.,viscosity=1.)))
    before,_,_=base.partition('   Add BC: inlet {')
    before=before.replace('Spectral radius of infinite time step: 0','Spectral radius of infinite time step: 0.5')
    before=before.replace(f'Increment in saving VTK files: {n}', 'Increment in saving VTK files: 1')
    before=before.replace('Absolute tolerance: 1e-15','Absolute tolerance: 1e-23')
    before=before.replace('   Tolerance: 1e-8','   Tolerance: 1e-10')
    deck=before+'''   Add BC: inlet {
      Type: Dir
      Time dependence: Unsteady
      Fourier coefficients file path: flow.fcs
      Impose flux: t
      Profile: User_defined
      Spatial profile file path: profile.dat
   }
   Add BC: outlet {
      Type: Neu
      Time dependence: RCR
      RCR values: (3, 0.025, 8)
      Distal pressure: 0.03
      Initial pressure: '''+format(circuit_exact(0.),'.17g')+'''
   }
   Add BC: wall {
      Type: Dir
      Value: 0
   }
}
'''
    (dest/'svFSI.inp').write_text(deck)


def surface_fluxes(mesh, files):
    import numpy as np
    from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridReader
    from vtkmodules.util.numpy_support import vtk_to_numpy
    coords,_,faces=read_mesh(mesh)
    reader=vtkXMLUnstructuredGridReader()
    weights=None
    for i,path in enumerate(files):
        reader.SetFileName(str(path))
        reader.Update()
        grid=reader.GetOutput()
        points=vtk_to_numpy(grid.GetPoints().GetData())
        if i==0:
            # The native VTK writer stores coordinates at lower precision than its velocity field.
            id_by_coord={tuple(np.asarray(x,dtype=points.dtype)):n for n,x in coords.items()}
            if len(id_by_coord)!=len(coords):raise ValueError("VTU coordinates cannot distinguish reference nodes")
            position={id_by_coord[tuple(x)]:n for n,x in enumerate(points)}
            if len(position)!=len(coords):raise ValueError("Exported svFSI coordinates differ")
            weights=np.zeros((2,len(points)))
            wall=sorted({position[n] for t,f in faces if t==3 for n in f})
            for tag,tri in faces:
                if tag not in (1,2):continue
                a,b,c=(np.asarray(coords[n]) for n in tri)
                area=np.linalg.norm(np.cross(b-a,c-a))/2
                for node in tri:weights[tag-1,position[node]]+=area/3
            previous=points.copy()
        elif not np.array_equal(previous,points):raise ValueError("A rigid tube mesh moved")
        v=vtk_to_numpy(grid.GetPointData().GetArray('Velocity'))
        if np.max(np.abs(v[wall]))>1e-12:raise ValueError("Wall velocity violates no slip")
        yield weights@v[:,0]


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for k in ('work','eon','svfsi','mpiexec','svfsi-libs'):
        cli.add_argument('--'+k,type=Path,required=True)
    cli.add_argument('--steps',type=int,nargs='+',default=[32,64,128,256])
    args=cli.parse_args()
    if min(args.steps)<8:cli.error('At least eight samples per cycle required')
    home=args.work.resolve()
    source=home/'eon'
    cfg=json.loads(generate(source,sectors=8,axial=1,radial=2,clamped_slab=True).read_text())
    model=dict(tag=2,proximal_resistance=3.,distal_resistance=8.,compliance=.025,
               distal_pressure=.03,initial_capacitor_pressure=circuit_exact(0))
    cfg['fsi']['domains']['rcr_outlets']=[model]
    cfg['fsi']['inlet']['ramp_time']=0.
    cfg['fsi']['inlet']['flow_rate'].update(mean=0.,amplitude=.01,period=1.)
    cfg['fsi'].update(pressure_face_history=True,output_interval=10000,stabilization_tau=.01)
    geo=json.loads((source/'geometry.json').read_text())
    run=Runner(args.eon,str(args.mpiexec.resolve()),source,interface_area=geo['interface_area'])
    digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    report=dict(svfsi_source=SVFSI_REVISION,mesh_sha256=digest(source/'fluid.msh'),
                eon_sha256=digest(args.eon),svfsi_sha256=digest(args.svfsi),runs=[])
    paired=[]
    for n in args.steps:
        cfg['fsi'].update(steps=n,dt=1/n)
        _,rows,_=run.solve(f'rcr-{n}',cfg)
        sv=home/f'svfsi-{n}'
        sv.mkdir(exist_ok=False)
        prepare_sv(source,sv,n)
        env=dict(os.environ,LD_LIBRARY_PATH=str(args.svfsi_libs.resolve()),OMP_NUM_THREADS='1',
                 OPENBLAS_NUM_THREADS='1',OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp')
        with (sv/'solve.log').open('w') as log:
            subprocess.run([args.svfsi.resolve(),'svFSI.inp'],cwd=sv,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        data=sv/'1-procs'
        norms=check_convergence((data/'histor.dat').read_text(),n)
        fields=[list(map(float,line.split())) for line in (data/'RCR.dat').read_text().splitlines()]
        external=[line.split() for line in (data/'B_NS_Velocity_flux.txt').read_text().splitlines()[3:]]
        if len(rows)!=n or len(fields)!=n or len(external)!=n:raise ValueError('Missing accepted circuit observations')
        files=sorted(data.glob('result_*.vtu'),key=lambda p:int(p.stem.rsplit('_',1)[1]))
        if [int(p.stem.rsplit('_',1)[1]) for p in files]!=list(range(1,n+1)):
            raise ValueError("Missing double-precision volume output")
        vtk_flux=surface_fluxes(source/'fluid.msh',files)
        sv_flow=[];sv_pressure=[];times=[]
        old_q=0.;pc_reference=circuit_exact(0.)
        # Exact capacitor solution for a linear interpolation of the measured endpoint flows.
        h=1/n
        weight=-math.expm1(-h/.2)
        ode_error=face_error=circuit_error=flow_error=boundary_text_error=0.
        for j,((published_time,pc,pb,q),printed,face,row) in enumerate(zip(fields,external,vtk_flux,rows),1):
            t=j*h
            if abs(published_time-t)>6e-7 or abs(row['time']-t)>1e-12:raise ValueError('Observation time mismatch')
            pc_reference=.03+(pc_reference-.03)*(1-weight)+8*(old_q*weight+(q-old_q)*(1-.2*weight/h))
            old_q=q
            ode_error=max(ode_error,abs(pc-pc_reference))
            face_error=max(face_error,abs(face[1]-face[0]),abs(face[1]-row['endpoint_rcr_flow']))
            for token,value in zip(printed,(-face[0],face[1],0.)):
                delta=abs(float(token)-value)
                unit=10.**Decimal(token).as_tuple().exponent
                # Upstream STR truncates fixed-width boundary tables and retains fewer digits for negative values.
                if delta>unit+2e-12:raise ValueError("Printed boundary flux disagrees with the VTU field")
                boundary_text_error=max(boundary_text_error,delta)
            circuit_error=max(circuit_error,abs(pb-pc-3*q))
            flow_error=max(flow_error,abs(q-.01*math.sin(2*math.pi*t)),abs(q-row['endpoint_rcr_flow']))
            times.append(t);sv_flow.append(q);sv_pressure.append(pb)
            paired.append([n,j,t,row['endpoint_rcr_flow'],q,row['endpoint_rcr_pressure'],pb,row['endpoint_capacitor_pressure'],pc,circuit_exact(t)])
        # The independent text tables use different printed precisions (6 or 7 significant digits).
        if max(ode_error,circuit_error)>8e-8 or face_error>2e-10 or flow_error>8e-9:
            raise ValueError(f'Circuit/face consistency failed: {ode_error}, {circuit_error}, {face_error}, {flow_error}')
        row=dict(steps=n,convergence=norms,max_flux_difference=flow_error,max_vtu_face_flux_error=face_error,max_boundary_text_difference=boundary_text_error,
                 sv_capacitor_vs_exact_linear_flux_pa=ode_error,sv_algebraic_pressure_error_pa=circuit_error,
                 max_intercode_pressure_difference_pa=max(abs(r['endpoint_rcr_pressure']-p) for r,p in zip(rows,sv_pressure)),
                 eonsim=metrics(times,[r['endpoint_rcr_flow'] for r in rows],[r['endpoint_rcr_pressure'] for r in rows]),
                 svfsi=metrics(times,sv_flow,sv_pressure),deck_sha256=digest(sv/'svFSI.inp'))
        report['runs'].append(row)
        with (home/'paired.csv').open('w',newline='') as f:
            writer=csv.writer(f)
            writer.writerow(['steps','accepted_step','time_s','eon_q','sv_q','eon_pb','sv_pb','eon_pc','sv_pc','exact_pb'])
            writer.writerows(paired)
        (home/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(n,row['max_intercode_pressure_difference_pa'],ode_error,flush=True)


if __name__=='__main__':
    main()
