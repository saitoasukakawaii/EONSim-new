> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# N200 elastic tube, field budgets and mesh replay

At source checkpoint `6093f01`, both frozen EONSim `b072cc8` and pinned svFSI
`7bdb74c` completed6400 steps, with N200/default stabilization, ramp16 and
32 cycles. Stored states5600..6400 include the true preceding endpoint.
[archives.json](archives.json) records4298 raw files read back and SHA256
checked in12 bounded archives,91,131,020 bytes total. The
[manifest](manifest.json) includes inputs, copied analysis sources, commands,
logs, full saved fields, statuses, independent replay and the N400 preflight.
The N400 controller copy is a plan in progress, not a completed N400 result.

The N200 controller's inherited source label is corrected by a separate
`provenance-label-correction.json` in its archive. The original metadata and
hash-identical copied sources are retained. No numerical state was changed.

## Actual N200 results

EONSim passes all five-field periodic/quality checks; the last-cycle maximum
is1.91934e-6. Every reference equation step passes the strict relative log
audit, but its mesh-displacement period maximum is1.93514e-5, above1e-5.
The two last-cycle differences remain required. Full comparison is ineligible.

| Observable | N200 difference | Individual gate |
|---|---|---|
|Mid-wall radial/area amplitude|2.38922%|below5%|
|Mid-pressure amplitude|2.48284%|**fails2%**|
|Mid-pressure phase|.51230degrees|below1degree|
|Left flow amplitude/phase|1.50429% /.65485degrees|below5% /2degrees|
|Right flow amplitude/phase|1.48179% /.66565degrees|below5% /2degrees|

## Same-source field differences

[summary.json](summary.json) reports exact P1 field norms on the common mesh.
The N100 side uses the completed same-source convergence re-audits from
`elastic-convergence-reaudit-c49c69c`, not the older unbound field reports.
The N100→N200 comparison uses100 common phases. The sampling check linearly
reconstructs the actual200-phase history from every other saved state,
including its real preceding endpoint. This is a sampled-grid difference,
not a continuous-time norm or a replacement for time refinement.

| EONSim field | N100→N200 RMS | Cycle31→32 RMS |100→200 sampling RMS|
|---|---|---|---|
|Fluid velocity|.0118957|1.14377e-7|9.81183e-5|
|Pressure|.0215366|6.15967e-9|1.84453e-4|
|Mesh displacement|.0132258|7.94985e-7|1.08082e-4|
|Solid velocity|.0179077|1.36613e-6|1.43615e-4|
|Solid displacement|.0178189|8.03443e-7|1.43599e-4|

All values use the previously declared field scales. Reference values and
prerequisite failures are also retained. Each difference still needs comparison
with that program's last same-dt spatial field difference; no10% budget pass
is claimed. Five manufactured sinusoidal interpolation checks recover
`(1-cos(2*pi/N))/2` within1e-14; see [oracle](phase-sampling-oracle.json).

## Independent replay of the reference mesh update

The frozen `replay-reference-mesh.py` assembles the Tet4 pseudoelastic mesh
operator from the previous deformed configuration, with nu=.3 and the exact
element-volume normalization in pinned `MESH.f`. It reads the actual accepted
boundary displacement history; no fluid/solid PDE is rerun and no reference
source is patched. Source and input hashes accompany every result.

| Check | N100 | N200 |
|---|---|---|
|Actual field replay, max normalized node difference|2.69509e-15|4.78688e-15|
|Closed-boundary incremental geometry, mesh RMS drift|1.94584e-5|1.93212e-5|
|Closed-boundary fixed initial geometry, mesh RMS drift|1.62497e-16|2.48814e-16|
|Reverse closed-boundary incremental geometry, mesh RMS drift|1.91752e-5|1.91824e-5|

Actual field replay passes its predeclared1e-8 check. Counterfactual boundary
histories subtract only the linear interpolation of the actual endpoint
mismatch, making the boundary return exactly. The fixed-geometry control
uses the same pseudoelastic law, not EONSim's vector Laplace equation. These
controlled results isolate an incremental-geometry path contribution on this
coarse mesh. They do not qualify a modified coupled reference or justify
dropping the original ALE periodic gate. Spatial effects remain pending.

The separate five-step N400/reference preflight passes all ten final equation
rows at the explicit1e-26 linear floor, max three iterations. It verifies
startup solvability only; the long N400 result remains pending. No C++ change,
new build, unrelated regression rerun, overall elastic pass or PR accompanies
this evidence checkpoint.
