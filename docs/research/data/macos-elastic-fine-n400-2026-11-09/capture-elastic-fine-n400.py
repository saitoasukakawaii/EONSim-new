from pathlib import Path
import json,hashlib,shutil,gzip,re
root=Path(__file__).resolve().parents[2];b=root/'build/recompute-20261109';w=b/'elastic-s24-l1-n400';d=root/'docs/research/data/macos-elastic-fine-n400-2026-11-09';d.mkdir()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
r=json.loads((b/(w.name+'-audit.json')).read_text());receipt=json.loads((w/'completion-postflight.json').read_text())
assert r['steps']==receipt['accepted_steps']==12800 and r['first_step']==11601 and r['sampled_steps']==1200
assert sha(w/'case.json')==r['case_sha256'] and sha(root/'scripts/audit_pressure_tube.py')==r['analysis_script_sha256']
for name,digest in receipt['input_sha256'].items():assert sha(w/name)==digest
for name,digest in receipt['index_sha256'].items():assert sha(w/name)==digest
assert r['periodic'] and all(v['passed'] for v in r['quality_gates'].values())
mean=r['harmonics']['mid_radial_displacement']['mean'];expected=r['infinite_plane_strain_compliance']*r['physical_definition']['pressure'];error=abs(mean-expected)/abs(expected)
assert error<.02 and min(r['minimum_solid_jacobian'],r['minimum_fluid_jacobian'])>0
worst=max(v['relative_max'] for cycle in r['cycle_differences'].values() for v in cycle.values());assert worst<1e-5
files=[]
for p in sorted(w.rglob('*')):
 if p.is_file() and not p.is_symlink():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
dump(d/'raw-manifest.json',dict(local_root=str(w),files=files,total_bytes=sum(x['bytes'] for x in files),scope='Fresh local complete raw bytes, not embedded/uploaded; transparent compression keeps content unchanged'))
for name in ['case.json','definition.json','completion-postflight.json','failure.json']:shutil.copy2(w/name,d/name)
raw=(b/(w.name+'-audit.json')).read_bytes();(d/'audit.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((d/'audit.json.gz').read_bytes())==raw
summary=dict(steps=12800,audited_first=11601,audited_last=12800,periodic=True,maximum_cycle_relative_difference=worst,quality_gates=r['quality_gates'],minimum_solid_jacobian=r['minimum_solid_jacobian'],minimum_fluid_jacobian=r['minimum_fluid_jacobian'],lame=dict(mean=mean,expected=expected,relative_error=error,limit=.02,passed=error<.02),audit_sha256=sha(b/(w.name+'-audit.json')),qualification='Local physical/period gates pass; N800 time/space/tail/sampling, geometry, finite-end and matched-reference gates incomplete')
dump(d/'summary.json',summary)
(d/'README.md').write_text(f'''# Fresh elastic fine N400: final-three-cycle physical audit passes\n\nAll12800 accepted steps,32 cycles/16-cycle ramp, from zero; snapshot92fef88\nEONSim Release, macOS arm64/PETSc3.25.6, serial MUMPS/LU32. Controller52281\nfailed only after both successful solves while collecting the wrong restart\nPVD name; original failure remains. `finalize-elastic-series.py` verified\ncontiguous logs and built indexes without another solve.\n\nAudit32102 exit0, actual preceding endpoint11600 and every step11601..12800.\nWorst five-field cycle maximum{worst:.10g}<1e-5; kinematics5.42102e-20,\nstage mass7.06900e-17, divergence theorem1.18914e-17. Both Jacobians positive.\nLamé mid-ring mean{mean:.15g}, expected{expected:.15g}, relative error\n{100*error:.10g}%<2%. Independent error budgets and matched reference remain\nrequired; coarse3.195% failure is preserved, not replaced by this result.\n\nCommand: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1\nbuild/analysis-venv/bin/python scripts/audit_pressure_tube.py --case\nbuild/recompute-20261109/elastic-s24-l1-n400/case.json --work\nbuild/recompute-20261109/elastic-s24-l1-n400 --first-step 11601 --output\nbuild/recompute-20261109/elastic-s24-l1-n400-audit.json`.\n\nFull raw hashes remain in this evidence, raw data local. Complete audit is\nlosslessly compressed and read back; all consumed source inputs are bound.\nNo full physical or48h-completion claim.\n''')
print(json.dumps(summary,indent=2))
