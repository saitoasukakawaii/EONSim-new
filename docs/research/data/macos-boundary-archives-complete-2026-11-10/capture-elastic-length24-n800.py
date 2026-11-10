"""Capture complete length24 N800 audit and raw provenance, preserving failed physical gates."""
from pathlib import Path
import json,hashlib,shutil,gzip,re
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109';w=b/'elastic-s24-l1-n800-length24';e=root/'docs/research/data/macos-elastic-length24-n800-2026-11-09'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
ap=b/(w.name+'-audit.json');r=json.loads(ap.read_text());receipt=json.loads((w/'completion.json').read_text())
assert r['steps']==receipt['accepted_steps']==25600 and r['first_step']==23201 and r['sampled_steps']==2400
assert sha(w/'case.json')==r['case_sha256'] and sha(root/'scripts/audit_pressure_tube.py')==r['analysis_script_sha256']
assert all(row['exit_code']==0 for row in receipt['receipts'])
definition=json.loads((w/'definition.json').read_text())
assert definition['length']==24 and definition['seed']==[24,2,24] and definition['level']==1 and definition['steps_per_cycle']==800
geometry=json.loads((w/'geometry.json').read_text());assert geometry['length']==24 and geometry['axial']==24 and geometry['sectors']==24
assert not list(w.rglob('*.compressed-pending'))

for name,digest in definition['inputs'].items():assert sha(w/name)==digest
assert sha(w/'eonsim')==definition['binary_sha256']
assert [(x['accepted_first'],x['accepted_last']) for x in receipt['receipts']]==[(1,23200),(23201,25600)]
for label,first,last in [('early',1,23200),('dense',23201,25600)]:
 text=(w/label/'solve.log').read_text()
 assert list(map(int,re.findall(r'^fsi_step=(\d+)',text,re.M)))==list(range(first,last+1))
 assert 'status=success' in text
mean=r['harmonics']['mid_radial_displacement']['mean'];expected=r['infinite_plane_strain_compliance']*r['physical_definition']['pressure'];error=abs(mean-expected)/abs(expected)
worst=max(v['relative_max'] for cycle in r['cycle_differences'].values() for v in cycle.values())
assert r['periodic']==(worst<1e-5)
summary=dict(steps=25600,audited_first=23201,audited_last=25600,periodic=r['periodic'],maximum_cycle_relative_difference=worst,quality_gates=r['quality_gates'],minimum_solid_jacobian=r['minimum_solid_jacobian'],minimum_fluid_jacobian=r['minimum_fluid_jacobian'],lame=dict(mean=mean,expected=expected,relative_error=error,limit=.02,passed=error<.02),audit_sha256=sha(ap),qualification='Physical checks only; independent numerical budgets, geometry/end controls and matched reference still required. Any failed gate remains failed.')
summary['all_local_physical_checks_passed']=r['periodic'] and all(v['passed'] for v in r['quality_gates'].values()) and min(r['minimum_solid_jacobian'],r['minimum_fluid_jacobian'])>0 and error<.02
assert not e.exists();e.mkdir();files=[]
for p in sorted(w.rglob('*')):
 if p.is_file() and not p.name.endswith('.compressed-pending'):
  assert not p.is_symlink();before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
# A completed capture must include the archived prefix, not silently omit it.
import importlib.util
vp=b/'verify-length-boundary-prefix.py';spec=importlib.util.spec_from_file_location('length_boundary_prefix',vp);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
archive_proof=module.verify();assert not ({r['path'] for r in files}&{r['path'] for r in archive_proof['files']})
files+=archive_proof['files'];files.sort(key=lambda row:row['path']);dump(e/'boundary-archive-proof.json',archive_proof);shutil.copy2(vp,e/vp.name)
dump(e/'raw-manifest.json',dict(local_root=str(w),files=files,count=len(files),total_bytes=sum(v['bytes'] for v in files),scope='Retained files plus independently decoded archived immutable boundary prefix; all logical bytes local, restore archived members before directory replay.'))
for name in ['case.json','definition.json','completion.json']:shutil.copy2(w/name,e/name)
raw=ap.read_bytes();(e/'audit.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((e/'audit.json.gz').read_bytes())==raw
shutil.copy2(Path(__file__),e/'capture.py');dump(e/'summary.json',summary)
(e/'README.md').write_text('''# Fresh elastic length24 N800 physical audit\n\nAll25600steps/32cycles from zero,16-cycle ramp. Both numerical phases completed0; contiguous accepted steps, original input and executable hashes independently checked. No numerical rerun. Full last2400frames plus preceding23200endpoint audited. summary.json records actual passed/failed physical gates without changing any threshold. Full audit compressed and decoded readback exact, complete raw manifest retained.\n\nAudit command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n800-length24/case.json --work build/recompute-20261109/elastic-s24-l1-n800-length24 --first-step23201 --output build/recompute-20261109/elastic-s24-l1-n800-length24-audit.json`. All physical checks passing would still not establish independent budgets or final production qualification.\n'''.replace('--first-step23201','--first-step 23201'))
print(json.dumps(summary,indent=2))
