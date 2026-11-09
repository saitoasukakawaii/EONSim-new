"""Self-review the concrete mature FSI screen before any numerical work."""
import hashlib,importlib.util,json,os,shutil,time
from pathlib import Path
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
C=W/'fsi-retained-lu-mature-screen-b8d1c76';OUT=D/C.name
V=W/'fsi-lu-reuse-validation-9ccd73f';ROOT=Path(__file__).resolve().parents[2]
read=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (W/'fsi-retained-lu-mature-screen-current.json').exists() and not (C/'plan-review.json').exists()
assert not any((OUT/name).exists() for name in ('old-first','new-default','new-window32','new-window8','old-last','new-replay16'))
os.sched_setaffinity(0,{19});os.nice(19)
controller=C/'controller.py';spec=importlib.util.spec_from_file_location('screen',controller);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.validate_completion();definition=m.verify();assert definition['controller_sha256']==sha(controller)
assert definition['cpus']==[19] and definition['nice']==19 and definition['shared_cpu']
assert definition['lock']=='elastic-budget-analysis.lock'
assert [definition[k] for k in ('memory_max_bytes','swap_max_bytes','admission_bytes','running_floor_bytes')]==[2*1024**3,0,10*1024**3,8*1024**3]
assert definition['mode_timeout']==1800 and definition['comparison_timeout']==7200
assert [definition[k] for k in ('nodal_limit','history_limit','mass_limit','legacy_clock_limit','cost_ratio_limit')]==[2e-9,2e-9,1e-8,1e-12,.9]
expected=[['old-first','old',0,6200,6232],['new-default','new',0,6200,6232],['new-window32','new',32,6200,6232],
          ['new-window8','new',8,6200,6232],['old-last','old',0,6200,6232],['new-replay16','new',32,6216,6232]]
assert definition['modes']==expected
assert definition['expected_lu_counts']=={'old-first':32,'new-default':32,'new-window32':1,'new-window8':4,'old-last':32,'new-replay16':1}
for label,binary,window,start,end in expected:
    args=['/usr/bin/python3',str(C/'execution-guard.py'),str(OUT/('eonsim-'+binary)),'-case','case.json','-checkpoint',str(OUT/label/'checkpoint'),
          '-restart',str(OUT/label/'checkpoint'),'-stop_after',str(end),'-solver_report','-log_view',':profile.txt','-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2']
    if window:args+=['-fsi_lu_pc_reuse_window',str(window)]
    assert definition['planned_commands'][label]==args
original=read(m.OLD/'case.json');assert read(OUT/'case.json')==original
variant=m.case();variant['mesh']='fluid.msh';variant['fsi']['domains']['solid_mesh']='solid.msh';variant['fsi']['checkpoint_interval']=200
assert variant==original and original['fsi']['steps']==6400 and original['fsi']['output_interval']==1
assert original['fsi']['dt']==2*__import__('math').pi/200 and 6200*original['fsi']['dt']>original['fsi']['pressure_time']['ramp_time']
assert 'stabilization_tau' not in original['fsi'] and original['time']=={'scheme':'generalized_alpha','rho_infinity':.5}
assert sha(OUT/'eonsim-new')==sha(V/'eonsim-release')=='6993d7f29778524317de991af58af6287a3c9d813ba81337299f4089e0d611c9'
assert sha(OUT/'eonsim-old')=='2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12'
for name,h in read(V/'definition.json')['source_hashes'].items():assert sha(ROOT/name)==sha(V/'source'/name)==h
assert read(C/'scales.json')==read(C/'original-audit.json')['scales']
import h5py,numpy as np
seed=m.generation(OUT/'seed',6200);tokens=(seed/'manifest').read_text().split()
assert tokens[:3]==['EONSim_checkpoint_v3','1','6200']
with h5py.File(seed/'state_rank0.h5') as h:
    assert len(h)==11 and tuple(h['metadata'][...][:3])==(3,0,1) and int(h['metadata'][8])==6200
    assert all(np.all(np.isfinite(h[name][...])) for name in h)
    assert np.array_equal(h['clock'][...],np.array(list(map(float,tokens[3:]))))
    seed_info=dict(step=6200,datasets={name:list(h[name].shape) for name in h},sha256=sha(seed/'state_rank0.h5'))
result=dict(passed=True,decision='run_bounded_fsi_mature_lu_screen_only',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    reviewer_sha256=sha(Path(__file__)),definition_sha256=sha(C/'definition.json'),validation_completion_sha256=sha(V/'completion.json'),
    source_files_checked=len(read(V/'definition.json')['source_hashes']),seed=seed_info,
    field_pair_states=176,native_pair_states=144,native_datasets=1584,adopted=False,full_qualification=False,
    scope='Implementing-agent review of actual immutable plan. Only output frequency/path changes; existing full-load seed, physics, tolerances and actual clock contracts unchanged. All six numerical modes and every raw pair required, then separate review before any future adoption.')
shutil.copy2(__file__,C/'plan-reviewer.py');(C/'plan-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
