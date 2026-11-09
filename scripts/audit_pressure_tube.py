"""Read and audit the linear elastic equal-pressure tube's accepted fields.

The EONSim reader uses the standard library. The pinned svFSI reader needs VTK
in the separate analysis environment. Both are mapped by reference coordinates
and checked against the actual input topology; unused output points are ignored.
No elastic qualification is inferred from successful file reading alone.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

import study_rigid_tube as tube
from fsi_field_cycles import read_snapshot, series
from fsi_cycle_metrics import volume_budget


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def norm(a):
    return math.sqrt(dot(a,a))


def key(x):
    return tuple(round(v,9) for v in x)


class Domain:
    def __init__(self,path):
        self.path=Path(path)
        self.nodes,self.cells,self.faces=tube.read_mesh(path)
        self.lookup={key(x):n for n,x in self.nodes.items()}
        if len(self.lookup)!=len(self.nodes):
            raise ValueError('Ambiguous reference coordinates')
        self.topology={tuple(sorted(c)) for c in self.cells}
        self.volumes=[tube.determinant(self.nodes,c)/6 for c in self.cells]
        if len(self.topology)!=len(self.cells) or min(self.volumes)<=0:
            raise ValueError('Invalid input tetrahedra')
        self.volume=sum(self.volumes)
        self.parents={}
        counts=Counter()
        for c in self.cells:
            for j in range(4):
                f=tuple(sorted(c[:j]+c[j+1:]))
                counts[f]+=1;self.parents[f]=c
        if {tuple(sorted(f)) for _,f in self.faces}!={f for f,n in counts.items() if n==1}:
            raise ValueError('Input surface does not cover exterior')
        middle=(min(x[0] for x in self.nodes.values())+max(x[0] for x in self.nodes.values()))/2
        self.mid_pressure_weights={}
        for face,count in counts.items():
            if count!=2 or not all(abs(self.nodes[n][0]-middle)<1e-9 for n in face):continue
            a,b,c=[self.nodes[n] for n in face]
            area=norm(tube.cross(tube.sub(b,a),tube.sub(c,a)))/2
            for n in face:self.mid_pressure_weights[n]=self.mid_pressure_weights.get(n,0.)+area/3

    def canonical(self,nodes,cells,coordinate_type='Float64'):
        if coordinate_type not in ('Float32','Float64'):
            raise ValueError('Unsupported reference coordinate type')
        lookup=self.lookup
        if coordinate_type=='Float32':
            # The pinned svFSI writer rounds reference positions to binary32,
            # while its physical fields remain binary64. Match that exact
            # serialization, reject collisions, then retain the input geometry
            # for all physical integrals. Do not widen a distance tolerance.
            lookup={struct.unpack('=3f',struct.pack('=3f',*x)):n for n,x in self.nodes.items()}
            if len(lookup)!=len(self.nodes):
                raise ValueError('Ambiguous Float32 reference coordinates')
        mapping={};out={}
        for n,value in nodes.items():
            if any(len(v)!=(1 if field=='pressure' else 3) for field,v in value.items()):
                raise ValueError('Invalid physical field width')
            x=value['reference_position']
            target=lookup.get(tuple(x) if coordinate_type=='Float32' else key(x))
            if target is None or (coordinate_type=='Float64' and
                    max(abs(a-b) for a,b in zip(x,self.nodes[target]))>1e-9):
                raise ValueError('Output reference coordinates differ from input')
            if target in out:
                raise ValueError('Duplicate reference node within physical domain')
            if any(not math.isfinite(v) for values in value.values() for v in values):
                raise ValueError('Nonfinite physical output')
            mapping[n]=target
            out[target]=dict(value,reference_position=self.nodes[target]) if coordinate_type=='Float32' else value
        if out.keys()!=self.nodes.keys():
            raise ValueError('Incomplete physical output nodes')
        actual=[tuple(sorted(mapping[n] for n in c)) for c in cells]
        if len(actual)!=len(self.cells) or set(actual)!=self.topology:
            raise ValueError('Output tetrahedra differ from input')
        return out

    def rms_difference(self,a,b,field):
        integral=0.
        for c,volume in zip(self.cells,self.volumes):
            local=[[x-y for x,y in zip(a[n][field],b[n][field])] for n in c]
            total=[sum(v[j] for v in local) for j in range(len(local[0]))]
            integral+=volume*(dot(total,total)+sum(dot(v,v) for v in local))/20
        return math.sqrt(integral/self.volume)

    def geometry(self,frame,displacement):
        current={n:tuple(x+d for x,d in zip(self.nodes[n],frame[n][displacement])) for n in self.nodes}
        volumes=[tube.determinant(current,c)/6 for c in self.cells]
        minimum=min(v/r for v,r in zip(volumes,self.volumes))
        if not math.isfinite(minimum) or minimum<=0:
            raise ValueError('Nonpositive endpoint geometry')
        return current,volumes,minimum

    def surface_vector(self,face,coordinates):
        a,b,c=[coordinates[n] for n in face]
        av=tuple(v/2 for v in tube.cross(tube.sub(b,a),tube.sub(c,a)))
        parent=self.parents[tuple(sorted(face))]
        center=[sum(coordinates[n][j] for n in parent)/4 for j in range(3)]
        return tuple(-v for v in av) if dot(av,tube.sub(a,center))<0 else av


def eonsim_frame(path,domain,solid=False):
    nodes,_,cells=read_snapshot(path,solid=solid,include_cells=True)
    return domain.canonical(nodes,cells)


def svfsi_frame(path,domains):
    import vtk
    reader=vtk.vtkXMLUnstructuredGridReader();errors=[]
    reader.AddObserver('ErrorEvent',lambda *args:errors.append(str(args)))
    reader.SetFileName(str(path));reader.Update()
    if errors:
        raise ValueError(f'Invalid VTK output: {path}: {errors}')
    grid=reader.GetOutput();data=grid.GetPointData()
    if grid.GetPoints() is None:
        raise ValueError('Reference output has no coordinates')
    coordinate_type={vtk.VTK_FLOAT:'Float32',vtk.VTK_DOUBLE:'Float64'}.get(grid.GetPoints().GetDataType())
    if coordinate_type is None:
        raise ValueError('Unsupported reference coordinate type')
    names=[data.GetArrayName(i) for i in range(data.GetNumberOfArrays())]
    if len(names)!=len(set(names)):
        raise ValueError('Ambiguous duplicate reference field names')
    mesh_id=grid.GetCellData().GetArray('Mesh_ID')
    if mesh_id is None:
        raise ValueError('Reference output has no physical mesh IDs')
    result=[];seen=set()
    for region,(domain,fields) in enumerate(zip(domains,(
            {'velocity':'Velocity','pressure':'Pressure','mesh_displacement':'Mesh_displacement'},
            {'velocity':'Velocity','displacement':'Solid_displacement'})),1):
        arrays={name:data.GetArray(source) for name,source in fields.items()}
        if any(value is None for value in arrays.values()):
            raise ValueError(f'Missing unambiguous reference fields for mesh {region}')
        for name,value in arrays.items():
            if value.GetNumberOfComponents()!=(1 if name=='pressure' else 3):
                raise ValueError('Invalid reference field width')
        cells=[]
        for i in range(grid.GetNumberOfCells()):
            mid=mesh_id.GetTuple1(i);seen.add(mid)
            if mid!=region:continue
            cell=grid.GetCell(i)
            if cell.GetCellType()!=10 or cell.GetNumberOfPoints()!=4:
                raise ValueError('Reference cell is not Tet4')
            cells.append(tuple(cell.GetPointId(j) for j in range(4)))
        nodes={}
        for n in {n for c in cells for n in c}:
            nodes[n]={'reference_position':grid.GetPoint(n)}
            nodes[n].update({name:array.GetTuple(n) for name,array in arrays.items()})
        result.append(domain.canonical(nodes,cells,coordinate_type))
    if seen!={1.,2.}:
        raise ValueError('Unexpected reference physical mesh IDs')
    return tuple(result)


def ring(domain,tag=3):
    wall={n for t,f in domain.faces if t==tag for n in f}
    lo=min(x[0] for x in domain.nodes.values());hi=max(x[0] for x in domain.nodes.values())
    nodes=[n for n in wall if abs(domain.nodes[n][0]-(lo+hi)/2)<1e-9]
    nodes.sort(key=lambda n:math.atan2(domain.nodes[n][2],domain.nodes[n][1]))
    if len(nodes)<6:
        raise ValueError('No resolved material mid-ring')
    return nodes


def ring_metrics(domain,frame,current):
    ids=ring(domain)
    area=0.;radial=0.;length=0.
    # Four-point Gauss rule integrates the radial projection along each P1
    # polygon segment. This is a material ring, not an Eulerian plane cut.
    points=(-.8611363115940526,-.3399810435848563,.3399810435848563,.8611363115940526)
    weights=(.3478548451374538,.6521451548625461,.6521451548625461,.3478548451374538)
    for a,b in zip(ids,ids[1:]+ids[:1]):
        x,y=domain.nodes[a],domain.nodes[b];segment=norm(tube.sub(y,x));length+=segment
        area+=(current[a][1]*current[b][2]-current[b][1]*current[a][2])/2
        for z,w in zip(points,weights):
            t=(z+1)/2
            position=[(1-t)*x[j]+t*y[j] for j in range(3)]
            displacement=[(1-t)*frame[a]['mesh_displacement'][j]+t*frame[b]['mesh_displacement'][j] for j in range(3)]
            radial+=segment*w/2*dot(displacement[1:],position[1:])/norm(position[1:])
    if area<=0:
        raise ValueError('Invalid projected mid-ring area')
    return dict(mid_radial_displacement=radial/length,mid_ring_projected_area=area,
                mid_ring_axial_displacement=max(abs(frame[n]['mesh_displacement'][0]) for n in ids))


def fluid_metrics(domain,frame):
    coordinates,volumes,minimum=domain.geometry(frame,'mesh_displacement')
    flux={};pressure_integral={};area={}
    for tag,face in domain.faces:
        av=domain.surface_vector(face,coordinates)
        velocity=[sum(frame[n]['velocity'][j] for n in face)/3 for j in range(3)]
        flux[tag]=flux.get(tag,0.)+dot(velocity,av)
        weight=norm(av);area[tag]=area.get(tag,0.)+weight
        pressure_integral[tag]=pressure_integral.get(tag,0.)+weight*sum(frame[n]['pressure'][0] for n in face)/3
    integral=squared=0.
    for c,volume in zip(domain.cells,volumes):
        e1,e2,e3=[tube.sub(coordinates[c[j]],coordinates[c[0]]) for j in (1,2,3)]
        inverse=[tuple(x/(6*volume) for x in v) for v in (tube.cross(e2,e3),tube.cross(e3,e1),tube.cross(e1,e2))]
        divergence=sum(dot(tube.sub(frame[c[j+1]]['velocity'],frame[c[0]]['velocity']),inverse[j]) for j in range(3))
        integral+=volume*divergence;squared+=volume*divergence**2
    result=dict(volume=sum(volumes),minimum_fluid_jacobian=minimum,
        outward_flow_left=flux[1],outward_flow_right=flux[2],wall_flux=flux[3],
        total_outward_flux=sum(flux.values()),divergence_integral=integral,
        divergence_theorem_defect=abs(sum(flux.values())-integral),
        divergence_rms=math.sqrt(squared/sum(volumes)),
        pressure_left=pressure_integral[1]/area[1],pressure_right=pressure_integral[2]/area[2])
    weights=domain.mid_pressure_weights
    if not weights:raise ValueError('No mesh-aligned reference mid-section')
    result['mid_pressure']=sum(frame[n]['pressure'][0]*w for n,w in weights.items())/sum(weights.values())
    result.update(ring_metrics(domain,frame,coordinates))
    return result


def interface_errors(fluid,solid,ff,sf):
    wall={n for tag,face in fluid.faces if tag==3 for n in face}
    solid_wall={n for tag,face in solid.faces if tag==13 for n in face}
    mapping={key(solid.nodes[n]):n for n in solid_wall}
    if {key(fluid.nodes[n]) for n in wall}!=mapping.keys():
        raise ValueError('Input interface is not conforming')
    result=dict(interface_velocity=0.,interface_displacement=0.,clamped_solid_velocity=0.,
                clamped_solid_displacement=0.,fixed_mesh_cap=0.)
    for n in wall:
        other=mapping[key(fluid.nodes[n])]
        for label,left,right in (('interface_velocity','velocity','velocity'),
                                 ('interface_displacement','mesh_displacement','displacement')):
            result[label]=max(result[label],norm(tube.sub(ff[n][left],sf[other][right])))
    for n in {n for tag,face in solid.faces if tag in (11,12) for n in face}:
        for label,field in (('clamped_solid_velocity','velocity'),('clamped_solid_displacement','displacement')):
            result[label]=max(result[label],norm(sf[n][field]))
    result['fixed_mesh_cap']=max(norm(ff[n]['mesh_displacement']) for tag,face in fluid.faces if tag in (1,2) for n in face)
    return result


def harmonic(rows,field,period):
    n=len(rows)
    if n<4 or any(not math.isfinite(row[field]) for row in rows):
        raise ValueError('Invalid harmonic samples')
    dt=period/n
    if any(abs(rows[i]['time']-rows[i-1]['time']-dt)>1e-9*period for i in range(1,n)):
        raise ValueError('Harmonics require one complete equally sampled cycle')
    sine=2*sum(row[field]*math.sin(2*math.pi*row['time']/period) for row in rows)/n
    cosine=2*sum(row[field]*math.cos(2*math.pi*row['time']/period) for row in rows)/n
    mean=sum(row[field] for row in rows)/n
    higher=math.sqrt(sum((row[field]-mean-sine*math.sin(2*math.pi*row['time']/period)-cosine*math.cos(2*math.pi*row['time']/period))**2 for row in rows)/n)
    return dict(mean=mean,sine=sine,cosine=cosine,amplitude=math.hypot(sine,cosine),
                phase_degrees=math.degrees(math.atan2(cosine,sine)),higher_harmonic_rms=higher)


def analyze(case,work,reference=False,first_step=1,reference_log=None,reference_chain=None):
    cfg=json.loads(case.read_text());f=cfg['fsi'];profile=f['pressure_time']
    if (f['body']!='elastic' or f['material']!='linear' or f.get('inlet') or
        f['domains']['pressure_tags']!=[1,2] or cfg.get('time',{}).get('scheme')!='generalized_alpha'):
        raise ValueError('Requires a linear equal-pressure elastic tube')
    fluid=Domain(case.parent/cfg['mesh']);solid=Domain(case.parent/f['domains']['solid_mesh'])
    period=profile['period'];dt=f['dt'];n=round(period/dt);steps=f['steps']
    if (abs(n*dt-period)>1e-10*period or steps%n or type(first_step) is not int or
            first_step<1 or (first_step-1)%n or steps-first_step+1<3*n):
        raise ValueError('Need at least three complete equally sampled cycles')
    if (steps-3*n)*dt<profile.get('ramp_time',0.)-1e-10*period:
        raise ValueError('Need at least three complete cycles after the startup ramp')
    geometry=json.loads((case.parent/'geometry.json').read_text())
    radius=geometry['radius'];outer=radius+geometry['thickness'];length=geometry['length']
    for domain,target in ((fluid,radius),(solid,outer)):
        if abs(max(norm(x[1:]) for x in domain.nodes.values())-target)>1e-9:
            raise ValueError('Geometry metadata radius differs from actual mesh')
        if abs(max(x[0] for x in domain.nodes.values())-min(x[0] for x in domain.nodes.values())-length)>1e-9:
            raise ValueError('Geometry metadata length differs from actual mesh')
    nu=f['poisson'];young=f['young']
    compliance=(1+nu)*((1-2*nu)*radius**2+outer**2)*radius/(young*(outer**2-radius**2))
    dscale=abs(profile['amplitude'])*compliance
    if dscale<=0:
        raise ValueError('Need a nonzero oscillatory pressure scale')
    omega=2*math.pi/period
    scales=({'velocity':dscale*omega*length/radius,'pressure':abs(profile['amplitude']),'mesh_displacement':dscale},
            {'velocity':dscale*omega,'displacement':dscale})
    if reference_log is not None and reference_chain is not None:
        raise ValueError('Choose a reference log or an explicit restart chain')
    if (reference_log is not None or reference_chain is not None) and not reference:
        raise ValueError('Reference log requires svFSI fields')
    convergence=None;reference_input_hash=None
    paths=[];initial_path=None
    required=set(range(first_step-(first_step>1),steps+1))
    if reference:
        report=json.loads((work/'export.json').read_text())
        if report['mode']!='linear elastic pressure tube' or report['load_evaluation']!='alpha_f stage':
            raise ValueError('Reference requires explicit stage-pressure input')
        if json.loads((work/'source-case.json').read_text())!=cfg:
            raise ValueError('Reference case differs from requested case')
        for name,digest in report['files'].items():
            if hashlib.sha256((work/name).read_bytes()).hexdigest()!=digest:
                raise ValueError(f'Reference input changed: {name}')
        reference_input_hash=hashlib.sha256((work/'export.json').read_bytes()).hexdigest()
        if reference_log is not None:
            from audit_svfsi_convergence import analyze as analyze_convergence
            convergence=analyze_convergence(work,reference_log)
            if convergence['first_step']!=1 or convergence['last_step']!=steps:
                raise ValueError('Reference restart requires a complete chain for full-study convergence')
        if reference_chain is not None:
            from svfsi_restart_evidence import analyze_chain
            convergence=analyze_chain(reference_chain,expected_work=work,expected_steps=steps)
        output_paths=list((work/'results').glob('result_*.vtu'))
        outputs={int(p.stem.rsplit('_',1)[1]):p for p in output_paths}
        if len(outputs)!=len(output_paths):
            raise ValueError('Duplicate reference output step')
        if not required<=set(outputs) or not set(outputs)<=set(range(1,steps+1)):
            raise ValueError('Incomplete reference output history')
        if reference_chain is not None:
            for boundary in convergence['boundaries']:
                if boundary['step'] in required:
                    digest=hashlib.sha256(outputs[boundary['step']].read_bytes()).hexdigest()
                    if digest!=boundary.get('output_sha256'):
                        raise ValueError('Reference restart boundary output differs from its original endpoint')
        paths=[outputs[i] for i in range(first_step,steps+1)]
        if first_step>1:initial_path=outputs[first_step-1]
    else:
        fluid_series=series(work/'solution.pvd');solid_series=series(work/'solution_solid.pvd')
        if len(fluid_series)!=len(solid_series):
            raise ValueError('Incomplete EONSim output history')
        outputs={}
        for (t,p),(s,q) in zip(fluid_series,solid_series):
            if not math.isfinite(t) or not math.isfinite(s):
                raise ValueError('Nonfinite EONSim accepted output time')
            i=round(t/dt)
            if i in outputs or not 1<=i<=steps or abs(t-i*dt)>1e-9*period or abs(s-t)>1e-10*period:
                raise ValueError('EONSim accepted output times differ from requested grid')
            outputs[i]=(p,q)
        if not required<=set(outputs):
            raise ValueError('Incomplete EONSim output history')
        paths=[outputs[i] for i in range(first_step,steps+1)]
        if first_step>1:initial_path=outputs[first_step-1]
    def read(path):
        return svfsi_frame(path,(fluid,solid)) if reference else (eonsim_frame(path[0],fluid),eonsim_frame(path[1],solid,True))
    rows=[];previous={};cycles={};defects={};minimum_solid=math.inf
    previous_endpoint={n:dict(reference_position=x,velocity=[0.]*3,pressure=[0.],mesh_displacement=[0.]*3)
                       for n,x in fluid.nodes.items()}
    initial_volume=fluid.volume;initial_net=0.;initial_minimum_fluid=math.inf
    if initial_path is not None:
        previous_endpoint,initial_solid=read(initial_path)
        initial_metrics=fluid_metrics(fluid,previous_endpoint)
        initial_volume=initial_metrics['volume']
        initial_minimum_fluid=initial_metrics['minimum_fluid_jacobian']
        initial_net=-initial_metrics['outward_flow_left']-initial_metrics['outward_flow_right']
        _,_,minimum_solid=solid.geometry(initial_solid,'displacement')
        defects.update(interface_errors(fluid,solid,previous_endpoint,initial_solid))
    for step,path in enumerate(paths,first_step):
        ff,sf=read(path)
        row=dict(step=step,time=step*dt,**fluid_metrics(fluid,ff));rows.append(row)
        af=1. if step==1 and not reference else 1/(1+cfg['time'].get('rho_infinity',.5))
        stage={n:{field:tuple((1-af)*a+af*b for a,b in zip(previous_endpoint[n][field],ff[n][field]))
                  for field in ff[n]} for n in ff}
        stage_metrics=fluid_metrics(fluid,stage)
        row.update(evaluation_time=(step-1+af)*dt,
            stage_total_outward_flux=stage_metrics['total_outward_flux'],
            stage_divergence_theorem_defect=stage_metrics['divergence_theorem_defect'],
            stage_minimum_fluid_jacobian=stage_metrics['minimum_fluid_jacobian'])
        previous_endpoint=ff
        _,_,quality=solid.geometry(sf,'displacement');minimum_solid=min(minimum_solid,quality)
        for name,value in interface_errors(fluid,solid,ff,sf).items():
            defects[name]=max(defects.get(name,0.),value)
        phase=(step-1)%n;cycle=(step-1)//n+1
        if phase in previous:
            metrics=cycles.setdefault(cycle,{})
            # Keep paths instead of a full cycle of nodal dictionaries. A dense
            # fine-grid cycle can exceed the analysis memory limit by itself.
            for domain,a,b,scale,prefix in zip((fluid,solid),read(previous[phase]),(ff,sf),scales,('fluid','solid')):
                for field,value in scale.items():
                    error=domain.rms_difference(a,b,field)/value
                    entry=metrics.setdefault(prefix+'_'+field,dict(relative_max=0.,relative_rms_squared=0.))
                    entry['relative_max']=max(entry['relative_max'],error)
                    entry['relative_rms_squared']+=error*error/n
        previous[phase]=path
    for metrics in cycles.values():
        for entry in metrics.values():
            entry['relative_rms']=math.sqrt(entry.pop('relative_rms_squared'))
    last=steps//n
    periodic=all(value['relative_max']<1e-5 for cycle in (last-1,last) for value in cycles[cycle].values())
    fields=('mid_radial_displacement','mid_ring_projected_area','mid_pressure','pressure_left','pressure_right','outward_flow_left','outward_flow_right')
    harmonics={field:harmonic(rows[-n:],field,period) for field in fields}
    mass_rows=[dict(time=r['time'],accepted_dt=dt,endpoint_volume=r['volume'],
                   endpoint_inlet_flow=-r['outward_flow_left'],endpoint_outlet_flow=r['outward_flow_right']) for r in rows]
    quality={name:dict(maximum=value,limit=limit,passed=value<limit) for name,value,limit in (
        ('kinematics',max(defects.values()),1e-12),
        ('stage_mass',max(abs(r['stage_total_outward_flux']) for r in rows),1e-9),
        ('stage_divergence_theorem',max(r['stage_divergence_theorem_defect'] for r in rows),1e-12))}
    return dict(case_sha256=hashlib.sha256(case.read_bytes()).hexdigest(),solver='svFSI' if reference else 'EONSim',
        reference_convergence=convergence,reference_input_manifest_sha256=reference_input_hash,
        analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        physical_definition=dict(radius=radius,outer_radius=outer,length=length,young=young,poisson=nu,
            density=f['density'],solid_density=f['solid_density'],viscosity=f['viscosity'],pressure=f['pressure'],pressure_time=profile),
        infinite_plane_strain_compliance=compliance,
        quality_gates=quality,
        steps=steps,first_step=first_step,sampled_steps=len(rows),period=period,samples_per_cycle=n,
        analysis_window=dict(first_step=first_step,last_step=steps,initial_step=first_step-1,
            initial_state='zero startup' if first_step==1 else 'actual preceding endpoint',
            scope='Quality and period metrics cover this stored window; no unstored warmup field claim'),
        scales=scales,periodic=periodic,cycle_differences=cycles,
        maximum_kinematic_defects=defects,minimum_solid_jacobian=minimum_solid,
        minimum_fluid_jacobian=min(initial_minimum_fluid,min(r['minimum_fluid_jacobian'] for r in rows)),
        maximum_total_outward_flux=max(abs(r['total_outward_flux']) for r in rows),
        maximum_stage_total_outward_flux=max(abs(r['stage_total_outward_flux']) for r in rows),
        maximum_stage_divergence_theorem_defect=max(r['stage_divergence_theorem_defect'] for r in rows),
        maximum_divergence_theorem_defect=max(r['divergence_theorem_defect'] for r in rows),
        endpoint_trapezoidal_volume_budget=volume_budget(mass_rows,initial_time=(first_step-1)*dt,
            initial_volume=initial_volume,initial_net_flow=initial_net),
        harmonics=harmonics,rows=rows,
        reference_meshes={d.path.name:hashlib.sha256(d.path.read_bytes()).hexdigest() for d in (fluid,solid)},
        interpretation='Endpoint fields; stage mass is reconstructed with alpha_f (EONSim first step is BE). Endpoint net flux and trapezoidal volume budget are separate diagnostics. Projected area/radial mean follow the reference material mid-ring, and pressure uses reference area weights at the material mid-section. No Eulerian plane cut. Period norms use exact P1 reference mass integrals.',
        qualification='Incomplete: space/time/tail/sampling, geometry and cross-solver comparisons remain required')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--svfsi',action='store_true');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--first-step',type=int,default=1,help='First audited step, aligned to a full cycle; requires the actual preceding endpoint')
    evidence=parser.add_mutually_exclusive_group()
    evidence.add_argument('--reference-log',type=Path,help='Evidence for one original or explicitly initialized native segment')
    evidence.add_argument('--reference-chain',type=Path,help='Original and native restart segments covering the complete study')
    args=parser.parse_args()
    result=analyze(args.case.resolve(),args.work.resolve(),args.svfsi,args.first_step,args.reference_log,args.reference_chain)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','cycle_differences')},allow_nan=False))
