"""Fresh FSI trajectory with terminal-segment byte-preserving output compression."""
from pathlib import Path
import argparse,hashlib,json,math,os,re,shutil,signal,stat,subprocess,sys,time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'cases/fsi'));from generate_pressure_tube import generate
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def compress(folder):
 rows=[]
 for p in sorted(folder.glob('*.vtu')):
  assert not p.is_symlink();before=p.stat()
  if before.st_flags&stat.UF_COMPRESSED:continue
  digest=sha(p);q=p.with_name(p.name+'.compress-pending');assert not q.exists()
  subprocess.run(['ditto','--hfsCompression',str(p),str(q)],check=True)
  assert q.stat().st_size==before.st_size and sha(q)==digest and sha(p)==digest
  assert (p.stat().st_size,p.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns)
  if q.stat().st_blocks<before.st_blocks:os.replace(q,p);assert sha(p)==digest
  else:q.unlink()
  rows.append(dict(path=p.name,sha256=digest,logical_bytes=before.st_size,allocated_before=before.st_blocks*512,allocated_after=p.stat().st_blocks*512))
 dump(folder/'compression.json',dict(files=rows,saved_allocated_bytes=sum(r['allocated_before']-r['allocated_after'] for r in rows),logical_content_unchanged=True))

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--probe',action='store_true');a=p.parse_args();w=a.work.resolve();assert not w.exists()
 binary=ROOT/'build/macos-release/eonsim';assert sha(binary)=='04a7aa5b0b6d22e408efc6cace75d4b11a483a595ecfd222c8f4fe8d49282873'
 if not a.probe:
  proof=ROOT/'build/recompute-20261109/elastic-segment-probe/comparison.json'
  check=json.loads(proof.read_text());assert check['passed'] and check['maximum_all_field_difference']<2e-9 and check['maximum_applied_pressure']>.01
  assert sha(proof.parent/'eonsim')==sha(binary)
  assert shutil.disk_usage(ROOT).free>38*1024**3,'Need38GiB before bounded compressed fine output'
 case=generate(w,sectors=8 if a.probe else 24,radial=1 if a.probe else 2,axial=2 if a.probe else 12,length=2 if a.probe else 12,level=0 if a.probe else 1,steps_per_cycle=1600,cycles=32)
 cfg=json.loads(case.read_text());cfg['fsi']['pressure_time']['ramp_time']=16*2*math.pi
 n=1600;early=29*n;end=32*n;chunk=256;cadence=n
 if a.probe:
  cfg['fsi'].update(dt=.02,steps=16,checkpoint_interval=4);cfg['fsi']['pressure_time'].update(amplitude=.05,period=.4,ramp_time=.04);early=4;end=16;chunk=4;cadence=1
 dump(case,cfg);shutil.copy2(binary,w/'eonsim')
 options=['-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32']
 definition=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),binary_sha256=sha(binary),controller_sha256=sha(Path(__file__)),inputs={s:sha(w/s) for s in ['case.json','fluid.msh','solid.msh','geometry.json']},probe=a.probe,steps_per_cycle=n,cycles=32,level=1,ranks=1,threads=1,dense_segment_steps=chunk,solver_options=options,disk_floor_bytes=20*1024**3,memory_rss_limit_bytes=3*1024**3,scope='All physical steps retained; restart every bounded dense output segment, compress terminal VTU bytes only; no field deletion or sampling reduction.')
 if not a.probe:definition['loaded_segment_probe_sha256']=sha(proof)
 dump(w/'definition.json',definition);env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
 stages=[('early',early,cadence)]+[(f'dense-{i:03}',min(target,end),1) for i,target in enumerate(range(early+chunk,end+chunk,chunk),1)]
 previous=0;receipts=[];all_steps=[]
 try:
  for label,target,interval in stages:
   folder=w/label;folder.mkdir();local=json.loads(json.dumps(cfg));local['mesh']='../fluid.msh';local['fsi']['domains']['solid_mesh']='../solid.msh';local['fsi']['output_interval']=interval;dump(folder/'case.json',local)
   cmd=[str(w/'eonsim'),'-case','case.json','-checkpoint',str(w/'checkpoint'),'-stop_after',str(target),*options]
   if previous:
    marker,generation=(w/'checkpoint/current').read_text().split();tokens=(w/'checkpoint'/generation/'manifest').read_text().split();assert marker==tokens[0]=='EONSim_checkpoint_v4' and int(tokens[2])==previous;cmd+=['-restart',str(w/'checkpoint'/generation)]
   dump(folder/'command.json',cmd);start=time.monotonic();peak=0
   with (folder/'solve.log').open('w') as log:
    process=subprocess.Popen(cmd,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);dump(w/'live.json',dict(pid=process.pid,label=label,target=target,start_unix=time.time()))
    try:
     while process.poll() is None:
      if time.monotonic()-start>86400:raise TimeoutError(label)
      rss=subprocess.run(['ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True)
      if rss.returncode==0 and rss.stdout.strip():peak=max(peak,int(rss.stdout)*1024)
      if peak>definition['memory_rss_limit_bytes']:raise MemoryError('RSS limit')
      if shutil.disk_usage(w).free<definition['disk_floor_bytes']:raise RuntimeError('Disk floor')
      time.sleep(.1 if a.probe else 2)
    except BaseException:
     if process.poll() is None:
      os.killpg(process.pid,signal.SIGTERM)
      try:process.wait(timeout=10)
      except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
     raise
   text=(folder/'solve.log').read_text();steps=list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)));assert process.returncode==0 and 'status=success' in text and steps==list(range(previous+1,target+1));all_steps+=steps
   row=dict(label=label,previous=previous,accepted_first=steps[0],accepted_last=steps[-1],exit_code=0,peak_rss_bytes=peak,seconds=time.monotonic()-start);dump(folder/'receipt.json',row);receipts.append(row)
   compress(folder);dump(w/'progress.json',receipts);previous=target
  assert all_steps==list(range(1,end+1))
  for suffix in ['','_solid']:
   root=ET.Element('VTKFile',type='Collection',version='0.1',byte_order='LittleEndian');collection=ET.SubElement(root,'Collection');times=[]
   for row in receipts:
    stem='solution' if row['previous']==0 else f"solution_restart{row['previous']}"
    for d in ET.parse(w/row['label']/(stem+suffix+'.pvd')).findall('.//DataSet'):
     v=dict(d.attrib);v['file']=row['label']+'/'+v['file'];assert (w/v['file']).exists();times.append(float(v['timestep']));ET.SubElement(collection,'DataSet',v)
   assert all(x<y for x,y in zip(times,times[1:]));assert len(times)==end if a.probe else len(times)==29+3*n
   ET.ElementTree(root).write(w/('solution'+suffix+'.pvd'),encoding='utf-8',xml_declaration=True)
  dump(w/'completion.json',dict(accepted_steps=end,receipts=receipts,probe=a.probe,scope='Trajectory complete; physical audit and original error budget still required'))
 except BaseException as e:dump(w/'failure.json',dict(error=repr(e),receipts=receipts));raise
 print((w/'completion.json').read_text())
if __name__=='__main__':main()
