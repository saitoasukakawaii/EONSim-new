"""Identity and clock of an accepted, rank-matched generalized-alpha/RCR checkpoint."""
from pathlib import Path
import re

from paired_tube import digest


def checkpoint_receipt(directory, step, ranks):
    import h5py
    import numpy as np
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
        with h5py.File(path,'r') as f:
            if set(f)!=required:
                raise ValueError(f'Incomplete generalized-alpha/RCR state for rank {rank}')
            m=f['metadata'][...]
            if (m.shape!=(9,) or tuple(m[:3])!=(3,rank,ranks) or int(m[-1])!=step
                    or tuple(f['clock'][...])!=(step/32,1/32)
                    or f['rcr_capacitor'].shape!=(3,) or f['rigid'].shape!=(2,)
                    or f['time_metadata'].shape!=(2,) or f['time_metadata'][0]!=1):
                raise ValueError(f'Inconsistent checkpoint clock/history at rank {rank}')
            if any(dataset.ndim!=1 or not np.isfinite(dataset[...]).all() for dataset in f.values()):
                raise ValueError(f'Nonfinite or invalid native checkpoint values on rank {rank}')
        hashes[path.name]=digest(path)
    return dict(generation=pointer[1],ranks=ranks,step=step,time=step/32,next_dt=1/32,
                manifest_sha256=digest(generation/'manifest'),rank_files=hashes)
