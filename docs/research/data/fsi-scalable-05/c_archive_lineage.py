"""Check the C members of an incremental archive using their original Linux paths and file hashes."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
import re


@dataclass
class Segment:
    descriptor: dict
    generation: str
    identity: dict


def option(command, name, required=True):
    if name not in command and not required:
        return None
    if command.count(name)!=1 or command.index(name)+1>=len(command):
        raise ValueError(f'Missing or repeated command option: {name}')
    return command[command.index(name)+1]


def file_hash(index, path):
    item=index.get(str(path),{})
    if item.get('bytes',0)<=0 or not re.fullmatch(r'[0-9a-f]{64}',item.get('sha256','')):
        raise ValueError(f'Missing indexed regular file: {path}')
    return item['sha256']


def verify_outputs(row,folder,index,start,end):
    stem=f'tube_restart{start}' if start else 'tube'
    ranks=row['ranks']
    def indexed(name):
        return file_hash(index,folder/name)
    result=dict(phase_hashes={},indices={},history={})
    for suffix in ('.csv','_pressure_faces.csv'):
        result['history'][stem+suffix]=indexed(stem+suffix)
    for region in ('','_solid'):
        pvd=stem+region+'.pvd'
        result['indices'][pvd]=indexed(pvd)
        for step in range(start+4,end+1,4):
            phase=f'{stem}_step{step}{region}'
            pvtu=phase+'.pvtu'
            result['indices'][pvtu]=indexed(pvtu)
            pieces=[indexed(f'{phase}_rank{i}.vtu') for i in range(ranks)]
            result['phase_hashes'][phase]=sha256(''.join(pieces).encode()).hexdigest()
            if step==end:
                final='tube'+region
                result['indices'][final+'.pvtu']=indexed(final+'.pvtu')
                if pieces!=[indexed(f'{final}_rank{i}.vtu') for i in range(ranks)]:
                    raise ValueError(f'Terminal distributed field differs from its last phase: {folder}/{final}')
    if result!=row['outputs']:
        raise ValueError(f'Incomplete or changed saved output hashes: {folder}')


def verify_checkpoint(row,folder,index,end):
    checkpoint=row['checkpoint']
    gen=checkpoint['generation']
    ranks=row['ranks']
    names={f'state_rank{i}.h5' for i in range(ranks)}
    if (not re.fullmatch(r'generation_[0-9]+',gen) or checkpoint['ranks']!=ranks
            or (checkpoint['step'],checkpoint['time'],checkpoint['next_dt'])!=(end,end/32,1/32)
            or set(checkpoint['rank_files'])!=names):
        raise ValueError(f'Invalid checkpoint layout or absolute clock: {folder}')
    ck=folder/'checkpoint'
    pointer=f'EONSim_checkpoint_v3 {gen}\n'.encode()
    manifest=f'EONSim_checkpoint_v3 {ranks} {end} {end/32:.17g} {1/32:.17g}\n'.encode()
    if (file_hash(index,ck/'current')!=sha256(pointer).hexdigest()
            or file_hash(index,ck/gen/'manifest')!=sha256(manifest).hexdigest()
            or checkpoint['manifest_sha256']!=sha256(manifest).hexdigest()
            or any(file_hash(index,ck/gen/n)!=h for n,h in checkpoint['rank_files'].items())):
        raise ValueError(f'Original checkpoint publication or rank state hashes changed: {folder}')
    return gen


def verify_prefix(row,start,prior,partner):
    lineage=[s.descriptor for s in prior]
    if row.get('prefix_segments',[])!=lineage or row.get('prefix_T_job',0)!=sum(s['T_job'] for s in lineage):
        raise ValueError('Incorrect prefix segment directory, extent, timing or receipt hash')
    restart=option(row['command'],'-restart',required=False)
    if not start:
        if prior or partner or any(v is not None for v in (
                restart,row.get('restart_generation'),row.get('prefix_receipt'),
                row.get('prefix_pair_directory'),row.get('prefix_pair_receipt'))):
            raise ValueError('Cold C member unexpectedly references a checkpoint')
        return
    if not prior or not partner:
        raise ValueError('Missing one of the prior independent trajectory members')
    own=prior[-1]
    other=partner[-1]
    if (own.descriptor['end_step']!=start or other.descriptor['end_step']!=start
            or row.get('prefix_receipt')!=own.descriptor['window_sha256']
            or restart!=own.generation or row.get('restart_generation')!=own.generation):
        raise ValueError('Command did not resume its own accepted checkpoint generation')
    if row['profile']=='lu':
        if (row.get('prefix_pair_receipt')!=other.descriptor['window_sha256']
                or row.get('prefix_pair_directory')!=other.descriptor['directory']):
            raise ValueError('Direct continuation lacks the previous independent iterative partner')
    elif row.get('prefix_pair_receipt') is not None or row.get('prefix_pair_directory') is not None:
        raise ValueError('Unexpected independent prefix override on the iterative trajectory')


def audit_archive_pair(entries,index,start,end,previous=None):
    """Return the two extended histories after checking this complete pair; pass the result to the next window."""
    profiles=('lu','fixed-1e-6')
    previous=previous or {p:[] for p in profiles}
    by_profile={entry['data']['profile']:entry for entry in entries}
    if len(entries)!=2 or set(by_profile)!=set(profiles) or set(previous)!=set(profiles):
        raise ValueError('Expected one complete direct/iterative C pair')
    segments={}
    for p,partner in zip(profiles,reversed(profiles)):
        entry=by_profile[p]
        row=entry['data']
        rel=PurePosixPath(entry['receipt'])
        folder=rel.parent
        if (rel.name!='window.json' or len(folder.parts)!=1 or row['case']!='C' or row['ranks']!=64
                or (row['start_step'],row['steps'],row['segment_steps'],row['covered_steps'])!=(start,end,end-start,end)):
            raise ValueError(f'Unexpected C trajectory extent or location: {rel}')
        ck_arg=PurePosixPath(option(row['command'],'-checkpoint'))
        directory=ck_arg.parent
        if (ck_arg.name!='checkpoint' or not directory.is_absolute() or directory.name!=folder.name
                or '..' in directory.parts or option(row['command'],'-case')!='case.json'):
            raise ValueError(f'Checkpoint command and archived run directory differ: {rel}')
        identity={k:row[k] for k in ('case','profile','ranks','policy','binary','compiled_source','partition',
                                     'archive_receipt','preconditioner')}
        identity['meshes']={k:row['inputs'][k] for k in ('fluid.msh','solid.msh')}
        identity['campaign_root']=str(directory.parent)
        if previous[p] and identity!=previous[p][-1].identity:
            raise ValueError(f'Changed solver, mesh, partition or campaign along {p} continuation')
        if (set(row['inputs'])!={'case.json','fluid.msh','solid.msh'}
                or any(file_hash(index,folder/n)!=sha for n,sha in row['inputs'].items())
                or file_hash(index,folder/'solve.log')!=row['log_sha256']):
            raise ValueError(f'Archived input/log hashes differ: {rel}')
        verify_prefix(row,start,previous[p],previous[partner])
        gen=verify_checkpoint(row,folder,index,end)
        verify_outputs(row,folder,index,start,end)
        descriptor=dict(directory=str(directory),window_sha256=file_hash(index,rel),start_step=start,
                        end_step=end,T_job=row['T_job'])
        segments[p]=Segment(descriptor,str(directory/'checkpoint'/gen),identity)
    fixed=by_profile['fixed-1e-6']['data']
    direct=segments['lu'].descriptor
    if (fixed.get('reference_directory')!=direct['directory'] or fixed['reference_receipt']!=direct['window_sha256']
            or fixed['reference_outputs']!=by_profile['lu']['data']['outputs']
            or fixed['qualification']!='independent_pair_passed'
            or by_profile['lu']['data']['qualification']!='awaiting_independent_crosscheck'):
        raise ValueError('Iterative member did not qualify against this exact direct run')
    return {p:[*previous[p],segments[p]] for p in profiles}
