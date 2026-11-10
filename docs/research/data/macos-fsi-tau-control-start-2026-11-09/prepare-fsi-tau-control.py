from pathlib import Path
import json,math,hashlib,subprocess,os,shutil
root=Path.cwd();base=root/'build/recompute-20261109';work=base/'elastic-tau-time-preparation';assert not work.exists();work.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=base/'elastic-s24-l1-n800';cfg=json.loads((source/'case.json').read_text());assert cfg['time']==dict(scheme='generalized_alpha',rho_infinity=.5)
# First-order fluid alpha_m=5/6, alpha_f=2/3, gamma=2/3: effective_dt=8/15*h.
rho=.5;am=(3-rho)/(2*(1+rho));af=1/(1+rho);gamma=.5+am-af;scale=af*gamma*(2*math.pi/400)/am
assert abs(scale-(8/15)*(2*math.pi/400))<1e-16
cfg['fsi']['stabilization_time_scale']=scale
for name in ['fluid.msh','solid.msh','geometry.json']:shutil.copy2(source/name,work/name)
(work/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
binary=root/'build/macos-fsi-tau-diagnostic/eonsim';assert sha(binary)=='47ed3b523bdfd68105cbf50fb2e626da73943c52765e1f7003a15edf6a2bfa06'
probe=work/'probe';probe.mkdir();pcfg=json.loads(json.dumps(cfg));pcfg['mesh']='../fluid.msh';pcfg['fsi']['domains']['solid_mesh']='../solid.msh';pcfg['fsi']['output_interval']=1
(probe/'case.json').write_text(json.dumps(pcfg,indent=2)+'\n')
cmd=[str(binary),'-case','case.json','-stop_after','8','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2','-fsi_lu_pc_reuse_window','32']
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');env.pop('PETSC_OPTIONS',None)
with (probe/'solve.log').open('w') as log:r=subprocess.run(cmd,cwd=probe,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
text=(probe/'solve.log').read_text();assert r.returncode==0 and 'status=success' in text
import re
steps=list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)));assert steps==list(range(1,9))
record=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),binary_sha256=sha(binary),source_definition_sha256=sha(source/'definition.json'),inputs={n:sha(work/n) for n in ['case.json','fluid.msh','solid.msh','geometry.json']},tau_time_scale=scale,formula='fluid alpha_f*gamma/alpha_m * (2*pi/400) = (8/15)*(2*pi/400)',startup_scope='Same fixed scale also applies during initial BE step; not claiming exact matching of N400 startup tau.',command=cmd,probe_steps=steps,probe_exit_code=r.returncode,probe_log_sha256=sha(probe/'solve.log'))
(work/'preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
