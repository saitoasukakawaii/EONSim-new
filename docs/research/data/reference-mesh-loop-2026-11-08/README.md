> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Prescribed boundary-loop mechanism diagnostic

Source `a7a177e`; `/usr/bin/python3 -u
build/prod48-20261107/diagnose-reference-mesh-loop.py`, one thread on CPU23.
[34 files](manifest.json) were read back from a713432-byte archive;
[hashes](archives.json), [definition](definition.json) and [results](summary.json)
include frozen readers, actual prescribed arrays, meshes and drift vectors.
The original201 reference frames remain bound by SHA256 to the previously
archived [N200 evidence](../pressure-tube-time-2026-11-08/README.md).

The same independently verified incremental mesh equation is replayed with
strictly closed prescribed boundary displacement. At mesh nu=.3/N200, its
drift vector reproduces the previous diagnostic exactly (normalized maximum
nodal difference0, limit1e-10). Every new free-row true relative residual is
below2.769e-15, passing the unchanged1e-10 diagnostic limit.

| Prescribed-boundary counterfactual | Normalized endpoint drift RMS |
|---|---|
|Original closed path,200 increments, mesh nu=.3|1.93212004e-5|
|Same piecewise-linear path,400 increments|1.92856655e-5|
|Same piecewise-linear path,800 increments|1.92681050e-5|
|First temporal harmonic,200 increments|1.93212004e-5|
|Rank-one harmonic shape path,200 increments|2.05307713e-7|
|Original closed path, mesh nu=0|5.85006845e-6|
|Original closed path, mesh nu=.45|5.10699624e-5|
|Original closed path, mesh nu=.49|5.78988475e-5|

All endpoint boundary differences are exactly zero. Subdivision changes the
integration resolution of the same path, unlike rerunning the coupled
problem with a new time step. Its persistent drift supports a path-dependent
mesh-response diagnosis; time refinement alone does not remove this observed
effect. The sine/cosine boundary coefficient matrix has a second/first
singular-value ratio.353202; the rank-one control removes its second shape
direction. This nodal Euclidean SVD is not a physical energy norm.

The mesh nu sweep changes only a counterfactual mesh material. Every reported
norm retains the physical solid's nu=.3 Lamé normalization. These results
are not full coupled solutions and cannot qualify any parameter choice.
In particular, a smaller mesh-only drift fornu0 does not make the original
nu=.3 coupled study pass. A separate fresh32-cycle coupled nu0 study was
subsequently started, retaining the original binary, physical inputs and
all acceptance gates; its outcome is not part of this completed capture.
