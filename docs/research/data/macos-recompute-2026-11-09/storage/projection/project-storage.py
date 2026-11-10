from pathlib import Path
import json,shutil,time
b=Path(__file__).resolve().parent;rows=[]
names=[('alpha1-s96-l1-n800',800,'wom'),('alpha2-s96-l1-n400',400,'wom'),('alpha2-s96-l1-n800',800,'wom'),('alpha1-s96-l1-n800-tautime-n400',800,'wom'),('elastic-s24-l1-n400',400,'fsi'),('elastic-s24-l1-n800',800,'fsi'),('elastic-s24-l1-n800-length24',800,'fsi')]
ratio=.4839106751096929
for name,n,kind in names:
 w=b/name;files=[p for p in w.rglob('*') if p.is_file() and not p.is_symlink()];logical=sum(p.stat().st_size for p in files);allocated=sum(p.stat().st_blocks*512 for p in files)
 if kind=='wom':expected=(4*n+2)*3241128+200*1024**2;compressed=expected
 else:
  frame=w/'early'/f'solution_step{n}.vtu'
  paths=[frame,frame.with_name(frame.stem+'_boundary.vtu'),frame.with_name(frame.stem+'_solid.vtu'),frame.with_name(frame.stem+'_solid_boundary.vtu')]
  size=sum(p.stat().st_size for p in paths);vtk=(3*n+29)*size;native=33*(3110736 if 'length24' in name else 1583952)
  expected=vtk+native+20*1024**2;compressed=vtk*ratio+native+20*1024**2
 rows.append(dict(work=name,observed_logical_bytes=logical,observed_allocated_bytes=allocated,projected_final_logical_bytes=expected,projected_final_allocated_after_vtu_compression=round(compressed),remaining_allocated_change_estimate=round(compressed-allocated)))
free=shutil.disk_usage(b).free
r=dict(observed_unix=time.time(),free_bytes=free,disk_floor_bytes=20*1024**3,studies=rows,projected_free_after_these_studies=free-sum(x['remaining_allocated_change_estimate'] for x in rows),scope='Estimate only; current representative VTU sizes and measured coarse compression ratio; excludes future replacement reference jobs. Native HDF uncompressed; active files untouched.',next_action='After required audits and budgets complete, losslessly archive finished raw family with hash/readback verification before removing redundant materialized copies. Preserve inputs and designated restart states. Never drop phases or change numerical gates.')
(b/'storage-projection.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='studies'},indent=2))
