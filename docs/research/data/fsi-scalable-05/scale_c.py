"""Qualification, partition preparation and MPI binding checks for the C20 scaling diagnostic."""
import json
import math
import os
import re
import sys


SOLVE_SECONDS = {32: 1800, 128: 1200}
PREPARE_SECONDS = 120
HYBRID_SECONDS = 1500


def hybrid_bindings(log, topology, ranks=64):
    """Match libgomp's actual team places to each MPI process's inherited core mask."""
    physical={}
    for line in topology.splitlines():
        if line and not line.startswith('#'):
            cpu,core,socket=map(int,line.split(','))
            physical[cpu]=(socket,core)
    by_rank={}
    for rank,cpus in re.findall(r'^fsi05_mpi_mask rank=(\d+) cpus=([0-9,-]+)$',log,re.M):
        mask=set()
        for item in cpus.split(','):
            bounds=[int(v) for v in item.split('-')]
            mask.update(range(bounds[0],bounds[-1]+1))
        if int(rank) in by_rank or len(mask)!=2:
            raise ValueError('MPI did not provide a unique two-core mask')
        by_rank[int(rank)]=mask
    teams={}
    for rank,worker,team,cpus in re.findall(
            r'^fsi05_omp rank=(\d+) worker=(\d+) team=(\d+) cpus=(\S+)\s*$',log,re.M):
        # Linked libraries can also form serial teams. Only actual two-worker
        # regions verify the threaded FSI layout on this SMT-disabled node.
        if team=='1':
            continue
        if team!='2' or worker not in ('0','1') or not cpus.isdecimal():
            raise ValueError('Unexpected OpenMP team or worker affinity')
        places=teams.setdefault(int(rank),{})
        if places.setdefault(int(worker),int(cpus))!=int(cpus):
            raise ValueError('An OpenMP worker changed its core')
    if set(by_rank)!=set(range(ranks)) or set(teams)!=set(by_rank):
        raise ValueError('Missing MPI process or actual OpenMP team')
    for rank,mask in by_rank.items():
        if set(teams[rank])!={0,1} or set(teams[rank].values())!=mask:
            raise ValueError('Workers did not cover their MPI rank core mask')
    cores={physical[cpu] for mask in by_rank.values() for cpu in mask}
    if len(cores)!=ranks*2:
        raise ValueError('Physical cores overlap across MPI ranks or OpenMP workers')
    return dict(ranks=ranks,threads_per_rank=2,unique_physical_cores=len(cores),
        worker_cpu_by_rank=teams,physical_core_by_cpu={cpu:physical[cpu] for mask in by_rank.values() for cpu in mask})


def reference_area_budget(fluid_mesh,interface_tag,ranks,physical_limit):
    """Independent undeformed Tri3 measure and a bound for summing positive face areas."""
    nodes,_,faces=fluid_mesh
    areas=[]
    for tag,ids in faces:
        if tag!=interface_tag:
            continue
        a,b,c=(nodes[i] for i in ids)
        u=[y-x for x,y in zip(a,b)]
        v=[y-x for x,y in zip(a,c)]
        cross=[u[(j+1)%3]*v[(j+2)%3]-u[(j+2)%3]*v[(j+1)%3] for j in range(3)]
        areas.append(.5*math.hypot(*cross))
    if not areas or any(not math.isfinite(x) or x<=0 for x in areas):
        raise ValueError('Invalid frozen interface triangulation')
    area=math.fsum(areas)
    # One local sum per owner, followed by an MPI sum. The count bounds
    # both serial sums even without a pairwise reduction. 32 covers the
    # coordinate differences, cross product and norm on these regular Tri3s.
    n=len(areas)+max(ranks)+32
    e=n*sys.float_info.epsilon
    limit=min(physical_limit,area*e/(1.-e))
    return dict(triangles=len(areas),area=area,absolute_limit=limit)


