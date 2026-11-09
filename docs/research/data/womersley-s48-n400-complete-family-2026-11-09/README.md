> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S48 α2: completed N400 trajectory and N200-target error budget

The six-cycle, 2400-step N400 study finished on 2026-11-08 at18:44:12UTC.
It is **not physically qualified**: the final velocity error is1.0459910557%,
above the unchanged1% limit. The matched N200 result also remains a failure
at1.0468222496%. Completion and archival do not change either verdict.

| Final N400 diagnostic | Value | Gate |
| --- | ---: | --- |
| Velocity relative L2 error | 1.0459910557% | FAIL, <1% |
| Pressure RMS over amplitude | 0.1907398426% | PASS, <1% |
| Flow amplitude error | 0.5183525706% | PASS, <1% |
| Flow phase error | 0.1019895043 degrees | PASS, <1 degree |
| Maximum net flux | 1.325543035e-17 | PASS, <1e-10 |
| Last-period velocity/pressure difference | 6.492602409e-15 /6.146421461e-15 | PASS, <1e-6 |

The [budget](budget.json) is explicitly for the **fine N200 target**. Its
velocity time/tail/sampling terms are respectively1.614634%,7.020664e-12%,
and3.876334% of the last spatial field difference. Pressure terms are
2.104185%,2.731971e-11%,and3.863771%. Each is below10%; the analytic velocity
failure still makes overall `passed=false`. N400 is not independently
spatially qualified by this budget.

The case uses seed48/4/8, level2, α2,400 steps and400 phases per cycle,
two warmup cycles, four ranks, the original default stabilization, and
MUMPS/chord with an eight-step retained LU preconditioner. The executable
SHA256 is `f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`.
The exact executable identity in [analysis](n400-analysis.json) and archived
definitions is authoritative; executable bytes are omitted by the archive
policy while source, build identity, inputs, commands, logs and complete
retained current/history states are preserved.

The sealed archive contains8162 files in153 complete parts totaling
3,774,516,920 bytes. The whole [archive manifest](archives.json) and
[source manifest](manifest.json) enumerate every member. Each part is an
ordinary100644 Git blob; [full index verification](index-staging.json)
records its byte-for-byte Git readback. Local D-drive archive copies remain
in place; sparse working-tree entries are not replacement pointers.
Local storage was committed in three bounded batches. The first two commits
contain only their verified parts and batch receipts; the complete metadata
is committed after all153 parts pass final verification. No upload occurs
in this archival step.

[Summary and provenance](summary.json) bind the completed producer, resource
receipts, original failed gates, and earlier complete N200/middle archives.
Those earlier raw trajectories are SHA-linked ordinary Git data and are not
duplicated here. This archive does not include the independently running
S96 N800 refinement, α1 studies, or elastic-tube production outputs.
