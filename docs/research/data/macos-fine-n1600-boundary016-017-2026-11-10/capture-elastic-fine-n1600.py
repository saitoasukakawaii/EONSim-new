"""Capture complete fine N1600 audit and raw provenance, preserving failed physical gates."""
from pathlib import Path
import json,hashlib,shutil,gzip,re,math
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109';w=b/'elastic-s24-l1-n1600';e=root/'docs/research/data/macos-elastic-fine-n1600-2026-11-10'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
ap=b/(w.name+'-audit.json')
if not ap.is_file() or not (w/'completion.json').is_file():raise SystemExit('Incomplete N1600: final audit and completion receipt required; no capture created')
r=json.loads(ap.read_text());receipt=json.loads((w/'completion.json').read_text())
assert r['steps']==receipt['accepted_steps']==51200 and r['first_step']==46401 and r['sampled_steps']==4800
assert sha(w/'case.json')==r['case_sha256'] and sha(root/'scripts/audit_pressure_tube.py')==r['analysis_script_sha256']
assert all(row['exit_code']==0 for row in receipt['receipts'])
definition=json.loads((w/'definition.json').read_text())
assert definition['steps_per_cycle']==1600 and definition['cycles']==32 and definition['level']==1 and definition['ranks']==1 and not definition['probe']
for name,digest in definition['inputs'].items():assert sha(w/name)==digest
assert sha(w/'eonsim')==definition['binary_sha256']
expected=[('early',0,46400)]
previous=46400
for i,target in enumerate(range(46656,51200+256,256),1):
 target=min(target,51200);expected.append((f'dense-{i:03}',previous,target));previous=target
assert [(x['label'],x['previous'],x['accepted_last']) for x in receipt['receipts']]==expected
for label,previous,target in expected:
 row=json.loads((w/label/'receipt.json').read_text());assert row['exit_code']==0 and row['accepted_first']==previous+1 and row['accepted_last']==target
 text=(w/label/'solve.log').read_text();assert 'status=success' in text
 assert list(map(int,re.findall(r'^fsi_step=(\d+) ',text,re.M)))==list(range(previous+1,target+1))
assert not list(w.rglob('*.compress-pending')) and not list(w.rglob('*.compressed-pending'))
for name in ['solution.pvd','solution_solid.pvd']:
 entries=ET.parse(w/name).findall('.//DataSet');steps=[]
 for entry in entries:
  p=w/entry.attrib['file'];assert p.is_file() and not p.is_symlink()
  step=round(float(entry.attrib['timestep'])/(2*math.pi/1600));assert abs(float(entry.attrib['timestep'])-step*2*math.pi/1600)<1e-8
  steps.append(step)
 assert steps==list(range(1600,46401,1600))+list(range(46401,51201))
mean=r['harmonics']['mid_radial_displacement']['mean'];expected=r['infinite_plane_strain_compliance']*r['physical_definition']['pressure'];error=abs(mean-expected)/abs(expected)
worst=max(v['relative_max'] for cycle in r['cycle_differences'].values() for v in cycle.values())
assert r['periodic']==(worst<1e-5)
summary=dict(steps=51200,audited_first=46401,audited_last=51200,periodic=r['periodic'],maximum_cycle_relative_difference=worst,quality_gates=r['quality_gates'],minimum_solid_jacobian=r['minimum_solid_jacobian'],minimum_fluid_jacobian=r['minimum_fluid_jacobian'],lame=dict(mean=mean,expected=expected,relative_error=error,limit=.02,passed=error<.02),audit_sha256=sha(ap),qualification='Physical checks only; independent numerical budgets, geometry/end controls and matched reference still required. Any failed gate remains failed.')
summary['all_local_physical_checks_passed']=r['periodic'] and all(v['passed'] for v in r['quality_gates'].values()) and min(r['minimum_solid_jacobian'],r['minimum_fluid_jacobian'])>0 and error<.02
assert not e.exists();e.mkdir();files=[]
for p in sorted(w.rglob('*')):
 if p.is_file():
  assert not p.is_symlink();before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
# Include every archived boundary member in the final original-byte inventory.
import importlib.util
for verifier,proofname in [('verify-fine-n1600-boundary-prefix.py','boundary-archive-proof.json'),('verify-fine-n1600-boundary009-013.py','boundary009-013-archive-proof.json'),('verify-fine-n1600-boundary014-015.py','boundary014-015-archive-proof.json'),('verify-fine-n1600-boundary016-017.py','boundary016-017-archive-proof.json')]:
 vp=b/verifier;spec=importlib.util.spec_from_file_location('fine_boundary_prefix',vp);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 archive_proof=module.verify();assert not ({r['path'] for r in files}&{r['path'] for r in archive_proof['files']})
 files+=archive_proof['files'];files.sort(key=lambda row:row['path']);dump(e/proofname,archive_proof);shutil.copy2(vp,e/vp.name)
dump(e/'raw-manifest.json',dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(v['bytes'] for v in files),scope='Retained files plus fully decoded archived boundary prefix; original logical bytes remain local. Restore archived paths before full-directory replay.'))
for name in ['case.json','definition.json','completion.json','progress.json']:shutil.copy2(w/name,e/name)
raw=ap.read_bytes();(e/'audit.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((e/'audit.json.gz').read_bytes())==raw
shutil.copy2(Path(__file__),e/'capture.py');dump(e/'summary.json',summary)
(e/'README.md').write_text('''# Fresh elastic fine N1600 physical audit\n\nAll51200steps/32cycles from zero,16-cycle ramp. All20segmented phases completed0; every accepted step and all4829PVD phases per domain independently checked against logs, receipts, actual paths and original input/binary hashes. No numerical rerun. Full last4800frames plus preceding46400endpoint audited. summary.json records actual passed/failed physical gates without changing any threshold. Full audit compressed and decoded readback exact, complete raw manifest retained.\n\nAudit command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n1600/case.json --work build/recompute-20261109/elastic-s24-l1-n1600 --first-step46401 --output build/recompute-20261109/elastic-s24-l1-n1600-audit.json`. All physical checks passing would still not establish independent budgets or final production qualification.\n'''.replace('--first-step46401','--first-step 46401'))
print(json.dumps(summary,indent=2))
