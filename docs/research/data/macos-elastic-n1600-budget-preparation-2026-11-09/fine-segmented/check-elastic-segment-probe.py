from pathlib import Path
import json,os,subprocess,sys,hashlib
r=Path.cwd();sys.path.insert(0,str(r/'tests'));from verify_fsi_lu_reuse import frames,compare,rows
w=r/'build/recompute-20261109/elastic-segment-probe';assert json.loads((w/'completion.json').read_text())['accepted_steps']==16
full=w/'uninterrupted';full.mkdir();cfg=json.loads((w/'case.json').read_text());cfg['mesh']=str(w/'fluid.msh');cfg['fsi']['domains']['solid_mesh']=str(w/'solid.msh');cfg['fsi']['output_interval']=1;cfg['output']='solution.vtu';(full/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
cmd=[str(w/'eonsim'),'-case','case.json','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32'];env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
with (full/'solve.log').open('w') as log:result=subprocess.run(cmd,cwd=full,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert result.returncode==0
seg=frames(w);continuous=frames(full);difference=compare(seg,continuous)
history=rows((full/'solve.log').read_text(),'fsi_step=');pressure=max(float(x['applied_pressure']) for x in history);assert pressure>.01
files=0
for row in json.loads((w/'completion.json').read_text())['receipts']:
 folder=w/row['label']
 for entry in json.loads((folder/'compression.json').read_text())['files']:
  assert hashlib.sha256((folder/entry['path']).read_bytes()).hexdigest()==entry['sha256'];files+=1
proof=dict(passed=True,maximum_all_field_difference=difference,maximum_applied_pressure=pressure,steps=16,segments=4,all_fluid_solid_phases=len(seg),compressed_attempt_files_rehashed=files,command=cmd,scope='Actual loaded generalized-alpha run with LU reuse: segmented/restarted/compressed fields versus uninterrupted run; original tolerance2e-9.')
(w/'comparison.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
