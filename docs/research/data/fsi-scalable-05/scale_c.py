"""Qualification, partition preparation and MPI binding checks for the C20 scaling diagnostic."""
import json
import os
import re


SOLVE_SECONDS = {32: 1800, 128: 1200}
PREPARE_SECONDS = 120


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
