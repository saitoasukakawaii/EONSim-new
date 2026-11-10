from pathlib import Path
import json,hashlib,gzip,shutil
root=Path.cwd();b=root/'build/recompute-20261109';w=b/'reference-kinematic-elastic-s24-l1-n400-nu0';d=root/'docs/research/data/macos-kinematic-fine-n400-physics-2026-11-10';d.mkdir()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
r=json.loads((w/'audit.json').read_text());c=json.loads((w/'completion.json').read_text())
assert r['steps']==c['steps']==12800 and r['first_step']==11601 and r['sampled_steps']==1200
assert r['reference_convergence']['passed'] and r['reference_convergence']['reference_build']==c['reference_build']
assert sha(w/'source-case.json')==r['case_sha256'] and sha(root/'scripts/audit_pressure_tube.py')==r['analysis_script_sha256']
assert r['periodic'] and all(v['passed'] for v in r['quality_gates'].values())
mean=r['harmonics']['mid_radial_displacement']['mean'];expected=r['infinite_plane_strain_compliance']*r['physical_definition']['pressure'];error=abs(mean-expected)/abs(expected)
worst=max(v['relative_max'] for cy in r['cycle_differences'].values() for v in cy.values())
assert error<.02 and worst<1e-5 and min(r['minimum_fluid_jacobian'],r['minimum_solid_jacobian'])>0
files=[]
for p in sorted(w.rglob('*')):
 if p.is_file() and not p.is_symlink():
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  files.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest))
dump(d/'raw-manifest.json',dict(local_root=str(w),files=files,total_bytes=sum(x['bytes'] for x in files)))
raw=(w/'audit.json').read_bytes();(d/'audit.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((d/'audit.json.gz').read_bytes())==raw
for n in ['completion.json','source-case.json','execution.json','convergence.json']:shutil.copy2(w/n,d/n)
summary=dict(source_commit='ea6dfff',steps=12800,first_step=11601,sampled_steps=1200,periodic=r['periodic'],maximum_cycle_relative_difference=worst,quality_gates=r['quality_gates'],minimum_solid_jacobian=r['minimum_solid_jacobian'],minimum_fluid_jacobian=r['minimum_fluid_jacobian'],lame=dict(mean=mean,expected=expected,relative_error=error,limit=.02,passed=error<.02),audit_sha256=sha(w/'audit.json'),qualification='Local physical audit only; independent budgets and matched solver comparison incomplete.')
dump(d/'summary.json',summary)
(d/'README.md').write_text(f'''# 补丁版 svFSI N400 局部物理审计

基线 ea6dfff，审计句柄84960退出0。实际窗口11601..12800，共1200个相位，使用真实11600端点。方程收敛、运动学、阶段质量与散度检查通过；两域Jacobian为正。末两周期五场最大相对差{worst:.12g}<1e-5。Lamé均值误差{error*100:.12g}%<2%，参照输入平均压力0.02。完整审计gzip读回逐字节一致，完整本地原始文件清单已记录；原始数据未上传。

执行命令：`build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n400/case.json --work build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0 --svfsi --first-step 11601 --reference-log build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/solve.log --output build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/audit.json`。

采用已批准并验证的固定版本补丁，身份见completion。独立空间/时间/尾周期/采样预算、细网格跨求解器比较仍未完成；历史粗网格和时间预算失败保留。无完整资格或48小时完成声明，无push/PR。复用现有审计方法，不新增文章。
''')
shutil.copy2('/tmp/capture-eon-n400-audit.py',d/'capture.py')
print(json.dumps(summary,ensure_ascii=False));print('raw files',len(files))
