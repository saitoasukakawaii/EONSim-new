"""Small-strain Lamé pressure–area response of a plane-strain quarter annulus."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from audit_rigid_tube_fields import QUADRATURE
import study_rigid_tube as tube


INNER, OUTER, LENGTH = 1., 1.2, 2.
YOUNG, POISSON, PRESSURE = 100., .3, .02
LIMITS = dict(radius_relative_error=.02,area_relative_error=.02,displacement_relative_l2=.03)


def lame(radius, inner_pressure, outer_pressure=0.):
    """Plane strain: return radial displacement, radial and hoop Cauchy stresses."""
    a2,b2 = INNER**2,OUTER**2
    a = (inner_pressure*a2-outer_pressure*b2)/(b2-a2)
    b = (inner_pressure-outer_pressure)*a2*b2/(b2-a2)
    return ((1+POISSON)/YOUNG*((1-2*POISSON)*a*radius+b/radius),
            a-b/radius**2,a+b/radius**2)


def config(pressure):
    if not math.isfinite(pressure) or pressure<=0:
        raise ValueError('Use a finite positive internal pressure')
    rollers = [dict(tag=tag,type='displacement',components=[axis],value=[0,0,0])
               for tag,axis in ((11,0),(12,0),(15,1),(16,2))]
    loads = [dict(tag=13,type='pressure',value=pressure),dict(tag=14,type='pressure',value=0.)]
    return dict(mesh='wall.msh',output='solution.vtu',solid=dict(mode='static',material='linear',
                young=YOUNG,poisson=POISSON,density=1.,boundaries=rollers+loads),
                solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=20))


def make_case(directory, sectors, layers, axial, pressure):
    """Keep a quarter of the structured FSI wall; classify its two new symmetry faces."""
    if sectors<8 or sectors%4:
        raise ValueError('Use a full-circle sector count divisible by four and at least eight')
    cfg = config(pressure)
    directory.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        tube.generate(temp,sectors=sectors,radial=1,axial=axial,radius=INNER,
                      thickness=OUTER-INNER,length=LENGTH,wall_layers=layers)
        full,cells,tagged = tube.read_mesh(Path(temp)/'solid.msh')
    nodes = {n:tuple(0. if abs(v)<1e-14 else v for v in p)
             for n,p in full.items() if p[1]>=-1e-14 and p[2]>=-1e-14}
    quarter = [tet for tet in cells if all(n in nodes for n in tet)]
    exterior = {tuple(sorted(f)):tag for tag,f in tagged}
    incidence = Counter(tuple(sorted(t[:i]+t[i+1:])) for t in quarter for i in range(4))
    faces = []
    for f,count in incidence.items():
        if count==2:
            continue
        if count!=1:
            raise ValueError('Nonmanifold quarter wall')
        tag = exterior.get(f)
        if tag is None:
            if all(nodes[n][1]==0 for n in f):
                tag = 15
            elif all(nodes[n][2]==0 for n in f):
                tag = 16
            else:
                raise ValueError('Unexpected exposed face inside the quarter wall')
        faces.append((tag,f))
    tube.write_mesh(directory/cfg['mesh'],nodes,quarter,faces,region=20)
    (directory/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (directory/'geometry.json').write_text(json.dumps(dict(sectors=sectors,wall_layers=layers,
                                              axial=axial,inner=INNER,outer=OUTER,length=LENGTH),indent=2)+'\n')


def displacements(directory, ranks, nodes):
    owned = {}
    ghosts = []
    for rank in range(ranks):
        filename = 'solution.vtu' if ranks==1 else f'solution_rank{rank}.vtu'
        piece = ET.parse(directory/filename).find('.//Piece')
        data = {a.get('Name'):a.text.split() for a in piece.findall('PointData/DataArray')}
        ids = list(map(int,data['mesh_node_id']))
        disp = list(map(float,data['displacement']))
        xyz = list(map(float,piece.find('Points/DataArray').text.split()))
        owners = list(map(int,data['owner']))
        if len(owners)!=len(ids) or len(disp)!=3*len(ids) or len(xyz)!=len(disp):
            raise ValueError('Incomplete wall VTU point data')
        for i,n in enumerate(ids):
            value = tuple(disp[3*i:3*i+3])
            if not all(map(math.isfinite,value)) or tuple(xyz[3*i:3*i+3])!=nodes[n]:
                raise ValueError('Wall field or reference coordinates differ from the mesh')
            if owners[i]==rank:
                if n in owned:
                    raise ValueError('Duplicate displacement owner')
                owned[n] = value
            else:
                ghosts.append((n,value))
    if owned.keys()!=nodes.keys():
        raise ValueError('Incomplete wall displacement ownership')
    if any(max(abs(a-b) for a,b in zip(v,owned[n]))>1e-10 for n,v in ghosts):
        raise ValueError('Ghost and owner displacements differ')
    return owned


def bore_section(nodes, state, ring):
    """Area strain from the shoelace derivative, plus the finite deformed area."""
    ring = sorted(ring,key=lambda n:math.atan2(nodes[n][2],nodes[n][1]))
    area = area_change = quadratic = radial = 0.
    weights = [0.]*len(ring)
    for i,(a,b) in enumerate(zip(ring,ring[1:])):
        y,z = nodes[a][1:]
        Y,Z = nodes[b][1:]
        uy,uz = state[a][1:]
        vy,vz = state[b][1:]
        area += (y*Z-z*Y)/2
        area_change += (uy*Z+y*vz-uz*Y-z*vy)/2
        quadratic += (uy*vz-uz*vy)/2
        length = math.hypot(Y-y,Z-z)
        weights[i] += length/2
        weights[i+1] += length/2
    for n,weight in zip(ring,weights):
        y,z = nodes[n][1:]
        radial += weight*(y*state[n][1]+z*state[n][2])/math.hypot(y,z)
    return dict(radial_displacement=radial/sum(weights),area=area,linear_area_strain=area_change/area,
                deformed_area_strain=(area_change+quadratic)/area)


def analyze(directory, ranks=1):
    cfg = json.loads((directory/'case.json').read_text())
    p = next(b['value'] for b in cfg['solid']['boundaries'] if b['tag']==13)
    if cfg!=config(p):
        raise ValueError('Case differs from the declared Lamé problem')
    g = json.loads((directory/'geometry.json').read_text())
    s,m,k = (g[key] for key in ('sectors','wall_layers','axial'))
    if (g['inner'],g['outer'],g['length'])!=(INNER,OUTER,LENGTH) or s%4 or m<1 or k<2:
        raise ValueError('Inconsistent quarter-annulus specification')
    nodes,cells,faces = tube.read_mesh(directory/cfg['mesh'])
    if (len(cells)!=6*(s//4)*m*k or len(nodes)!=(s//4+1)*(m+1)*(k+1)
            or {tag for tag,_ in faces}!={11,12,13,14,15,16}):
        raise ValueError('Resolution or boundary tags differ from the quarter-wall mesh')
    log = (directory/'solve.log').read_text().splitlines()
    if not log or log[-1]!='status=success':
        raise ValueError('Missing successful solid solve')
    step, = [dict(v.split('=',1) for v in line.split()) for line in log if line.startswith('solid_step=')]
    if int(step['solid_step'])!=0:
        raise ValueError('Expected the static equilibrium step')
    state = displacements(directory,ranks,nodes)
    radius_exact = lame(INNER,p)[0]
    area_exact = 2*radius_exact/INNER
    inner = {n for tag,f in faces if tag==13 for n in f}
    slices = []
    for x in sorted({nodes[n][0] for n in inner}):
        ring = [n for n in inner if nodes[n][0]==x]
        if len(ring)!=s//4+1:
            raise ValueError('Incomplete bore ring')
        slices.append(dict(x=x,**bore_section(nodes,state,ring)))
    area = (s//4)*math.sin(2*math.pi/s)/2
    if len(slices)!=k+1 or any(not math.isclose(r['area'],area*INNER**2,rel_tol=1e-11) for r in slices):
        raise ValueError('Incorrect reference bore areas')
    error2 = exact2 = volume = work = 0.
    for tet in cells:
        v = tube.determinant(nodes,tet)/6
        if v<=0:
            raise ValueError('Nonpositive wall tetrahedron')
        volume += v
        for bary,weight in QUADRATURE:
            y,z = (sum(l*nodes[n][j] for l,n in zip(bary,tet)) for j in (1,2))
            radius = math.hypot(y,z)
            ur = lame(radius,p)[0]
            u = [sum(l*state[n][j] for l,n in zip(bary,tet)) for j in range(3)]
            error2 += v*weight*(u[0]**2+(u[1]-ur*y/radius)**2+(u[2]-ur*z/radius)**2)
            exact2 += v*weight*ur**2
    if not math.isclose(volume,LENGTH*area*(OUTER**2-INNER**2),rel_tol=1e-10):
        raise ValueError('Incorrect reference wall volume')
    for tag,face in faces:
        if tag!=13:
            continue
        a,b,c = (nodes[n] for n in face)
        av = tube.cross(tube.sub(b,a),tube.sub(c,a))
        sign = 1 if sum(av[j]*(a[j]+b[j]+c[j]) for j in (1,2))>0 else -1
        work += p*sign*sum(av[j]*sum(state[n][j] for n in face)/3 for j in range(3))/2
    strain_energy = float(step['strain_energy'])
    if not (work>0 and strain_energy>0 and error2>=0 and exact2>0):
        raise ValueError('Invalid elastic work, energy or displacement integral')
    metrics = dict(radius_relative_error=max(abs(r['radial_displacement']/radius_exact-1) for r in slices),
                   area_relative_error=max(abs(r['linear_area_strain']/area_exact-1) for r in slices),
                   displacement_relative_l2=math.sqrt(error2/exact2))
    return dict(sectors=s,wall_layers=m,axial=k,ranks=ranks,pressure=p,nodes=len(nodes),tetrahedra=len(cells),
                exact_radius_displacement=radius_exact,exact_linear_area_strain=area_exact,slices=slices,
                external_load_work=work,strain_energy=strain_energy,
                relative_work_energy_residual=abs(work-2*strain_energy)/work,**metrics,
                passed=all(value<LIMITS[name] for name,value in metrics.items()))


def solve(directory, executable, mpiexec, ranks, sectors, layers, axial, pressure):
    make_case(directory,sectors,layers,axial,pressure)
    command = [executable.resolve(),'-case','case.json']
    if ranks>1:
        tube.run([*command,'-prepare','parts','-parts',ranks],directory,'prepare.log')
        command = [mpiexec,'-n',ranks,*command,'-partition','parts']
    tube.run(command,directory,'solve.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--executable',type=Path)
    parser.add_argument('--mpiexec',default='mpiexec')
    parser.add_argument('--ranks',type=int,default=1)
    parser.add_argument('--mesh',type=int,nargs=3,metavar=('FULL_SECTORS','WALL_LAYERS','AXIAL'),default=(48,4,4))
    parser.add_argument('--pressure',type=float,default=PRESSURE)
    parser.add_argument('--analyze-only',action='store_true')
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    if args.ranks<1 or (not args.analyze_only and args.executable is None):
        parser.error('Use a positive rank count and supply the solver for a new run')
    if not args.analyze_only:
        solve(args.work,args.executable,args.mpiexec,args.ranks,*args.mesh,args.pressure)
    result = analyze(args.work,args.ranks)
    print(json.dumps(result,indent=2,allow_nan=False))
    if args.check and not result['passed']:
        raise SystemExit('Missed a Lamé wall target')


if __name__=='__main__':
    main()
