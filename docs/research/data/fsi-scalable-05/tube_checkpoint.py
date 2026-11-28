"""Identity and clock of an accepted, rank-matched generalized-alpha/RCR checkpoint."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from paired_tube import digest


def checkpoint_arrays(path, required):
    """Use the HDF5 tools shipped alongside the solver; preserve integer signatures and raw FP64."""
    import numpy as np
    header=subprocess.check_output(['h5dump','-H','-x','-X',':',str(path)])
    elements=ET.fromstring(header).findall('./RootGroup/Dataset')
    if sorted(e.get('Name') for e in elements)!=sorted(required):
        raise ValueError(f'Incomplete generalized-alpha/RCR datasets in {path}')
    # Explicit dataset order binds binary slices to the header, including empty owner vectors.
    fields=[]
    options=[]
    for element in elements:
        name=element.attrib['Name']
        space=element.find('./Dataspace/SimpleDataspace')
        typ='IntegerType' if name=='metadata' else 'FloatType'
        kind=element.find('./DataType/AtomicType/'+typ)
        if (space is None or space.get('Ndims')!='1' or len(space.findall('Dimension'))!=1
                or kind is None or kind.get('Size')!='8' or (typ=='IntegerType' and kind.get('Sign')!='false')):
            raise ValueError(f'Invalid native checkpoint type or dimensions: {path} {name}')
        fields.append((name,int(space.find('Dimension').attrib['DimSize']),'<u8' if name=='metadata' else '<f8'))
        options+=['-d',name]
    with tempfile.TemporaryDirectory() as tmp:
        raw=Path(tmp)/'state.bin'
        subprocess.run(['h5dump','-O',os.devnull,'-b','LE','-o',str(raw),*options,str(path)],check=True)
        data=raw.read_bytes()
    if len(data)!=8*sum(n for _,n,_ in fields):
        raise ValueError(f'Incomplete native checkpoint data in {path}')
    values={}
    offset=0
    for name,n,dtype in fields:
        values[name]=np.frombuffer(data,dtype=dtype,count=n,offset=offset)
        if not np.isfinite(values[name]).all():
            raise ValueError(f'Nonfinite native checkpoint in {path} {name}')
        offset+=8*n
    return values


def checkpoint_receipt(directory, step, ranks):
    pointer=(directory/'current').read_text().split()
    if len(pointer)!=2 or pointer[0]!='EONSim_checkpoint_v3' or not re.fullmatch(r'generation_\d+',pointer[1]):
        raise ValueError('Unpublished or malformed checkpoint generation')
    generation=directory/pointer[1]
    meta=(generation/'manifest').read_text().split()
    if (len(meta)!=5 or meta[0]!=pointer[0] or int(meta[1])!=ranks or int(meta[2])!=step
            or float(meta[3])!=step/32 or float(meta[4])!=1/32):
        raise ValueError('Unexpected checkpoint rank count or absolute clock')
    required={'metadata','clock','reduced','physical','solid_displacement','rigid','rcr_capacitor',
              'time_metadata','fluid_rate','mesh_velocity','mesh_acceleration','solid_acceleration'}
    hashes={}
    for rank in range(ranks):
        path=generation/f'state_rank{rank}.h5'
        f=checkpoint_arrays(path,required)
        m=f['metadata']
        if (m.shape!=(9,) or tuple(m[:3])!=(3,rank,ranks) or int(m[-1])!=step
                or tuple(f['clock'])!=(step/32,1/32)
                or f['rcr_capacitor'].shape!=(3,) or f['rigid'].shape!=(2,)
                or f['time_metadata'].shape!=(2,) or f['time_metadata'][0]!=1
                or any(f[k].shape!=f['solid_displacement'].shape for k in
                       ('fluid_rate','mesh_velocity','mesh_acceleration','solid_acceleration'))):
            raise ValueError(f'Inconsistent checkpoint clock/history at rank {rank}')
        hashes[path.name]=digest(path)
    return dict(generation=pointer[1],ranks=ranks,step=step,time=step/32,next_dt=1/32,
                manifest_sha256=digest(generation/'manifest'),rank_files=hashes)

def verified_prefix(folder, current, output_folder, pair=None):
    """Recheck the exact predecessor chain and return the pinned generation, not its mutable current pointer."""
    import json
    from tube_protocol import audit_corrections, output_manifest
    def read(d):
        return json.loads((d/'window.json').read_text())
    prev=read(folder)
    if prev['steps']>=current['steps'] or prev['steps']%4:
        raise ValueError('Restart must advance beyond a complete saved phase')
    lineage=list(prev.get('prefix_segments',[]))
    lineage.append(dict(directory=str(folder),window_sha256=digest(folder/'window.json'),
                        start_step=prev.get('start_step',0),end_step=prev['steps'],T_job=prev['T_job']))
    end=0
    generation=None
    prior_sha=None
    for item in lineage:
        d=Path(item['directory'])
        record=read(d)
        start=record.get('start_step',0)
        if (digest(d/'window.json')!=item['window_sha256'] or start!=end or record['steps']!=item['end_step']
                or item['start_step']!=start or record['T_job']!=item['T_job']
                or any(record[k]!=current[k] for k in ('case','binary','compiled_source','partition','profile','ranks','preconditioner','policy'))
                or record['accepted_steps']!=list(range(start+1,record['steps']+1))
                or record['qualification'] not in ('awaiting_independent_crosscheck','independent_pair_passed')):
            raise ValueError('Changed or discontinuous prefix segment')
        if any(digest(d/n)!=sha for n,sha in record['inputs'].items()):
            raise ValueError('Restart prefix inputs changed')
        cfg=json.loads((d/'case.json').read_text())
        target=json.loads((output_folder/'case.json').read_text())
        cfg['fsi'].update(steps=target['fsi']['steps'],checkpoint_interval=target['fsi']['checkpoint_interval'])
        if cfg!=target or any(record['inputs'][n]!=current['inputs'][n] for n in ('fluid.msh','solid.msh')):
            raise ValueError('Changed physics or mesh across checkpoint')
        command=record['command']
        if start:
            if (record['prefix_receipt']!=prior_sha or record['restart_generation']!=str(generation)
                    or command[command.index('-restart')+1]!=str(generation)):
                raise ValueError('Prefix solver did not read its preceding verified generation')
        elif '-restart' in command:
            raise ValueError('First segment lacks a cold initial state')
        audit_corrections(d,record['steps'],record['ranks'],current['policy'],start)
        if output_manifest(d,record['steps'],record['ranks'],start)!=record['outputs']:
            raise ValueError('Previously accepted prefix fields/history changed')
        end=record['steps']
        checkpoint=checkpoint_receipt(d/'checkpoint',end,record['ranks'])
        if checkpoint!=record.get('checkpoint'):
            raise ValueError('Changed or missing native checkpoint')
        generation=d/'checkpoint'/checkpoint['generation']
        prior_sha=item['window_sha256']
    if prev['profile']=='lu':
        if pair is None:
            raise ValueError('A direct prefix needs its independently qualified iterative partner')
        partner=read(pair)
        if (partner['qualification']!='independent_pair_passed' or partner['profile']=='lu'
                or partner['reference_receipt']!=digest(folder/'window.json')
                or partner['reference_outputs']!=prev['outputs'] or partner['steps']!=end
                or partner['log_sha256']!=digest(pair/'solve.log')
                or partner['outputs']!=output_manifest(pair,end,partner['ranks'],partner.get('start_step',0))):
            raise ValueError('Direct prefix lacks a matching independent trajectory')
    elif prev['qualification']!='independent_pair_passed' or pair is not None:
        raise ValueError('Iteration must continue its independently qualified prefix')
    return prev,lineage,generation

def last_two_cycles(folder, meshes, ranks, start_step, physical_state):
    """Evaluate the frozen 6th/7th-cycle harmonics and same-phase interface displacement."""
    import math
    from paired_tube import MATERIAL, PEAK
    from perfused_eon import periodic_modes
    from study_hydrostatic_fsi import recovered_state
    from tube_protocol import pressure_face_history, tube_stem
    import benchmark_fsi_assembly as assembly
    if start_step>160:
        raise ValueError('Both complete final cycles must be present in the terminal segment')
    stem=tube_stem(start_step)
    history=assembly.history(folder/(stem+'.csv'),224,1/32,start_step)
    ports=pressure_face_history(folder,history,[2],start_step)
    hist={r['step']:r for r in history}
    phases={r['step']:r for r in physical_state['trace']}
    interface={n for tag,tri in meshes[1][2] if tag==13 for n in tri}
    if not interface:
        raise ValueError('Missing solid interface nodes')
    saved={}
    largest=0.
    samples=[]
    for step in range(164,225,4):
        obs=phases[step]
        row=hist[step]
        outer=ports[step,2]['endpoint_mean_pressure']
        samples.append(dict(time=step/32,full_inlet=4*row['endpoint_inlet_flow'],
                            full_outlet=PEAK*obs['outlet'],full_wall_flux=4*row['endpoint_wall_flux'],
                            inlet_mean_pressure=outer+obs['dp'],outlet_mean_pressure=outer,
                            circuit_pressure=row['endpoint_rcr_pressure'],capacitor_pressure=row['endpoint_capacitor_pressure'],
                            area_strain=obs['area']))
        state=recovered_state(folder,f'{stem}_step{step}_solid',meshes[1],True,ranks)
        if step<=192:
            saved[step]={n:state[n].displacement for n in interface}
        else:
            largest=max(largest,max(math.dist(state[n].displacement,saved[step-32][n]) for n in interface))
    strain=MATERIAL.lame_area_strain(20)
    mode,change=periodic_modes(samples,1.,PEAK,20.,strain)
    scale=.01*(math.sqrt(1+strain)-1)
    change['interface_displacement_over_static_radius_change']=largest/scale
    if not all(math.isfinite(v) for v in change.values()):
        raise ValueError('Invalid intercycle observation')
    return dict(cycles_completed=7,steady=all(v<1e-3 for v in change.values()),limit=1e-3,
                normalized_change=change,last_cycle_phasor=mode,samples_per_cycle=8,
                interface_nodes=len(interface),displacement_max_m=largest,displacement_scale_m=scale)
