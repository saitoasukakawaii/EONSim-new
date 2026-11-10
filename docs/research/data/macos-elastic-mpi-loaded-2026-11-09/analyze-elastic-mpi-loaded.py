"""Compare actual global fields across ranks and native history within the fixed partition."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,h5py
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from audit_pressure_tube import Domain,eonsim_frame
from fsi_field_cycles import series
w=ROOT/'build/recompute-20261109/elastic-mpi-loaded';serial=ROOT/'build/recompute-20261109/elastic-loaded-screen'
assert (w/'completion.json').exists(),'Numerical phases incomplete'
assert not (w/'report.json').exists(),'Refuse overwrite'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
used={}
def track(p):used[str(p.relative_to(ROOT))]=sha(p);return p
def maps(folder):
 out={}
 for p in folder.glob('generation_*/manifest'):
  m=track(p).read_text().split();assert m[:2]==['EONSim_checkpoint_v4','2'];step=int(m[2]);assert step not in out;out[step]=p.parent
 return out
definition=json.loads(track(w/'definition.json').read_text())
assert definition['inputs']=={name:sha(w/name) for name in definition['inputs']}
assert definition['partition_sha256']=={str(p.relative_to(w/'parts')):sha(p) for p in (w/'parts').rglob('*') if p.is_file()}
for name in ('eonsim','fluid.msh','solid.msh'):assert sha(w/name)==sha(serial/name)
base=maps(w/'loaded/checkpoint');replay=maps(w/'replay16/checkpoint')
assert set(base)==set(range(19201,19233)) and set(replay)==set(range(19217,19233))
maximum=0.;datasets=0
for step,path in replay.items():
 for rank in range(2):
  with h5py.File(track(base[step]/f'state_rank{rank}.h5')) as a,h5py.File(track(path/f'state_rank{rank}.h5')) as b:
   assert set(a)==set(b)
   for name in a:
    x,y=a[name][()],b[name][()];assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
    if name in ('metadata','clock','time_metadata'):assert np.array_equal(x,y),(step,rank,name)
    else:
     delta=float(np.max(np.abs(x-y),initial=0));maximum=max(maximum,delta);assert delta<2e-9,(step,rank,name,delta)
    datasets+=1
# Serial and distributed checkpoint layouts intentionally differ. Their v4 clocks must agree.
serialmap={int(p.read_text().split()[2]):p.parent for p in (serial/'direct-first/checkpoint').glob('generation_*/manifest')}
for step,path in base.items():
 with h5py.File(track(serialmap[step]/'state_rank0.h5')) as a:
  for rank in range(2):
   with h5py.File(track(path/f'state_rank{rank}.h5')) as b:
    for name in ('clock','time_metadata'):assert np.array_equal(a[name][()],b[name][()]),(step,rank,name)
compliance=(1+.3)*((1-2*.3)+1.2**2)/(1000*(1.2**2-1));ds=.01*compliance
scales=[dict(velocity=ds*12,pressure=.01,mesh_displacement=ds),dict(velocity=ds,displacement=ds)]
results={}
for label,leftdir,leftstart,rightdir,rightstart,count in [('serial_vs_mpi',serial/'direct-first',19200,w/'loaded',19200,32),('mpi_restart',w/'loaded',19200,w/'replay16',19216,16)]:
 node=0.;mass=0.;pairs=0
 for i,suffix in enumerate(('', '_solid')):
  domain=Domain(w/('solid.msh' if i else 'fluid.msh'))
  lp=track(leftdir/f'solution_restart{leftstart}{suffix}.pvd');rp=track(rightdir/f'solution_restart{rightstart}{suffix}.pvd')
  left=dict(series(lp));right=dict(series(rp));assert len(left)==32 and len(right)==count and right.keys()<=left.keys()
  for t,p in right.items():
   # Hash complete piece files too, while the reader checks global topology and ghost consistency.
   import xml.etree.ElementTree as ET
   for frame in (left[t],p):
    track(frame)
    for piece in ET.parse(frame).findall('.//Piece[@Source]'):track(frame.parent/piece.attrib['Source'])
   a=eonsim_frame(left[t],domain,bool(i));b=eonsim_frame(p,domain,bool(i))
   for field,scale in scales[i].items():
    d=max(abs(x-y) for n in a for x,y in zip(a[n][field],b[n][field]));node=max(node,d)
    m=domain.rms_difference(a,b,field)/scale;mass=max(mass,m)
    assert d<2e-9 and m<1e-8,(label,t,field,d,m)
   pairs+=1
 results[label]=dict(domain_frame_pairs=pairs,maximum_node_delta=node,maximum_relative_mass=mass)
report=dict(passed=True,definition=definition,comparisons=results,native_checkpoint_pairs=32,native_datasets=datasets,maximum_native_history_delta=maximum,clock_exact=True,analysis_sha256=sha(Path(__file__)),consumed_sha256=used,scope='Fully loaded short MPI/restart proof; no full physical or scaling qualification')
(w/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='consumed_sha256'},indent=2))
