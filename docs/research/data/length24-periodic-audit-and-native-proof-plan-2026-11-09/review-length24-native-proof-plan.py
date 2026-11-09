"""Executing-agent plan review only, before any L24 proof numerical command."""
import ast, hashlib, json, os, time
from pathlib import Path
import h5py
import numpy as np

os.sched_setaffinity(0,{14}); os.nice(19)
w=Path('/home/tfblab633/EONSim-prod48-20261107')
d=Path('/mnt/d/EONSim-prod48-20261107')
c=w/'length24-native-extension-proof-4f5f26d'; out=d/c.name
read=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

assert not (w/'length24-native-extension-proof-current.json').exists()
assert not (c/'plan-review.json').exists() and not (c/'replay200.log').exists()
definition=read(c/'definition.json'); ast.parse((c/'controller.py').read_text())
assert sha(c/'controller.py')==definition['controller_sha256']=='1e150dd1bf8df239d6f5de9d7de53bc62ed07abbd2481d2fb49cbd80aee5c062'
assert definition['cpus']==[14] and definition['shared_cpu'] and definition['nice']==19
assert [definition[k] for k in ('memory_max_bytes','swap_max_bytes','admission_bytes','running_floor_bytes')]==[2*1024**3,0,10*1024**3,8*1024**3]
assert definition['timeouts']=={'replay200':7200,'replay10':1200,'comparison':7200}
assert definition['original_native_boundary_pairs']==1 and definition['replay_native_pairs']==10 and definition['field_pairs']==210
assert [definition[k] for k in ('nodal_limit','history_limit','normalized_mass_limit','legacy_clock_limit')]==[2e-9,2e-9,1e-8,1e-12]
assert not definition['adopted']
assert sha(c/'bounded_cgroup_job_2g.py')==definition['cap_sha256']=='5070df17d8c299ea4bc393971e69fcc77f09821c1d0b895df6074c7a9997a939'
assert sha(c/'execution-guard.py')==definition['guard_sha256']=='5fe97dffd47ecca76da8ff183cd2ddb309d1e06d32210d71ab2d90977434e036'
for n,h in definition['source_hashes'].items():assert sha(c/'source'/n)==h
for n,h in definition['input_hashes'].items():assert sha(out/n)==h
assert sha(out/'eonsim')=='2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12'
base=read(out/'case.json'); actual=read(out/'replay200/case.json')
assert actual['fsi']['steps']==7200 and actual['fsi']['checkpoint_interval']==1 and actual['fsi']['output_interval']==1
actual['fsi']['steps']=6400;actual['fsi']['checkpoint_interval']=200
actual['mesh']='fluid.msh';actual['fsi']['domains']['solid_mesh']='solid.msh'
assert actual==base
for label in ('replay200','replay10'):
    target=out/label/'checkpoint'
    expect=['/usr/bin/python3',str(c/'execution-guard.py'),str(out/'eonsim'),'-case','case.json',
        '-checkpoint',str(target),'-restart',str(target),'-stop_after','6400','-solver_report','-log_view',':profile.txt',
        '-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2']
    assert definition['planned_commands'][label]==expect
native=[]
for step in (6200,6400):
    generations=list((out/f'original{step}').glob('*/manifest'));assert len(generations)==1
    p=generations[0]; assert int(p.read_text().split()[2])==step
    for n,h in definition['seed_hashes'][str(step)].items():assert sha(p.parent/n)==h
    with h5py.File(p.parent/'state_rank0.h5') as f:
        assert len(f)==11 and int(f['metadata'][()][8])==step and int(f['metadata'][()][2])==1
        assert all(np.all(np.isfinite(f[name][()])) for name in f)
        native.append(dict(step=step,datasets={name:list(f[name].shape) for name in f},clock=f['clock'][()].tolist()))
audit=read(c/'original-audit.json'); receipt=read(c/'original-audit-completion.json')['resource']
assert audit['periodic'] is False and audit['sampled_steps']==600
assert receipt['returncode']==0 and not receipt['remaining_scope_members'] and not receipt['cleanup']
assert all(int(line.split()[1])==0 for line in receipt['memory_events'].splitlines())
group=Path('/sys/fs/cgroup')/f'user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice'/receipt['unit']
assert not group.exists() or not (group/'cgroup.procs').read_text().strip()
for pid in (7713,42141):
    p=Path('/proc')/str(pid)/'stat'
    assert not p.exists() or p.read_text().rsplit(')',1)[1].split()[0] in ('Z','X')
assert sha(c/'immutable-inputs.json')==definition['immutable_manifest_sha256']
raw=read(c/'immutable-inputs.json')
for name,h in raw.items():assert sha(Path(name))==h
fields=read(c/'oracle-fields.json');assert len(fields)==2
assert all(set(one)=={str(i) for i in range(6201,6401)} for one in fields)
result=dict(passed=True,decision='run_bounded_l24_replay_proof_only',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    definition_sha256=sha(c/'definition.json'),reviewer_sha256=sha(Path(__file__)),
    immutable_files_reopened=len(raw),native_records=native,original_periodic=False,adopted=False,
    full_qualification=False,scope='Executing-agent review of concrete replay plan and original frozen inputs. No numerical proof yet; no long extension authorized by this result. Original c32 failure is retained. No external independent reviewer claim.')
(c/'plan-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result),flush=True)