def verify_baseline(path, reference, row, source_pieces):
    from paired_tube import digest
    from tube_protocol import audit_corrections, output_manifest
    baseline = json.loads((path/'window.json').read_text())
    if (row['steps']!=20 or row['case']!='C' or row['formal'] or not row['profile'].startswith('fixed-')
            or baseline['qualification']!='independent_pair_passed' or baseline.get('start_step',0)!=0
            or baseline['ranks']!=64 or baseline.get('formal',False)
            or baseline['reference_receipt']!=digest(reference/'window.json')
            or baseline['partition']!=source_pieces or baseline['log_sha256']!=digest(path/'solve.log')
            or any(baseline[k]!=row[k] for k in ('case','steps','inputs','binary','compiled_source','policy','archive_receipt'))
            or baseline.get('preconditioner',{'pc':'physics'})!=row['preconditioner']):
        raise ValueError('Scaling requires the qualified matching cold-start C64 fixed/LU pair')
    audit_corrections(path,20,64,row['policy'])
    if baseline['outputs']!=output_manifest(path,20,64):
        raise ValueError('C64 baseline output changed')
    return dict(baseline_directory=str(path),reference_directory=str(reference),
                baseline_window=digest(path/'window.json'),reference_window=baseline['reference_receipt'],
                source_partition=source_pieces,baseline_seconds=baseline['T_job'])


def equal_core_reference(path, reference, row):
    from paired_tube import digest
    from tube_protocol import audit_corrections, output_manifest
    source=path/'window.json'
    pure=json.loads(source.read_text())
    log=path/'solve.log'
    if (pure['qualification']!='independent_pair_passed' or pure['ranks']!=128 or pure['allocated_cpus']!=128 or pure['formal']
            or pure['start_step']!=0 or pure['accepted_steps']!=list(range(1,21))
            or pure['reference_receipt']!=digest(reference/'window.json') or pure['log_sha256']!=digest(log)
            or any(pure[k]!=row[k] for k in ('case','steps','inputs','policy','binary','compiled_source','preconditioner'))
            or pure['thread_environment']!=dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
            or pure['rank_bindings']!=read_bindings(log.read_text(),128) or '-fsi_threads' in pure['command']):
        raise ValueError('Hybrid comparison needs the qualified 128-by-1 C20 run with actual single-core bindings')
    audit_corrections(path,20,128,row['policy'])
    if pure['outputs']!=output_manifest(path,20,128):
        raise ValueError('Pure-MPI comparator output changed')
    return dict(directory=str(path),receipt_sha256=digest(source),T_job=pure['T_job'],
        baseline_directory=pure['scaling']['baseline_directory'],cores=128,allocated_cpus=pure['allocated_cpus'])


def prepare_partition(out,binary,ranks,row):
    from paired_tube import digest, run
    prep, part = out/'prepare', out/'partition'
    prep.mkdir()
    for name in row['inputs']:
        os.link(out/name,prep/name)
    record=dict(job=row['job'],inputs=row['inputs'],binary=row['binary'],parts=ranks,
                wall_limit=PREPARE_SECONDS,rss_limit=row['rss_limit'])
    row['partition_preparation']=record
    run(prep,[str(binary),'-case','case.json','-prepare',str(part),'-parts',str(ranks)],
        record,PREPARE_SECONDS,row['rss_limit'])
    expected={'manifest.yaml',*(f'rank_{i}.h5' for i in range(ranks))}
    if {p.name for p in part.iterdir() if p.is_file()}!=expected:
        raise ValueError('Partition is missing its manifest or has incorrect rank shards')
    return part,{name:digest(part/name) for name in sorted(expected)}


def read_bindings(log,ranks):
    pattern=re.compile(r'MCW rank (\d+) bound to (?:socket|package) (\d+)\[core (\d+)\[hwt (\d+)\]\]')
    bindings={}
    for line in log.splitlines():
        if 'MCW rank' not in line:
            continue
        matches=pattern.findall(line)
        if len(matches)!=1 or line.count('[core ')!=1:
            raise ValueError('MPI rank did not report binding to a single core and hardware thread')
        rank,socket,core,hwt=map(int,matches[0])
        if rank in bindings:
            raise ValueError('Duplicate MPI rank binding')
        bindings[rank]=(socket,core,hwt)
    if set(bindings)!=set(range(ranks)) or len({v[:2] for v in bindings.values()})!=ranks:
        raise ValueError('Missing or oversubscribed MPI bindings in C20 diagnostic')
    return {str(k):list(v) for k,v in bindings.items()}
