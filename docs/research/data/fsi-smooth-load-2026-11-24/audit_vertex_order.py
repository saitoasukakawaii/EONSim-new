"""Audit a Tet4 relabelling against the same completed tube with its original local vertex order."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_reflection import checked_strains, ring_geometry
from audit_rigid_tube_fields import p1_square
from study_rigid_tube import determinant, read_mesh
from svfsi_history import check_convergence


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boundary_surface(path):
    """Tri3 cyclic rotations and facet listing order preserve oriented pressure traction."""
    from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
    reader=vtkXMLPolyDataReader()
    reader.SetFileName(str(path));reader.Update()
    face=reader.GetOutput()
    ids=face.GetPointData().GetArray('GlobalNodeID')
    parent=face.GetCellData().GetArray('GlobalElementID')
    if (reader.GetErrorCode() or ids is None or parent is None or ids.GetNumberOfTuples()!=face.GetNumberOfPoints()
            or parent.GetNumberOfTuples()!=face.GetNumberOfCells()):
        raise ValueError('Incomplete native facet and parent identifiers')
    nodes={}
    for i in range(face.GetNumberOfPoints()):
        key=int(ids.GetTuple1(i));xyz=face.GetPoint(i)
        if key in nodes or not all(map(math.isfinite,xyz)):raise ValueError('Invalid surface node')
        nodes[key]=xyz
    facets=Counter()
    for i in range(face.GetNumberOfCells()):
        tri=face.GetCell(i)
        if tri.GetCellType()!=5 or tri.GetNumberOfPoints()!=3:raise ValueError('Expected Tri3 boundary')
        v=tuple(int(ids.GetTuple1(tri.GetPointId(j))) for j in range(3))
        oriented=min(v,v[1:]+v[:1],v[2:]+v[:2])
        facets[int(parent.GetTuple1(i)),oriented]+=1
    return nodes,facets


def source_meshes(base,case,vertex):
    if (base/'reference/solid.msh').read_bytes()!=(case/'reference/solid.msh').read_bytes():
        raise ValueError('Solid changed in fluid-vertex experiment')
    old=read_mesh(base/'reference/fluid.msh')
    new=read_mesh(case/'reference/fluid.msh')
    points,cells,faces=old
    if points!=new[0] or faces!=new[2] or len(cells)!=len(new[1]):
        raise ValueError('Fluid coordinates, tagged facets or number of elements changed')
    for a,b in zip(cells,new[1]):
        if (set(a)!=set(b) or len(set(b))!=4 or a[vertex]!=b[-1] or determinant(points,a)<=0 or
                not math.isclose(determinant(points,a),determinant(points,b),rel_tol=2e-12)):
            raise ValueError('Cell order, dependent vertex, orientation or signed volume changed')
    for name in ('eon/case.json','matched/svFSI.inp','matched/wall.vtu',
                 'eon/executable.sha256','matched/executable.sha256'):
        if digest(base/name)!=digest(case/name):raise ValueError('Input or solver changed: '+name)
    for source in (base/'matched').iterdir():
        target=case/'matched'/source.name
        if source.suffix=='.dat' and digest(source)!=digest(target):
            raise ValueError('Native pressure waveform changed: '+source.name)
        if source.suffix=='.vtp' and boundary_surface(source)!=boundary_surface(target):
            raise ValueError('Oriented native surface geometry or parent element changed: '+source.name)
    return [old,read_mesh(base/'reference/solid.msh')],[new,read_mesh(case/'reference/solid.msh')]


def read_states(folder,meshes,step,wall,fsi):
    eon=[fsi.recovered_state(folder/'eon',f'tube_step{step}'+('_solid' if k else ''),mesh,bool(k),1)
         for k,mesh in enumerate(meshes)]
    sv=wall.external_fields(folder/f'matched/1-procs/result_{step:03d}.vtu',meshes)
    return {'eonsim':eon,'svfsi':sv}


def state_change(first,second,meshes):
    result={};rms={};locations={}
    for k,(one,two) in enumerate(zip(first,second)):
        if one.keys()!=two.keys():raise ValueError('The field does not cover the common physical nodes')
        points,cells,_=meshes[k]
        volumes=[determinant(points,cell)/6 for cell in cells]
        volume=math.fsum(volumes)
        for name in ('displacement','velocity','pressure') if not k else ('displacement','velocity'):
            label=('wall_' if k else 'fluid_')+name
            delta={}
            for node in one:
                a,b=getattr(one[node],name),getattr(two[node],name)
                delta[node]=(a-b,) if name=='pressure' else tuple(v-w for v,w in zip(a,b))
            peak=max(delta,key=lambda node:max(map(abs,delta[node])))
            result[label]=max(map(abs,delta[peak]))
            locations[label]=list(points[peak])
            energy=math.fsum(p1_square([delta[node][i] for node in cell],v)
                             for cell,v in zip(cells,volumes) for i in range(len(delta[peak])))
            rms[label]=math.sqrt(energy/volume)
    return dict(max_nodal_change=result,volume_rms_change=rms,peak_reference_position=locations)


def audit(base,case,vertex,wall,fsi):
    old=json.loads((base/'results.json').read_text());new=json.loads((case/'results.json').read_text())
    for key in ('steps','mesh','axial_sections','peak_pressure','equilibrium_area_strain','source_executables'):
        if old[key]!=new[key]:raise ValueError('Run differs in '+key)
    n=old['steps']
    if old.get('fluid_last_vertex',3)!=3 or new.get('fluid_last_vertex',3)!=vertex or vertex==3:
        raise ValueError('Incorrect dependent vertex in run receipt')
    meshes=source_meshes(base,case,vertex)
    for folder,m,record in zip((base,case),meshes,(old,new)):
        for k,label in enumerate(('fluid','solid')):
            if record['mesh_sha256'][k]!=digest(folder/f'reference/{label}.msh'):
                raise ValueError('Run receipt does not match mesh')
        if set(record['run_hash_receipts'].values())!={True} or record['matched_pressure_max_abs']>3e-15:
            raise ValueError('Incomplete source or applied-load receipt')
        for equation in ('FS','MS'):
            check_convergence((folder/'matched/1-procs/histor.dat').read_text(),n,equation)
    geometries=[ring_geometry(m[1],r["mesh"]) for m,r in zip(meshes,(old,new))]
    output=[]
    for i,step in enumerate((n//2,n)):
        states=[read_states(folder,m,step,wall,fsi) for folder,m in zip((base,case),meshes)]
        measurement=dict(time=step/n)
        for name,key in (('eonsim','eon'),('svfsi','svfsi')):
            delta=state_change(states[0][name],states[1][name],meshes[0])
            (one,base_cache),(two,new_cache)=[
                checked_strains(report,i,step/n,key,geom,state[name][1])
                for report,geom,state in zip((old,new),geometries,states)]
            difference=(100*(two-one)/old['equilibrium_area_strain']).tolist()
            measurement[name]=dict(**delta,max_cached_strain_delta=max(base_cache,new_cache),x0_pct_initial_area=100*two[0],
                base_x0_pct_initial_area=100*one[0],max_section_change_pct_static=max(map(abs,difference)),
                signed_section_change_pct_static=difference)
        output.append(measurement)
    return dict(case=case.name,base_case=base.name,steps=n,vertex=vertex,axial_sections=old['axial_sections'],
                old_mesh_sha256=old['mesh_sha256'],new_mesh_sha256=new['mesh_sha256'],
                executables=old['source_executables'],samples=output)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--runs',type=Path,required=True,help='Root containing current-time and vertex-order runs')
    cli.add_argument('--group',choices=('vertex-order','regular-metric'),default='vertex-order')
    cli.add_argument('--reference-scripts',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    sys.path.append(str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as wall
    import study_hydrostatic_fsi as fsi
    rows=[]
    for p in sorted((args.runs/args.group).glob('*/results.json')):
        n,vertex,mode=p.parent.name.split('-')
        if vertex=='v3':continue
        base=(args.runs/'current-time'/f'{n}-{mode}' if args.group=='vertex-order' else
              args.runs/args.group/f'{n}-v3-{mode}')
        rows.append(audit(base,p.parent,int(vertex[1:]),wall,fsi))
    if not rows:raise ValueError('No completed reordered runs')
    args.output.write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
    for r in rows:
        print(r['case'],r['samples'][-1]['eonsim']['max_section_change_pct_static'],
              r['samples'][-1]['svfsi']['max_section_change_pct_static'])


if __name__=='__main__':main()
