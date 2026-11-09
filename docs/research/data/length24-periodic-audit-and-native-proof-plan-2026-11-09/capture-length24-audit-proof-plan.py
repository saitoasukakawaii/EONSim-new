"""Seal completed L24 audit and immutable proof plan; exclude running proof outputs."""
import hashlib,json,shutil,time
from pathlib import Path
root=Path('/mnt/c/Users/tfblab633/Documents/ChatGPT/数值计算/EONSim-new-current')
w=Path('/home/tfblab633/EONSim-prod48-20261107');d=Path('/mnt/d/EONSim-prod48-20261107')
c=w/'length24-native-extension-proof-4f5f26d'
folder=root/'docs/research/data/length24-periodic-audit-and-native-proof-plan-2026-11-09'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
assert not folder.exists()
definition=read(c/'definition.json');review=read(c/'plan-review.json')
assert review['passed'] and review['definition_sha256']==sha(c/'definition.json')
assert review['decision']=='run_bounded_l24_replay_proof_only'
audit=read(c/'original-audit.json');assert not audit['periodic'] and audit['sampled_steps']==600
folder.mkdir();records={}
items={name:c/name for name in ('controller.py','definition.json','plan-review.json','immutable-inputs.json','oracle-fields.json',
    'original-audit.json','original-audit-completion.json','scales.json','execution-guard.py','bounded_cgroup_job_2g.py')}
items['proof-case.json']=d/c.name/'replay200/case.json'
items['original-case.json']=d/c.name/'case.json'
items['review-length24-native-proof-plan.py']=root/'build/prod48-20261107/review-length24-native-proof-plan.py'
items['capture-length24-audit-proof-plan.py']=Path(__file__)
for name,source in items.items():
    before=sha(source);shutil.copy2(source,folder/name);assert sha(folder/name)==before==sha(source)
    records[name]=dict(source=str(source),sha256=before,bytes=source.stat().st_size)
for name,h in definition['source_hashes'].items():
    src=c/'source'/name;dst=folder/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    assert sha(src)==h;shutil.copy2(src,dst);assert sha(dst)==h
    records['source/'+name]=dict(source=str(src),sha256=h,bytes=src.stat().st_size)
mean=audit['harmonics']['mid_radial_displacement']['mean']
exact=read(folder/'original-case.json')['fsi']['pressure']*audit['infinite_plane_strain_compliance']
summary=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),base=definition['base'],
    completed_original_steps=6400,full_sampled_states=600,periodic=False,
    solid_velocity_cycle31_max=audit['cycle_differences']['31']['solid_velocity']['relative_max'],
    solid_velocity_cycle32_max=audit['cycle_differences']['32']['solid_velocity']['relative_max'],periodic_limit=1e-5,
    quality_gates=audit['quality_gates'],minimum_solid_jacobian=audit['minimum_solid_jacobian'],
    minimum_fluid_jacobian=audit['minimum_fluid_jacobian'],mean_radial=mean,plane_strain_mean=exact,
    lame_relative_error=abs(mean-exact)/abs(exact),lame_limit=.02,lame_passed=abs(mean-exact)/abs(exact)<.02,
    proof_plan_ready=True,proof_completed=False,extended_production_adopted=False,full_qualification=False,
    files=records,scope='Complete original c32 audit and immutable reviewed proof plan only. Running replay logs, fields, checkpoints and resources are intentionally excluded and must be captured after actual completion. Original failed periodic gate remains unchanged. Raw original trajectories belong to the separate full L24 archive, not this small static package.')
(folder/'source.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(folder=str(folder),files=len(records)+1,periodic=False,lame_relative_error=summary['lame_relative_error'],extended_production_adopted=False)))
