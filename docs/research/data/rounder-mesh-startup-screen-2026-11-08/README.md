> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S96 mesh diagnostics and rejected startup reuse window

These are independent diagnostics atd844e40, not an adopted long study.
The unchanged tube generator produced three meshes. The frozen interpolation
worker evaluates the existing circular reference on the P1 mesh; it does not
solve the three-dimensional PDE or establish its accuracy/cost.

| Seed and red level | Nodes / tetrahedra | Alpha2 interpolation error | Minimum / median shape quality |
|---|---:|---:|---:|
|96/8/8, level0|6,921 /34,560|0.0064576994717289|0.102385813 /0.302254587|
|96/8/8, level1|50,609 /276,480|0.0021657556122281767|0.054077866 /0.251028074|
|96/8/16, level1|98,241 /552,960|0.0021657556122281767|0.102006741 /0.358078660|

The [mesh report](mesh-report.json) retains alpha1 results, exact hashes and
all metrics. The smaller level1 mesh has interpolation error near the prior
91,905-node mesh, but worse minimum shape quality; that observation does not
establish a better PDE discretization. Geometric and total error norms cannot
be subtracted to infer a pure discretization error.

The actual32-step S96/8/8 level0 PDE screen uses the frozen f7bf9f3d binary,
four ranks sharing CPU21 with idle-yield, identical BDF2/default-stabilization
inputs, 2GiB memory/swap0 and full state output. In the
[startup report](startup-report.json), window8 takes95.526171680s with4 actual
LU factorizations; window32 takes127.680549184s with1 factorization.
The ratio1.336602806733527 fails the declared10% reduction gate.
Both modes converge;640 HDF datasets differ by at most2.369287058212599e-12,
with exact v4 clock/time metadata. **Numerical comparison passes, cost
selection fails, and neither a new coarse nor fine long study is adopted.**
Fewer factorizations alone did not imply lower cost.

The [definition](definition.json) freezes commands, sources, caps and gates.
Actual commands were `/usr/bin/python3 build/prod48-20261107/screen-rounder-tube-meshes.py`
and `/usr/bin/python3 build/prod48-20261107/run-rounder-womersley.py --level 0`.
Mesh work completed UTC05:48:31; the startup screen completed UTC06:02:03
on2026-11-08. The dependent level1 waiter was
[cancelled before any numerical work](numerical-waiter-cancellation.json),
after its exact PID/start/command identity was checked. Its original failure
and cancellation receipts remain in the archive; no original S48 producer
was changed or paused.

The first capture waiter was also [retired before capture](capture-waiter-cancellation.json):
two requested report copies shared the basename `report.json`, which the
unchanged capture helper correctly rejects. V2 copies them as
`startup-report.json` and `mesh-report.json`, verifies unchanged hashes, and
archives both original paths along with both controllers and cancellation
receipts. No original report was overwritten.

`capture-rounder-startup-screen-v2.py` completed UTC06:29:25. The
[manifest](manifest.json) contains436 complete verified files, and
[two parts](archives.json) total19,683,352 bytes. The
[actual Git-index check](index-staging.json), invoked with native Python3.13
and `stage-external-archives.py rounder-mesh-startup-screen-2026-11-08`,
verifies full ordinary blob contents while retaining the D originals.
This archive includes all completed numerical states and meshes; publication
and full physical qualification remain pending.
