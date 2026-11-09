"""Steady rigid-pipe qualification; no transient or elastic-wall claim.

Red refinement preserves the original polygon, including straight boundary edges.
All numerical inputs/outputs are relative to each case directory and replayable.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/fsi'))
from generate_tube import generate

RADIUS, LENGTH, VISCOSITY, DENSITY, DROP = 1., 2., 1., 1., .02
Q_EXACT = math.pi * RADIUS**4 * DROP / (8 * VISCOSITY * LENGTH)
LIMITS = dict(circle_flow_relative=.02, last_field_change_relative=.01,
              mpi_absolute=2e-9, net_flux_absolute=1e-10)


def read_mesh(path):
    lines = Path(path).read_text().splitlines()
    nodes = {int(v[0]): tuple(map(float, v[1:])) for v in
             (line.split() for line in lines[lines.index('$Nodes')+2:lines.index('$EndNodes')])}
    cells, faces = [], []
    for line in lines[lines.index('$Elements')+2:lines.index('$EndElements')]:
        v = list(map(int, line.split()))
        if v[1] == 4:
            cells.append(tuple(v[3+v[2]:]))
        elif v[1] == 2:
            faces.append((v[3], tuple(v[3+v[2]:])))
        else:
            raise ValueError('Expected Tet4/Tri3 mesh')
    return nodes, cells, faces


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def determinant(nodes, tet):
    a, b, c, d = [nodes[i] for i in tet]
    return sum(x*y for x, y in zip(sub(b, a), cross(sub(c, a), sub(d, a))))


def refine(nodes, cells, faces):
    nodes = dict(nodes)
    edges = {}
    def midpoint(a, b):
        key = tuple(sorted((a, b)))
        if key not in edges:
            edges[key] = len(nodes)+1
            nodes[edges[key]] = tuple((x+y)/2 for x, y in zip(nodes[a], nodes[b]))
        return edges[key]
    refined = []
    for a, b, c, d in cells:
        ab, ac, ad, bc, bd, cd = [midpoint(i,j) for i,j in
                                 ((a,b),(a,c),(a,d),(b,c),(b,d),(c,d))]
        # Split the interior octahedron along ab--cd. Face subdivisions are
        # independent of this diagonal, so adjacent tetrahedra remain conforming.
        refined.extend(((a,ab,ac,ad),(b,ab,bc,bd),(c,ac,bc,cd),(d,ad,bd,cd),
                        (ab,cd,ac,ad),(ab,cd,ad,bd),(ab,cd,bd,bc),(ab,cd,bc,ac)))
    refined = [t if determinant(nodes,t)>0 else (t[1],t[0],t[2],t[3]) for t in refined]
    boundary = []
    for tag, (a,b,c) in faces:
        ab, ac, bc = midpoint(a,b), midpoint(a,c), midpoint(b,c)
        boundary.extend((tag,t) for t in ((a,ab,ac),(b,bc,ab),(c,ac,bc),(ab,bc,ac)))
    return nodes, refined, boundary


def write_mesh(path, nodes, cells, faces, region=10):
    if not isinstance(region,int) or isinstance(region,bool) or region<=0:
        raise ValueError('Volume region must be a positive integer')
    with Path(path).open('w') as f:
        f.write(f'$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n{len(nodes)}\n')
        for i, x in nodes.items():
            f.write(f'{i} '+ ' '.join(format(v,'.17g') for v in x)+'\n')
        f.write(f'$EndNodes\n$Elements\n{len(cells)+len(faces)}\n')
        for i, (tag, t) in enumerate(faces, 1):
            f.write(f'{i} 2 2 {tag} {tag} '+' '.join(map(str,t))+'\n')
        for i, t in enumerate(cells, len(faces)+1):
            f.write(f'{i} 4 2 {region} {region} '+' '.join(map(str,t))+'\n')
        f.write('$EndElements\n')


def case_config():
    boundaries = [dict(tag=3,type='velocity',value=[0,0,0])]
    for tag, pressure in ((1,DROP),(2,0.)):
        boundaries.extend((dict(tag=tag,type='pressure',value=pressure,components=[0]),
                           dict(tag=tag,type='velocity',value=[0,0,0],components=[1,2])))
    return dict(mesh='fluid.msh',output='solution.vtu',
                  fluid=dict(mode='stokes',density=DENSITY,viscosity=VISCOSITY,boundaries=boundaries),
                  solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30))


def make_case(directory, sectors, level):
    directory.mkdir(parents=True, exist_ok=True)
    generate(directory/'base', sectors=sectors, axial=2, radial=2,
             radius=RADIUS, length=LENGTH)
    mesh = read_mesh(directory/'base/fluid.msh')
    for _ in range(level):
        mesh = refine(*mesh)
    write_mesh(directory/'fluid.msh', *mesh)
    (directory/'case.json').write_text(json.dumps(case_config(),indent=2)+'\n')


def _session_members(session):
    """Linux solver session members, including ranks in separate process groups."""
    result = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path/'stat').read_text().rsplit(')',1)[1].split()
            if int(fields[3]) == session and fields[0] != 'Z':
                result[int(path.name)] = fields[19]  # start identity, not just PID
        except (FileNotFoundError, ProcessLookupError):
            pass
    return result


def _stop_session(process):
    """Bound cleanup to the new Linux session owned by this one invocation."""
    session = process.pid
    record = dict(session=session, before=_session_members(session), signals=[])
    if process.poll() is None:
        # Give mpiexec a chance to relay cancellation and reap its ranks.
        process.send_signal(signal.SIGINT)
        record['signals'].append(dict(pid=process.pid, signal='SIGINT'))
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    for sig, grace in ((signal.SIGTERM,2.), (signal.SIGKILL,5.)):
        for pid, start in _session_members(session).items():
            # OpenMPI gives ranks their own process groups. Enumerate the
            # entire session even if the launcher has already exited.
            if _session_members(session).get(pid) != start:
                continue
            try:
                os.kill(pid,sig)
                record['signals'].append(dict(pid=pid,start=start,signal=sig.name))
            except ProcessLookupError:
                pass
        deadline = time.monotonic()+grace
        while _session_members(session) and time.monotonic()<deadline:
            time.sleep(.05)
    process.wait(timeout=5)
    record['after'] = _session_members(session)
    if record['after']:
        raise RuntimeError(f'Solver session {session} did not exit: {record["after"]}')
    return record


def run(command, directory, name, timeout=900):
    # Stream to disk so long solves and interrupted attempts leave live evidence.
    command = list(map(str,command))
    linux_session = sys.platform.startswith('linux')
    with (directory/name).open('w') as log:
        if not linux_session:
            # Preserve the existing non-Linux runner; the MPI session cleanup
            # contract below is specifically for the Linux/WSL production path.
            result = subprocess.run(command,cwd=directory,text=True,stdout=log,
                                    stderr=subprocess.STDOUT,timeout=timeout)
        else:
            result = subprocess.Popen(command,cwd=directory,text=True,stdout=log,
                                      stderr=subprocess.STDOUT,start_new_session=True)
            def cleanup():
                record = _stop_session(result)
                (directory/(str(name)+'.cleanup.json')).write_text(json.dumps(record,indent=2)+'\n')
            try:
                result.wait(timeout=timeout)
            except BaseException:
                cleanup()
                raise
            if _session_members(result.pid):
                cleanup()
                raise RuntimeError(f'{directory/name}: solver launcher left running child processes')
    if result.returncode or 'status=success' not in (directory/name).read_text():
        raise RuntimeError(f'{directory/name}: solver failed ({result.returncode})')


def fields(directory, ranks):
    owned, ghosts = {}, []
    for rank in range(ranks):
        path = directory/('solution.vtu' if ranks==1 else f'solution_rank{rank}.vtu')
        root = ET.parse(path)
        data = {v.attrib['Name']:v.text.split() for v in root.findall('.//PointData/DataArray')}
        for i, node in enumerate(data['mesh_node_id']):
            value = tuple(map(float,data['velocity'][3*i:3*i+3]+[data['pressure'][i]]))
            if not all(math.isfinite(x) for x in value):
                raise ValueError('Nonfinite field')
            node = int(node)
            if int(data['owner'][i]) == rank:
                if node in owned:
                    raise ValueError('Duplicate owner')
                owned[node] = value
            else:
                ghosts.append((node,value))
    if any(max(abs(x-y) for x,y in zip(v,owned[n]))>LIMITS['mpi_absolute'] for n,v in ghosts):
        raise ValueError('Ghost mismatch')
    return owned


def analyze(directory, sectors, level, ranks=1):
    if json.loads((directory/'case.json').read_text())!=case_config():
        raise ValueError('Case parameters differ from the declared reference problem')
    if 'status=success' not in (directory/('solve.log' if ranks==1 else 'solve-mpi.log')).read_text():
        raise ValueError('Missing successful solve log')
    nodes, cells, faces = read_mesh(directory/'fluid.msh')
    state = fields(directory,ranks)
    if state.keys()!=nodes.keys():
        raise ValueError('Incomplete field')
    volumes = [determinant(nodes,t)/6 for t in cells]
    if min(volumes)<=0:
        raise ValueError('Nonpositive tetrahedron')
    expected_volume = sectors*RADIUS**2*math.sin(2*math.pi/sectors)*LENGTH/2
    if abs(sum(volumes)-expected_volume)>1e-10*expected_volume:
        raise ValueError('Polygon volume changed during refinement')
    flux, area, pressure = {}, {}, {}
    for tag, face in faces:
        a,b,c = [nodes[n] for n in face]
        av = cross(sub(b,a),sub(c,a))
        surface = math.sqrt(sum(v*v for v in av))/2
        center = tuple(sum(nodes[n][i] for n in face)/3 for i in range(3))
        outward = (-1,0,0) if tag==1 else (1,0,0) if tag==2 else (0,center[1],center[2])
        sign = 1 if sum(x*y for x,y in zip(av,outward))>0 else -1
        q = sign*sum(av[i]*sum(state[n][i] for n in face)/3 for i in range(3))/2
        flux[tag] = flux.get(tag,0.)+q
        area[tag] = area.get(tag,0.)+surface
        pressure[tag] = pressure.get(tag,0.)+surface*sum(state[n][3] for n in face)/3
    q = (flux[2]-flux[1])/2
    volume_flow = sum(volume*sum(state[n][0] for n in tet)/4
                      for volume,tet in zip(volumes,cells))/LENGTH
    measured_drop = pressure[1]/area[1]-pressure[2]/area[2]
    if not q>0 or abs(sum(flux.values()))>=LIMITS['net_flux_absolute']:
        raise ValueError('Invalid flow or net flux')
    return dict(sectors=sectors,level=level,nodes=len(nodes),tetrahedra=len(cells),ranks=ranks,
                flow=q,circle_flow_relative_error=abs(q/Q_EXACT-1),
                polygon_continuum_flow_lower_bound=Q_EXACT*math.cos(math.pi/sectors)**4,
                polygon_continuum_flow_upper_bound=Q_EXACT,
                net_outward_flux=sum(flux.values()),volume=sum(volumes),
                measured_pressure_drop=measured_drop,
                measured_pressure_drop_relative_error=abs(measured_drop/DROP-1),
                volume_average_flow=volume_flow,
                mean_to_end_flow_relative_difference=abs(volume_flow-q)/Q_EXACT,
                maximum_transverse_velocity=max(abs(v[i]) for v in state.values() for i in (1,2)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path)
    parser.add_argument('--mpiexec',default='mpiexec')
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--study',action='store_true',help='Run full geometry/field refinement study')
    parser.add_argument('--case',type=int,nargs=2,action='append',metavar=('SECTORS','LEVEL'),
                        help='Add individual states without rerunning existing evidence')
    parser.add_argument('--analyze-only',action='store_true',help='Recompute from relocated mesh/VTU/log files')
    args = parser.parse_args()
    if not args.analyze_only and args.executable is None:
        parser.error('--executable is required for solves')
    work = args.work.resolve(); work.mkdir(parents=True,exist_ok=True)
    if args.case and args.study:
        parser.error('--case and --study are mutually exclusive')
    cases = args.case or ([(12,l) for l in range(5)]+[(48,l) for l in range(4)]+[(24,2),(24,3)]
                          if args.study else [(12,0),(12,1)])
    if any(s<6 or l<0 or l>4 for s,l in cases):
        parser.error('Require sectors >=6 and level 0..4')
    results = []
    for sectors, level in cases:
        directory = work/f's{sectors}-l{level}'
        if not args.analyze_only:
            make_case(directory,sectors,level)
            run([args.executable.resolve(),'-case','case.json'],directory,'solve.log')
        result = analyze(directory,sectors,level); results.append(result)
        print(json.dumps(result),flush=True)
    if args.case:
        return
    # One actual distributed state on an identical, moderately sized mesh.
    directory = work/'s12-l1'
    if not args.analyze_only:
        run([args.executable.resolve(),'-case','case.json','-prepare','parts','-parts',2],directory,'prepare.log')
        run([args.mpiexec,'-n',2,args.executable.resolve(),'-case','case.json','-partition','parts'],directory,'solve-mpi.log')
    serial, parallel = fields(directory,1), fields(directory,2)
    if serial.keys()!=parallel.keys():
        raise ValueError('MPI ownership mismatch')
    mpi_error = max(abs(x-y) for n in serial for x,y in zip(serial[n],parallel[n]))
    if mpi_error>=LIMITS['mpi_absolute']:
        raise ValueError(f'MPI field difference {mpi_error}')
    mpi_result = analyze(directory,12,1,2)
    changes = {}
    if args.study:
        for sectors, levels in ((12,range(5)),(48,range(4))):
            q = [next(r['flow'] for r in results if r['sectors']==sectors and r['level']==l) for l in levels]
            differences = [abs(y-x)/Q_EXACT for x,y in zip(q,q[1:])]
            changes[str(sectors)] = differences
            if not all(y<x for x,y in zip(differences,differences[1:])) or differences[-1]>=LIMITS['last_field_change_relative']:
                raise ValueError(f'Field refinement not accepted: {sectors}, {differences}')
        fine = next(r for r in results if (r['sectors'],r['level'])==(48,3))
        if fine['circle_flow_relative_error']>=LIMITS['circle_flow_relative']:
            raise ValueError(f'Circular flow not accepted: {fine}')
    elif results[-1]['circle_flow_relative_error']>=.20:
        raise ValueError('Small regression case exceeds its 20% flow smoke-test limit')
    report = dict(schema=1,scope='steady rigid tube only',limits=LIMITS,
                  parameters=dict(radius=RADIUS,length=LENGTH,viscosity=VISCOSITY,density=DENSITY,
                                  pressure_drop=DROP,analytic_flow=Q_EXACT,
                                  reynolds=2*DENSITY*Q_EXACT/(math.pi*VISCOSITY*RADIUS),womersley=0),
                  states=results,field_changes_relative=changes,mpi_field_max=mpi_error,mpi_state=mpi_result)
    if not args.analyze_only:
        report['executable_sha256'] = hashlib.sha256(args.executable.read_bytes()).hexdigest()
    name = 'recomputed.json' if args.analyze_only else 'summary.json'
    (work/name).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('rigid tube verification passed',flush=True)


if __name__ == '__main__':
    main()
