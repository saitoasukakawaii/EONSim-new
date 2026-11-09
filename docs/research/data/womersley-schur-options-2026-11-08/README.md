> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bounded Schur sub-preconditioner screen

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

Source c49c69c plus the exact copied probe; EONSim b072cc8 and PETSc3.23.7
unchanged. All 94 archived files were read back and SHA256 verified. Each mode
restarts the same immutable four-rank accepted checkpoint and takes three
steps, with identical physical inputs, residual and stopping tolerances.
The fixed maximum nodal velocity/pressure difference limit is 2e-9; owned and
ghost values are checked by the existing field reader. All modes use chord -2.

| Grid | Sub-preconditioners | Wall seconds | Maximum field difference |
| --- | --- | ---: | ---: |
| S48 level0 | GAMG velocity/pressure | 1.87500 | 0 |
| S48 level0 | GAMG velocity, HYPRE pressure | 1.22115 | 4.98375e-13 |
| S48 level0 | HYPRE both | .91934 | 2.20058e-12 |
| S48 level2, 91905 nodes / 516096 tets | GAMG velocity/pressure | 366.70294 | 0 |
| S48 level2 | GAMG velocity, HYPRE pressure | 292.45091 | 3.31320e-12 |
| S48 level2 | HYPRE both | 575.00644 | 7.20799e-12 |

All actual three-step reports have positive SNES/KSP reasons and finite
accepted fields. Fine-grid peak rank RSS is approximately 989/904/986 MB.
The all-HYPRE fine option uses fewer total Krylov iterations but costs more
per iteration; its fine linear solve time is 566.62 seconds versus 358.81 for
GAMG. A coarse-grid speed observation does not predict the fine-grid result.

Four ranks were restricted to CPUs18-23, verified by an actual MPI affinity
preflight. This is six logical CPUs on three guest-reported core groups, while independent
alpha1/alpha2 and serial elastic jobs ran elsewhere. These are local concurrent
option observations, not a general speed/scaling benchmark. No new setting
was adopted in an active production study. Any later adoption still requires
explicit study-definition and checkpoint provenance; three steps do not prove
long-term accuracy or the physical acceptance gates.

Commands, raw solver trees/timings, reports, input cases, final fields, exact
initial checkpoint hashes and executed probe sources are in the two archives.
No C++ change, new dependency or unrelated regression was required.
