> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Matched-mesh static end-length study

Frozen `b072cc8`/PETSc3.23.7 Release, one process on CPU22; source and exact
helper hashes at checkpoint6093f01. Ten full-annulus linear-elastic solves
completed. [archives.json](archives.json) records109 files independently read
back and SHA256 checked; [manifest.json](manifest.json) covers all commands,
inputs, meshes, logs, output fields, sources and status. See the captured
[controller](study-static-clamped-length.py), [results](summary.json) and
[length differences](length-differences.json).

R=1, outer radius1.2, E=1000, nu=.3, constant inner pressure.02, outer pressure0,
and all displacement components fixed on both end faces. The full circumference
is solved without quarter symmetry constraints. L12 and L24 use respectively
12 and24 initial axial layers, so each pair has the same local mesh sizes and
cross-section. Red refinement preserves the polygon. The S12 L12 level0/1
meshes are verified identical, after parsing, to the active coupled studies.

Mid-wall radial displacement is the reference-arclength-weighted projection
on the material ring at x=L/2. Gauss6/8 integration differences are below1e-9
on the Lamé scale (largest7.863e-13). All actual nonlinear/linear convergence
reasons are positive, constraints and geometry pass, and strain energy agrees
with half the pressure boundary work within the predeclared1e-10 relative check.

| Polygon/level | L12 mean error from circular Lamé (%) | L24 mean error (%) | L12→L24 change / Lamé scale (%) |
|---|---|---|---|
|S12/0|8.32581|8.71506|.389256|
|S12/1|4.81438|5.15375|.339374|
|S12/2|2.64200|2.94259|.300593|
|S24/1|1.25012|1.57258|.322455|
|S48/1|.309608|.621127|.311519|

These pairwise static observations isolate a change of end distance at matched
local resolution. They are not a dynamic end-error bound, an asymptotic spatial
rate, or a circular exact solution on a polygon. The S24/level1 result motivates
a bounded coupled preflight; it does not pass the actual dynamic mean-response,
periodic, cross-code or time/space budget gates. The previous
[quarter-annulus study](../lame-static-2026-11-08/README.md) has different supports
and remains separately identified. No C++ code, build or general performance
claim is introduced by these experiments.
