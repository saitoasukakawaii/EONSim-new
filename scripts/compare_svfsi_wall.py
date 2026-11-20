"""Compare relaxed EONSim and svFSI ALE/linear-elastic quarter tubes on the same cells."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile

import study_hydrostatic_fsi as fsi
import study_lame_wall as wall
import study_rigid_tube as tube
from svfsi_history import check_convergence
from svfsi_mesh import export_mesh


SVFSI_REVISION='94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571'
FLUID_FACES={1:'fluid_in',2:'fluid_out',3:'interface_fluid',5:'fluid_y',6:'fluid_z'}
SOLID_FACES={11:'wall_in',12:'wall_out',13:'interface_solid',14:'outer',15:'wall_y',16:'wall_z'}


def mesh_block(name,tags,domain):
    faces=''.join(f'   Add face: {face} {{\n      Face file path: {face}.vtp\n   }}\n' for face in tags.values())
    return f'Add mesh: {name} {{\n   Mesh file path: {name}.vtu\n'+faces+f'   Domain: {domain}\n}}\n'


def roller(name,direction,integral=False):
    extra='      Impose on state variable integral: t\n' if integral else ''
    return (f'   Add BC: {name} {{\n      Type: Dir\n      Value: 0\n      Zero out perimeter: f\n'
            f'      Effective direction: {direction}\n'+extra+'   }\n')


def prepare(case,directory,krylov_dimension=150):
    if krylov_dimension<1:
        raise ValueError('GMRES Krylov space dimension must be positive')
    cfg=json.loads((case/'case.json').read_text())
    f=cfg['fsi']
    rho=cfg['time'].get('rho_infinity')
    if rho is None or cfg!=fsi.case_config(f['dt'],f['dt']*f['steps'],f['pressure'],rho):
        raise ValueError('The matched case requires constant end pressure and generalized-alpha')
    dt=f['dt']; p=f['pressure']; n=f['steps']
    directory.mkdir(parents=True)
    for domain,faces,path in [('lumen',FLUID_FACES,'fluid.msh'),('wall',SOLID_FACES,'solid.msh')]:
        export_mesh(case/path,directory,domain,faces)
    data=f"""Continue previous simulation: 0
Number of spatial dimensions: 3
Number of time steps: {n}
Time step size: {dt:.17g}
Spectral radius of infinite time step: {rho:.17g}
Save results to VTK format: 1
Name prefix of saved VTK files: result
Increment in saving VTK files: 1
Start saving after time step: 1
Increment in saving restart files: {n}
Verbose: 1
Warning: 1

"""+mesh_block('lumen',FLUID_FACES,0)+mesh_block('wall',SOLID_FACES,1)+"""
Add projection: interface_solid {
   Project from face: interface_fluid
}
Add equation: FSI {
   Coupled: 1
   Min iterations: 2
   Max iterations: 12
   Tolerance: 1e-8
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
   LS type: GMRES {
      Tolerance: 1e-10
      Absolute tolerance: 1e-15
      Max iterations: 10
      Krylov space dimension: """+str(krylov_dimension)+"""
   }
   Output: Spatial {
      Displacement: t
      Velocity: t
      Pressure: t
   }
   Output: Alias {
      Displacement: FS_Displacement
   }
"""
    for name in ['fluid_in','fluid_out']:
        data+=f'   Add BC: {name} {{\n      Type: Neu\n      Value: {p:.17g}\n   }}\n'
    for name,axis in [('fluid_y','(0,1,0)'),('fluid_z','(0,0,1)'),('wall_in','(1,0,0)'),('wall_out','(1,0,0)'),('wall_y','(0,1,0)'),('wall_z','(0,0,1)')]:
        data+=roller(name,axis,name.startswith('wall'))
    data+="""}
