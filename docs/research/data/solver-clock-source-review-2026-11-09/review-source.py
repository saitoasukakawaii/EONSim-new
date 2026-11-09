"""Record targeted read-only source review and bind reused validation hashes.

Run from the repository root with Python. This collects no fresh numerical
test evidence, changes no producer, and cannot mark PROD-02 qualified.
"""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path

root=Path.cwd().resolve()
assert (root/'AGENTS.md').is_file() and (root/'.git').exists()
out=root/'docs/research/data/solver-clock-source-review-2026-11-09'
assert not (out/'review.json').exists()
git=['git','-c','safe.directory='+root.as_posix(),'-C',str(root)]
head=subprocess.check_output(git+['rev-parse','HEAD']).decode().strip()
assert head=='7ed5a5ddda43b7d3af4a51d35c3a054062f0ab54'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
groups={
 'lu-time-coefficient-refresh-2026-11-08':[
  'include/eonsim/nonlinear_system.hpp','src/algebra/nonlinear_system.cpp',
  'src/physics/fluid.cpp','tests/verify_lu_reuse.cpp','tests/verify_fluid_lu_reuse.py'],
 'checkpoint-clock-v4-2026-11-08':[
  'include/eonsim/time_step.hpp','include/eonsim/checkpoint.hpp','src/io/checkpoint.cpp',
  'tests/verify_checkpoint.cpp','tests/verify_time_integration.cpp',
  'src/physics/solid.cpp','src/physics/fsi.cpp','src/physics/ale.cpp',
  'src/physics/scalar2d.cpp','src/physics/scalar_p2.cpp']}
checks=[]
for archive,paths in groups.items():
 p=root/'docs/research/data'/archive/'source.json';expected=read(p)['hashes']
 for path in paths:
  value=sha(root/path)
  assert value==expected[path],(path,value,expected[path])
  checks.append(dict(path=path,sha256=value,validation_source=str(p.relative_to(root).as_posix()),
   validation_source_sha256=sha(p),exact_frozen_source_match=True))
anchors={
 'src/algebra/nonlinear_system.cpp':[
  'Move the retained owner into this attempt','int keep=!refresh_lu_preconditioner',
  'SNESSetLagPreconditioner','context.evaluate(x.get(),r.get(),nullptr,true)',
  'KSPSetPC(ksp,nullptr)'],
 'src/physics/fluid.cpp':['clock.restore(saved.step,saved.time,saved.next_dt,saved.time_correction)',
  'const bool refresh_lu=','last_lu_integration_dt=integration_dt;',
  'clock.time,clock.next_dt,clock.correction()'],
 'src/io/checkpoint.cpp':['state.time_correction','Inconsistent accepted checkpoint clock across ranks',
  'pointer_format!=format','clock_replay=approximate'],
 'include/eonsim/time_step.hpp':['double correction() const','time_correction_=saved_correction','const double increment=dt()-time_correction_']}
locations={}
for path,terms in anchors.items():
 lines=(root/path).read_text(encoding='utf-8').splitlines()
 locations[path]={term:[n for n,line in enumerate(lines,1) if term in line] for term in terms}
 assert all(locations[path].values())
result=dict(utc=datetime.now(timezone.utc).isoformat(),source_head=head,
 review_kind='Targeted executing-agent source review; not independent external review',
 scope=['Explicit retained-LU ownership, collective invalidation, current operator and final physical acceptance',
  'Effective integration-coefficient refresh and fresh restart execution cache',
  'Checkpoint v4 compensation, collective publication and explicit approximate v3 fallback'],
 exact_source_matches=checks,source_locations=locations,
 conclusions=[
  'No new runtime defect identified within this targeted scope.',
  'The default LU window remains zero; retained factors do not replace the current equation or its final physical residual check.',
  'Any-rank refresh, options/window change, expiry or solve failure invalidates the execution cache; effective integration time is tracked only after acceptance.',
  'Checkpoint v4 persists time correction. Legacy v3 cannot recover the missing correction and reports approximate clock replay.',
  'L2 state documentation still denied factor reuse unconditionally; corrected to distinguish the disabled default from the explicit validated fluid option.'],
 validation_reused=True,new_tests_run=[],new_builds_run=[],
 remaining=['Complete active physical studies and each required error budget',
  'Final review of the full delivery after all acceptance evidence exists'],
 full_project_qualification=False,push=False,pr=False,
 collector_sha256=sha(Path(__file__)))
out.mkdir(exist_ok=True)
(out/'review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
(out/'review-source.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(dict(source_head=head,matched_files=len(checks),runtime_changes=False,new_tests_run=0,report=str(out/'review.json'))))
