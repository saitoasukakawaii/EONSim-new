"""Export the conforming linear elastic pressure-tube case to pinned svFSI.

Input syntax follows SimVascular/svFSI 7bdb74c and its READFILES.f/FFT.f.
Mesh topology, surface parent IDs and outward orientation are checked here.
This adapter does not equate the two codes' time or stabilization operators.
"""
import argparse
import array as binary_array
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

import study_rigid_tube as tube


def array(parent,name,values,width=1,kind='Float64'):
    attributes=dict(type=kind,format='ascii',NumberOfComponents=str(width))
    if name:
        attributes['Name']=name
    node=ET.SubElement(parent,'DataArray',attributes)
    words=[format(v,'.17g') if isinstance(v,float) else str(v) for v in values]
    stride=max(width,12//width*width)
    node.text='\n'+'\n'.join(' '.join(words[i:i+stride]) for i in range(0,len(words),stride))+'\n'


def save_vtk(root,path):
    """Zlib-compressed appended raw XML, readable by VTK and pinned svFSI.

    Its legacy ASCII parser assumes one component per connectivity entry;
    compressed block headers let it recover the true nodes-per-cell instead.
    This is also the encoding used by that version's native writer.
    """
    blocks=[];offset=0
    kinds=dict(Float64=('d',float,8),Int32=('i',int,4),UInt8=('B',int,1))
    for node in root.iter('DataArray'):
        code,cast,width=kinds[node.attrib['type']]
        values=binary_array.array(code,map(cast,node.text.split()))
        if values.itemsize!=width:
            raise ValueError('Unexpected native array width')
        if sys.byteorder!='little':
            values.byteswap()
        data=values.tobytes()
        size=32768
        chunks=[zlib.compress(data[i:i+size]) for i in range(0,len(data),size)]
        header=[len(chunks),size,len(data)-(len(chunks)-1)*size,*map(len,chunks)]
        block=struct.pack('<'+str(len(header))+'I',*header)+b''.join(chunks)
        node.attrib.update(format='appended',offset=str(offset))
        if node.attrib.get('Name')=='connectivity':
            node.attrib.pop('NumberOfComponents',None)
        node.text=None;blocks.append(block);offset+=len(block)
    root.set('header_type','UInt32')
    root.set('compressor','vtkZLibDataCompressor')
    marker='__EONSIM_APPENDED_RAW__'
    ET.SubElement(root,'AppendedData',encoding='raw').text=marker
    ET.indent(root,space='  ')
    xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    path.write_bytes(xml.replace(marker.encode(),b'_'+b''.join(blocks)))


def write_mesh(source,target):
    nodes,cells,faces=tube.read_mesh(source)
    ids=sorted(nodes);index={n:i for i,n in enumerate(ids)}
    if min(tube.determinant(nodes,c) for c in cells)<=0:
        raise ValueError('Nonpositive tetrahedron')
    parents=defaultdict(list)
    for i,c in enumerate(cells,1):
        for j in range(4):
            parents[tuple(sorted(c[:j]+c[j+1:]))].append(i)
    if {tuple(sorted(f)) for _,f in faces}!={f for f,p in parents.items() if len(p)==1}:
        raise ValueError('Incomplete exterior surface')
    root=ET.Element('VTKFile',type='UnstructuredGrid',version='0.1',byte_order='LittleEndian')
    piece=ET.SubElement(ET.SubElement(root,'UnstructuredGrid'),'Piece',NumberOfPoints=str(len(ids)),NumberOfCells=str(len(cells)))
    array(ET.SubElement(piece,'PointData'),'GlobalNodeID',range(1,len(ids)+1),kind='Int32')
    array(ET.SubElement(piece,'CellData'),'GlobalElementID',range(1,len(cells)+1),kind='Int32')
    array(ET.SubElement(piece,'Points'),'Points',[v for n in ids for v in nodes[n]],3)
    connectivity=ET.SubElement(piece,'Cells')
    array(connectivity,'connectivity',[index[n] for c in cells for n in c],kind='Int32')
    array(connectivity,'offsets',range(4,4*len(cells)+1,4),kind='Int32')
    array(connectivity,'types',[10]*len(cells),kind='UInt8')
    target.mkdir(parents=True,exist_ok=True)
    save_vtk(root,target/'volume.vtu')
    tags=sorted({t for t,_ in faces})
    for tag in tags:
        selected=[f for t,f in faces if t==tag]
        used=sorted({n for f in selected for n in f});local={n:i for i,n in enumerate(used)}
        surface=[];parent_ids=[]
        for face in selected:
            parent=parents[tuple(sorted(face))]
            if len(parent)!=1:
                raise ValueError('Surface does not name one parent cell')
            parent=parent[0]
            a,b,c=[nodes[n] for n in face]
            av=tube.cross(tube.sub(b,a),tube.sub(c,a))
            center=tuple(sum(nodes[n][j] for n in cells[parent-1])/4 for j in range(3))
            if sum(x*y for x,y in zip(av,tube.sub(a,center)))<0:
                face=(face[0],face[2],face[1])
            surface.append(face);parent_ids.append(parent)
        root=ET.Element('VTKFile',type='PolyData',version='0.1',byte_order='LittleEndian')
        piece=ET.SubElement(ET.SubElement(root,'PolyData'),'Piece',NumberOfPoints=str(len(used)),
                            NumberOfVerts='0',NumberOfLines='0',NumberOfStrips='0',NumberOfPolys=str(len(surface)))
        array(ET.SubElement(piece,'PointData'),'GlobalNodeID',[index[n]+1 for n in used],kind='Int32')
        array(ET.SubElement(piece,'CellData'),'GlobalElementID',parent_ids,kind='Int32')
        array(ET.SubElement(piece,'Points'),'Points',[v for n in used for v in nodes[n]],3)
        polygons=ET.SubElement(piece,'Polys')
        array(polygons,'connectivity',[local[n] for f in surface for n in f],kind='Int32')
        array(polygons,'offsets',range(3,3*len(surface)+1,3),kind='Int32')
        save_vtk(root,target/f'face-{tag}.vtp')
    return dict(nodes=len(nodes),tetrahedra=len(cells),tags=tags)


def write_general_pressure(source,output,f,steps,offset):
    """Knot the prescribed law at every actual fixed-step boundary read.

    svFSI IGBC interpolates at MOD(global endpoint time, last table time).
    An extra future knot prevents the final accepted endpoint wrapping to zero.
    SETBCNEUL applies the pressure minus sign only to non-General inputs, so
    these scalar General values are already signed normal tractions.
    """
    nodes,_,faces=tube.read_mesh(source)
    index={node:i for i,node in enumerate(sorted(nodes),1)}
    profile=f['pressure_time'];ramp=profile.get('ramp_time',0.)
    times=[i*f['dt'] for i in range(steps+2)]
    values=[]
    for endpoint in times:
        t=endpoint-offset
        x=min(1.,max(0.,t/ramp)) if ramp>0 else 1.
        scale=x*x*x*(10+x*(-15+6*x))
        pressure=f['pressure']+profile['amplitude']*math.sin(2*math.pi*math.fmod(t,profile['period'])/profile['period'])
        values.append(-scale*pressure)
    for tag in (1,2):
        ids=sorted({index[n] for t,face in faces if t==tag for n in face})
        with (output/f'pressure-{tag}.txt').open('w') as stream:
            stream.write(f'1 {len(times)} {len(ids)}\n')
            stream.write(''.join(f'{t:.17g}\n' for t in times))
            series=''.join(f'{v:.17g}\n' for v in values)
            for node in ids:stream.write(f'{node}\n'+series)
    return dict(kind='General scalar normal traction',time_knots=len(times),
        table_end_time=times[-1],traction_sign=-1,ramp_time=ramp,
        scope='Exact prescribed values at fixed-step endpoint reads; linear interpolation between knots')


def export(case,output,hydrostatic=False,stage_pressure=False,output_start_step=1,general_pressure=False,tight_linear_atol=None):
    cfg=json.loads(case.read_text());f=cfg['fsi'];domains=f['domains']
    if tight_linear_atol is not None and (not math.isfinite(tight_linear_atol) or not 0<tight_linear_atol<1e-14):
        raise ValueError('Explicit tight linear absolute tolerance must be positive and below 1e-14')
    linear_atol='1e-14' if tight_linear_atol is None else format(tight_linear_atol,'.17g')
    if (type(output_start_step) is not int or not 1<=output_start_step<=f['steps'] or
            (hydrostatic and output_start_step!=1)):
        raise ValueError('Invalid output start step')
    if f.get('body')!='elastic' or f.get('material')!='linear' or f.get('inlet'):
        raise ValueError('Adapter requires a pressure-driven linear elastic tube')
    expected=lambda tags:[dict(tag=t,components=[0,1,2]) for t in tags]
    if (domains['pressure_tags']!=[1,2] or domains['fluid_constraints'] or
        domains['mesh_constraints']!=expected((1,2)) or domains['solid_constraints']!=expected((11,12)) or
        (domains['fluid_interface'],domains['solid_interface'])!=(3,13)):
        raise ValueError('Unsupported tube boundary configuration')
    time=cfg.get('time',{})
    if time.get('scheme')!='generalized_alpha':
        raise ValueError('Reference adapter requires generalized-alpha')
    profile=f.get('pressure_time')
    if general_pressure and not profile:
        raise ValueError('General pressure requires a pressure_time profile')
    if profile and (not all(math.isfinite(x) for x in (f['pressure'],f['dt'],profile['amplitude'],
            profile['period'],profile.get('ramp_time',0))) or f['dt']<=0 or profile['period']<=0 or profile.get('ramp_time',0)<0):
        raise ValueError('Invalid pressure profile')
    if profile and profile.get('ramp_time',0)!=0 and not general_pressure:
        raise ValueError('Fourier adapter does not approximate a startup ramp')
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Reference export requires an empty directory')
    summaries={}
    for name,path in (('fluid',cfg['mesh']),('solid',domains['solid_mesh'])):
        summaries[name]=write_mesh(case.parent/path,output/name)
    if summaries['fluid']['tags']!=[1,2,3] or summaries['solid']['tags']!=[11,12,13,14]:
        raise ValueError('Unexpected tube surface tags')
    steps=(min(f['steps'],round(profile['period']/f['dt'])) if profile else 3) if hydrostatic else f['steps']
    dt=f['dt']
    # MAIN increments global time before SETBCNEU, whereas PICI interpolates
    # pressure at alpha_f. An explicit adapter option supplies P(t_n+alpha_f*h)
    # at that endpoint-time read. No fitted phase or material change is used.
    offset=(1-1/(1+time.get('rho_infinity',.5)))*dt if stage_pressure else 0.
    lines=[f'Number of spatial dimensions: 3',f'Number of time steps: {steps}',f'Time step size: {dt:.17g}',
        f'Spectral radius of infinite time step: {time.get("rho_infinity",.5):.17g}',
        'Continue previous simulation: 0','Number of initialization time steps: 0',
        'Save results to VTK format: 1','Name prefix of saved VTK files: result',
        'Increment in saving VTK files: 1',f'Start saving after time step: {output_start_step}',
        'Increment in saving restart files: 100','Save results in folder: results','Verbose: 1','Warning: 1','Debug: 0']
    for name,domain in (('fluid',0),('solid',1)):
        if hydrostatic and name=='solid':
            continue
        lines += [f'Add mesh: {name} {{',f'  Mesh file path: {name}/volume.vtu',f'  Domain: {domain}']
        for tag in summaries[name]['tags']:
            lines += [f'  Add face: {name}{tag} {{',f'    Face file path: {name}/face-{tag}.vtp','  }']
        lines += ['}']
    if not hydrostatic:
        lines += ['Add projection: solid13 {','  Project from face: fluid3','}']
    lines += [f'Add equation: {"fluid" if hydrostatic else "FSI"} {{','  Coupled: 1',
        '  Min iterations: 1','  Max iterations: 30','  Tolerance: 1e-10']
    if not hydrostatic:
        lines += ['  Domain: 0 {','    Equation: fluid']
    lines += [f'    Density: {f.get("density",1):.17g}',f'    Viscosity: Constant {{ Value: {f.get("viscosity",1):.17g} }}',
              '    Backflow stabilization coefficient: 0.0']
    if not hydrostatic:
        lines += ['  }','  Domain: 1 {','    Equation: lElas',f'    Density: {f.get("solid_density",1):.17g}',
                  f'    Elasticity modulus: {f["young"]:.17g}',f'    Poisson ratio: {f["poisson"]:.17g}','  }']
    lines += ['  LS type: GMRES {','    Preconditioner: FSILS','    Tolerance: 1e-12',f'    Absolute tolerance: {linear_atol}',
        '    Max iterations: 1000','    Krylov space dimension: 100','  }',
        '  Output: Spatial {','    Velocity: t','    Pressure: t']
    if not hydrostatic:
        lines += ['    Displacement: t']
    lines += ['  }']
    if not hydrostatic:
        # Both equations otherwise write an array named Displacement. VTK
        # readers may replace one of those arrays, losing the physical solid
        # field or the ALE geometry. READOUTPUTS supports explicit aliases.
        lines += ['  Output: Alias {','    Displacement: Solid_displacement','  }']
    general=None
    if general_pressure:
        general=write_general_pressure(case.parent/cfg['mesh'],output,f,steps,offset)
    elif profile:
        # IFFT uses qi+t*qs+sum(r*cos(k*t)-i*sin(k*t)); the first row is DC.
        (output/'pressure.fcs').write_text(f'{offset:.17g}\n{profile["period"]:.17g}\n{f["pressure"]:.17g}\n0\n2\n0 0\n0 {-profile["amplitude"]:.17g}\n')
    for tag in (1,2):
        lines += [f'  Add BC: fluid{tag} {{','    Type: Neu']
        if general_pressure:
            lines += ['    Time dependence: General',f'    Temporal and spatial values file path: pressure-{tag}.txt']
        else:
            lines += (['    Time dependence: Unsteady','    Fourier coefficients file path: pressure.fcs'] if profile
                      else [f'    Value: {f["pressure"]:.17g}'])
        lines += ['  }']
    if hydrostatic:
        lines += ['  Add BC: fluid3 {','    Type: Dir','    Value: 0.0','  }']
    else:
        for tag in (11,12):
            lines += [f'  Add BC: solid{tag} {{','    Type: Dir','    Value: 0.0',
                '    Impose on state variable integral: t','    Zero out perimeter: f','    Effective direction: (1,1,1)','  }']
    lines += ['}']
    if not hydrostatic:
        lines += ['Add equation: mesh {','  Coupled: 1','  Min iterations: 1','  Max iterations: 30',
            '  Tolerance: 1e-10','  Poisson ratio: 0.3',
            '  LS type: CG {','    Preconditioner: FSILS','    Tolerance: 1e-12',f'    Absolute tolerance: {linear_atol}','    Max iterations: 1000','  }',
            '  Output: Spatial {','    Displacement: t','  }',
            '  Output: Alias {','    Displacement: Mesh_displacement','  }']
        for tag in (1,2):
            lines += [f'  Add BC: fluid{tag} {{','    Type: Dir','    Value: 0.0','  }']
        lines += ['}']
    (output/'svFSI.inp').write_text('\n'.join(lines)+'\n')
    (output/'source-case.json').write_text(json.dumps(cfg,indent=2)+'\n')
    manifest={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    report=dict(svfsi_commit='7bdb74cdd517310d6bf32c0bb7d42072aeac8658',mode='uniform-pressure import check' if hydrostatic else 'linear elastic pressure tube',
                meshes=summaries,files=manifest,pressure_time_offset=offset,
                load_evaluation='alpha_f stage' if stage_pressure else 'native endpoint-time input',
                scope='Prepared input; no reference agreement is inferred from export')
    if output_start_step!=1:report['output_start_step']=output_start_step
    if general is not None:report['general_pressure']=general
    if tight_linear_atol is not None:report['tight_linear_absolute_tolerance']=tight_linear_atol
    (output/'export.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--hydrostatic-smoke',action='store_true')
    p.add_argument('--stage-pressure',action='store_true',help='Explicitly align the continuous pressure law with the alpha_f assembly stage')
    p.add_argument('--output-start-step',type=int,default=1,help='First saved step, including the preceding endpoint needed for a later audit window')
    p.add_argument('--general-pressure',action='store_true',help='Explicit General table for the exact fixed-step pressure reads, including a smooth startup ramp')
    p.add_argument('--tight-linear-atol',type=float,help='Explicitly tighten both reference linear absolute stopping tolerances below 1e-14; nonlinear tolerances unchanged')
    a=p.parse_args();print(json.dumps(export(a.case.resolve(),a.output.resolve(),a.hydrostatic_smoke,a.stage_pressure,a.output_start_step,a.general_pressure,a.tight_linear_atol)))