Add equation: mesh {
   Coupled: 1
   Min iterations: 2
   Max iterations: 12
   Tolerance: 1e-8
   Poisson ratio: 0.3
   LS type: CG {
      Tolerance: 1e-10
      Absolute tolerance: 1e-15
      Max iterations: 2000
   }
   Output: Spatial {
      Displacement: t
   }
"""
    for name,axis in [('fluid_in','(1,0,0)'),('fluid_out','(1,0,0)'),('fluid_y','(0,1,0)'),('fluid_z','(0,0,1)')]:
        data+=roller(name,axis)
    (directory/'svFSI.inp').write_text(data+'}\n')


def external_fields(path, meshes):
    from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridReader
    reader=vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(path))
    reader.Update()
    grid=reader.GetOutput()
    if reader.GetErrorCode() or grid.GetNumberOfCells()!=sum(len(m[1]) for m in meshes):
        raise ValueError('Incomplete external fluid/solid result')
    mesh_id=grid.GetCellData().GetArray('Mesh_ID')
    if mesh_id is None: raise ValueError('Missing mesh region IDs')
    lookup=[{struct.pack('<3f',*pos):n for n,pos in mesh[0].items()} for mesh in meshes]
    if any(len(ids)!=len(m[0]) for ids,m in zip(lookup,meshes)):
        raise ValueError('Ambiguous source coordinates at external output precision')
    mapped=[{},{}]
    cells=[Counter(),Counter()]
    for i in range(grid.GetNumberOfCells()):
        region=mesh_id.GetTuple1(i)
        if region not in (1.,2.) or grid.GetCellType(i)!=10:
            raise ValueError('Unexpected element or mesh ID')
        k=int(region)-1
        tet=grid.GetCell(i)
        ids=[]
        for j in range(4):
            local=tet.GetPointId(j)
            if local not in mapped[k]:
                key=struct.pack('<3f',*grid.GetPoint(local))
                if key not in lookup[k]: raise ValueError('External geometry differs from source region')
                mapped[k][local]=lookup[k][key]
            ids.append(mapped[k][local])
        cells[k][tuple(sorted(ids))]+=1
    data=grid.GetPointData()
    arrays={}
    for name,width in [('Velocity',3),('Pressure',1),('Displacement',3),('FS_Displacement',3)]:
        arr=data.GetArray(name)
        if arr is None or arr.GetNumberOfComponents()!=width or arr.GetNumberOfTuples()!=grid.GetNumberOfPoints():
            raise ValueError('Missing or incomplete external '+name)
        arrays[name]=arr
    result=[]
    for k,mesh in enumerate(meshes):
        if (cells[k]!=Counter(tuple(sorted(t)) for t in mesh[1])
                or set(mapped[k].values())!=mesh[0].keys() or len(mapped[k])!=len(mesh[0])):
            raise ValueError('External region elements or nodes differ from the source mesh')
        # These VTUs use reference coordinates. FSI displacement is the
        # mechanical field. The separate mesh equation supplies fluid ALE motion.
        d=arrays['FS_Displacement' if k else 'Displacement']
        state={n:fsi.PointState(d.GetTuple3(i),arrays['Velocity'].GetTuple3(i),
                          0. if k else arrays['Pressure'].GetTuple1(i)) for i,n in mapped[k].items()}
        if not all(math.isfinite(x) for v in state.values() for x in (*v.displacement,*v.velocity,v.pressure)):
            raise ValueError('Nonfinite external field')
        result.append(state)
    return result


def compare(case,directory):
    eon=fsi.analyze(case)
    sizes=re.findall(r'^\s*Krylov space dimension: (\d+)\s*$',(directory/'svFSI.inp').read_text(),re.M)
    if len(sizes)!=1: raise ValueError('Expected one FSI GMRES space dimension')
    krylov=int(sizes[0])
    with tempfile.TemporaryDirectory() as tmp:
        valid=Path(tmp)/'matched'
        prepare(case,valid,krylov)
        for path in valid.iterdir():
            if path.read_bytes()!=(directory/path.name).read_bytes():
                raise ValueError('External inputs differ from the EONSim case: '+path.name)
    digest=(directory/'executable.sha256').read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}',digest): raise ValueError('Missing external binary digest')
    outputs=directory/'1-procs'
    log=(outputs/'histor.dat').read_text()
    n=eon['steps']
    convergence={eq:check_convergence(log,n,eq) for eq in ('FS','MS')}
    meshes=[tube.read_mesh(case/name) for name in ('fluid.msh','solid.msh')]
    previous=external_fields(outputs/f'result_{n-1:03d}.vtu',meshes)[1]
    fluid,solid=external_fields(outputs/f'result_{n:03d}.vtu',meshes)
    sc=meshes[1][0]
    def interface(mesh,tag):
        return {mesh[0][n]:n for t,f in mesh[2] if t==tag for n in f}
    fi,si=(interface(m,t) for m,t in zip(meshes,(3,13)))
    disps=[{n:v.displacement for n,v in field.items()} for field in (previous,solid)]
    areas=[]
    for section in eon['sections']:
        x=section['x']
        ring=[n for p,n in si.items() if p[0]==x]
        old,end=(wall.bore_section(sc,d,ring) for d in disps)
        areas.append(dict(x=x,previous=old['linear_area_strain'],area_strain=end['linear_area_strain'],
                          eonsim_area_strain=section['linear_area_strain']))
    exact=eon['exact_linear_area_strain']
    p=eon['pressure']
    volume=error2=0.
    jac=math.inf
    for field,mesh in zip((fluid,solid),meshes):
        nodes,tets,_=mesh
        xyz={n:tuple(a+b for a,b in zip(pos,field[n].displacement)) for n,pos in nodes.items()}
        for tet in tets:
            v=tube.determinant(xyz,tet)/6
            if v<=0: raise ValueError('Inverted external endpoint tetrahedron')
            jac=min(jac,v/(tube.determinant(nodes,tet)/6))
            if field is fluid:
                errors=[fluid[n].pressure-p for n in tet]
                error2+=v*(sum(errors)**2+sum(x*x for x in errors))/20
                volume+=v
    metrics=dict(worst_area_relative_error=max(abs(a['area_strain']/exact-1) for a in areas),
                 last_step_area_change_relative=max(abs(a['area_strain']-a['previous']) for a in areas)/exact,
                 final_max_fluid_speed=max(math.hypot(*v.velocity) for v in fluid.values()),
                 pressure_rms_relative=math.sqrt(error2/volume)/p,
                 interface_velocity_difference=max(abs(a-b) for x in fi for a,b in zip(fluid[fi[x]].velocity,solid[si[x]].velocity)),
                 interface_displacement_difference=max(abs(a-b) for x in fi for a,b in zip(fluid[fi[x]].displacement,solid[si[x]].displacement)))
    difference=max(abs(a['area_strain']-a['eonsim_area_strain']) for a in areas)/exact
    return dict(svfsi_target_revision=SVFSI_REVISION,svfsi_executable_sha256=digest,
                steps=n,dt=eon['dt'],gmres_krylov_dimension=krylov,
                sections=areas,eonsim_passed=eon['passed'],svfsi=metrics,
                svfsi_max_final_normalized_residual={eq:v[0] for eq,v in convergence.items()},
                svfsi_zero_corrections={eq:v[1] for eq,v in convergence.items()},
                svfsi_min_endpoint_jacobian_ratio=jac,worst_cross_code_area_difference=difference,
                passed=eon['passed'] and difference<.02 and all(v<fsi.LIMITS[k] for k,v in metrics.items()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--executable',type=Path)
    mode.add_argument('--analyze-only',action='store_true')
    p.add_argument('--check',action='store_true')
    p.add_argument('--krylov-dimension',type=int,default=150,help='External FSI GMRES subspace size for a new solve')
    a=p.parse_args()
    if a.check and not (a.executable or a.analyze_only):
        p.error('--check requires a solver or an existing result')
    if not a.analyze_only:
        prepare(a.case,a.work,a.krylov_dimension)
    if a.executable:
        binary=a.executable.resolve()
        (a.work/'executable.sha256').write_text(hashlib.sha256(binary.read_bytes()).hexdigest()+'\n')
        with (a.work/'solve.log').open('w') as log:
            subprocess.run([binary,'svFSI.inp'],cwd=a.work,stdout=log,stderr=subprocess.STDOUT,check=True)
    if a.executable or a.analyze_only:
        result=compare(a.case,a.work)
        print(json.dumps(result,indent=2,allow_nan=False))
        if a.check and not result['passed']: raise SystemExit('Missed a matched coupled criterion')
    else:
        print('Wrote matched svFSI inputs in',a.work)


if __name__=='__main__':
    main()
