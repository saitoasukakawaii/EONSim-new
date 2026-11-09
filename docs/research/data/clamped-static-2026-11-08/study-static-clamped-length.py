"""Static full-annulus end-length diagnostic; does not replace coupled gates."""
import fcntl,hashlib,json,math,os,re,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts'))
import study_rigid_tube as tube
work=Path('/home/tfblab633/EONSim-prod48-20261107');out=work/'static-clamped-length-6093f01'
status=work/'static-clamped-length-current.json';prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
scale=.02*(1+.3)/1000*(1.2**2+(1-2*.3))/(1.2**2-1)
planned=[(s,l,L) for s,l in ((12,0),(12,1),(12,2),(24,1),(48,1)) for L in (12,24)]

def update(state,**kw):
    d=dict(state=state,pid=os.getpid(),cpu=22,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(status);print(json.dumps(d),flush=True)

def inspect(directory,mesh,L,order):
    nodes,cells,faces=mesh;tree=ET.parse(directory/'solution.vtu')
    arrays={a.attrib['Name']:np.fromstring(a.text,sep=' ') for a in tree.findall('.//PointData/DataArray')}
    ids=arrays['mesh_node_id'].astype(int);u=dict(zip(map(int,ids),arrays['displacement'].reshape(-1,3)))
    xyz=np.fromstring(tree.find('.//Points/DataArray').text,sep=' ').reshape(-1,3)
    assert len(ids)==len(nodes) and set(ids)==set(nodes)
    assert max(np.max(abs(xyz[i]-nodes[int(n)])) for i,n in enumerate(ids))<1e-13
    assert all(np.all(np.isfinite(v)) for v in u.values())
    for tag,face in faces:
        if tag in (11,12):assert max(np.linalg.norm(u[n]) for n in face)<1e-12
    wall={n for tag,face in faces if tag==13 for n in face}
    ring=sorted((n for n in wall if abs(nodes[n][0]-L/2)<1e-12),key=lambda n:math.atan2(nodes[n][2],nodes[n][1]))
    assert len(ring)>=12
    g,w=np.polynomial.legendre.leggauss(order);g=(g+1)/2;w=w/2
    integral=length=0.
    for a,b in zip(ring,ring[1:]+ring[:1]):
        x=np.array([nodes[a],nodes[b]]);v=np.array([u[a],u[b]]);ds=np.linalg.norm(x[1]-x[0]);length+=ds
        q=(1-g[:,None])*x[0]+g[:,None]*x[1];vq=(1-g[:,None])*v[0]+g[:,None]*v[1]
        radial=q[:,1:]/np.linalg.norm(q[:,1:],axis=1)[:,None]
        integral+=ds*np.sum(w*np.sum(vq[:,1:]*radial,axis=1))
    energy=float(re.search(r'\bstrain_energy=([^\s]+)',(directory/'solve.log').read_text())[1]);workload=0.
    for tag,face in faces:
        if tag!=13:continue
        x=np.array([nodes[n] for n in face]);av=np.cross(x[1]-x[0],x[2]-x[0])/2
        if av@x.mean(axis=0)<0:av=-av
        workload+=.5*.02*(av@np.mean([u[n] for n in face],axis=0))
    assert abs(energy-workload)<1e-10*abs(energy)
    assert all(tube.determinant(nodes,c)>0 for c in cells)
    return dict(nodes=len(nodes),tets=len(cells),mid_ring_nodes=len(ring),mid_radial=integral/length,
        lame_scale=scale,relative_mid_error=abs(integral/length-scale)/scale,
        maximum_mid_axial=max(abs(u[n][0]) for n in ring),energy=energy,pressure_half_work=workload,
        energy_work_relative=abs(energy-workload)/abs(energy),quadrature_order=order)

try:
    assert not out.exists() and not status.exists()
    with (work/'lame-static-queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Let the earlier archive compression finish on this core as well.
        update('waiting_for_completed_capture')
        deadline=time.monotonic()+1800
        while not (root/'docs/research/data/pressure-tube-time-2026-11-08/archives.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Archive completion receipt not available')
            time.sleep(2)
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                args=(p/'cmdline').read_bytes().split(b'\0')
                if args and Path(os.fsdecode(args[0])).name in ('eonsim','svFSI'):assert 22 not in os.sched_getaffinity(int(p.name))
            except (FileNotFoundError,ProcessLookupError):pass
        assert shutil.disk_usage('/mnt/c').free>8*1024**3
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        assert int(mem['MemAvailable'].split()[0])>6*1024**2
        os.sched_setaffinity(0,{22});out.mkdir();shutil.copy2(work/'eonsim-b072cc8',out/'eonsim')
        env=os.environ.copy()
        for k in list(env):
            if k in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH') or k.startswith(('OMPI_','PMIX_','PRTE_')):env.pop(k)
        env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
            OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR=tempfile.mkdtemp(prefix='eonsim-clamped-'))
        hashes={}
        for p in (Path(__file__),root/'scripts/study_rigid_tube.py',root/'cases/fsi/generate_tube.py'):
            dst=out/'source'/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst);hashes[str(p.relative_to(root))]=sha(dst)
        (out/'definition.json').write_text(json.dumps(dict(source_head='6093f01',sources=hashes,binary_sha256=sha(out/'eonsim'),
            planned=planned,young=1000,poisson=.3,pressure=.02,radius=1,outer=1.2,
            scope='Static full annulus, all-component clamped ends. Compare L12/L24 at identical axial mesh size and cross-section. Not a coupled dynamic qualification or circular exact polygon solution.',
            quadrature_limit=1e-9),indent=2)+'\n')
        reports={}
        for sectors,level,L in planned:
            name=f's{sectors}-l{level}-length{L}';directory=out/name;directory.mkdir()
            tube.generate(directory/'base',sectors=sectors,axial=L,radial=2,radius=1,thickness=.2,length=L)
            mesh=tube.read_mesh(directory/'base/solid.msh')
            for _ in range(level):mesh=tube.refine(*mesh)
            tube.write_mesh(directory/'solid.msh',*mesh,region=20)
            if sectors==12 and L==12 and level in (0,1):
                original=work/f'elastic-s12-l{level}-n200-ramp16-c32/solid.msh'
                # Read-equivalence permits harmless decimal serialization differences.
                assert tube.read_mesh(original)==mesh
                (directory/'matching-coupled-mesh.json').write_text(json.dumps(dict(original=str(original),sha256=sha(original),parsed_mesh_identical=True),indent=2)+'\n')
            cfg=dict(mesh='solid.msh',output='solution.vtu',solid=dict(mode='static',material='linear',young=1000,poisson=.3,density=1,
                boundaries=[dict(tag=t,type='displacement',value=[0,0,0]) for t in (11,12)]+[
                    dict(tag=13,type='pressure',value=.02),dict(tag=14,type='pressure',value=0)]),
                solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-13,maximum_iterations=30))
            (directory/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
            command=[str(out/'eonsim'),'-case','case.json','-solver_report'];update('running',job=name,command=command)
            (directory/'command.json').write_text(json.dumps(dict(command=command,cwd=str(directory),cpu=22),indent=2)+'\n')
            start=time.perf_counter()
            with (directory/'solve.log').open('x') as log:subprocess.run(command,cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
            elapsed=time.perf_counter()-start;log=(directory/'solve.log').read_text();assert 'status=success' in log
            stats=dict(re.findall(r'(\w+)=([^\s]+)',next(s for s in log.splitlines() if s.startswith('solver_report '))))
            assert int(stats['snes_reason'])>0 and int(stats['ksp_reason'])>0
            low=inspect(directory,mesh,L,6);high=inspect(directory,mesh,L,8)
            qdiff=abs(low['mid_radial']-high['mid_radial'])/scale;assert qdiff<1e-9
            reports[name]=dict(**high,quadrature_change=qdiff,solver_report=stats,wall_seconds=elapsed)
            (out/'summary.json').write_text(json.dumps(reports,indent=2)+'\n')
        pairs={f's{s}-l{l}':abs(reports[f's{s}-l{l}-length12']['mid_radial']-reports[f's{s}-l{l}-length24']['mid_radial'])/scale for s,l in ((12,0),(12,1),(12,2),(24,1),(48,1))}
        (out/'length-differences.json').write_text(json.dumps(dict(relative_mid_radial_changes=pairs,
            interpretation='Pairwise static observation at matched local mesh sizes; not a dynamic finite-end bound or subtraction of spatial and geometry norms'),indent=2)+'\n')
        update('completed',work=str(out),studies=len(reports),length_differences=pairs)
except Exception as error:update('failed',error=str(error));raise
