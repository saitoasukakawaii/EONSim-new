> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Fine-grid retained LU: measured screen and adoption review

This completed screen uses the same accepted alpha2 step600, S48 level2
mesh, four-rank partition, BDF2/N200 inputs and physical final time1200.
It compares eight accepted steps601–608. The old binary is
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`;
the candidate is
`f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`.
Candidate implementation and prior Debug/Release/MPI evidence are in the
[separate correctness archive](../lu-preconditioner-reuse-2026-11-08/README.md).

| Configuration | Whole-job seconds | Actual LU factorizations | Peak cgroup bytes |
|---|---:|---:|---:|
| Old default MUMPS/chord | 494.556161080 | 8 | 10,841,153,536 |
| New default MUMPS/chord | 474.623760231 | 8 | 10,936,459,264 |
| New MUMPS/chord, window8 | 116.530105585 | 1 | 10,769,051,648 |

The [report](report.json) gives cached/new-default wall ratio
0.2455210112706628, a local75.4479% reduction, above the predeclared10%
selection threshold. PETSc `MatLUFactorNum` count ratios are1 across ranks;
the counts are actual events, not an inference from retained object names.
Triangular solves rise from16 to23; reuse reduces factorization work but
does not remove the cost of solving the current operator.

Each paired comparison reads160 HDF datasets across all eight states and
four ranks: current fluid, previous-time fluid, clock, metadata and time
metadata. Old/new default maximum field/history difference is
4.445228907190568e-18; the explicit legacy clock tolerance1e-12 sees zero
difference in its two stored entries. New default/cache maximum is
1.0343288725511712e-16; v4 clocks, including compensation, and time metadata
are exactly equal. All nonlinear/linear reasons are positive. The
[independent adoption review](handoff-review.json) rereads every dataset,
profile event, resource receipt and unchanged seed hash before recording
eligibility for the separate step600 handoff. This screen itself does not
adopt a production policy or qualify a long trajectory.

The existing study driver alone was paused while its numerical children
finished the natural600 boundary and released their large factors. Each
new mode then ran serially in a private14GiB/swap0 cgroup, with16GiB
available-memory admission,8GiB running guard and1200s timeout. All modes
exited normally, no memory-limit/OOM events occurred, and their scopes were
empty before the [original driver resumed](resume.json) at UTC04:26:39.
[Seed provenance](checkpoint-source.json) identifies the complete original
checkpoint. No second fine factorization overlapped the old numeric job.

Four ranks use WSL guest CPU groups0–7 with single-thread libraries and the
locked PETSc3.23.7 runtime. Other project jobs continue concurrently. The
raw frozen report says “physical cores”; interpret that historical label
using the [Windows/WSL topology correction](../execution-topology-2026-11-08/README.md).
This is one local execution screen, without host-core isolation, repeated
benchmark statistics or a scalability claim.

The archive also preserves three immutable early reference-log snapshots.
The [prefix diagnostic](reference-prefix-summary.json) checks4518 S12/N200
nu.3 steps,1758 S24/N400 nu.3 steps and1030 S24/N400 mesh-nu0 steps. Every
final equation row in those prefixes has a printed relative ratio below
1e-10, with at most three nonlinear iterations. The entire highest observed
step is excluded because its log may still be growing. This is an early
diagnostic; full-run convergence and physical qualification remain required.

[Queue review](queue-wait-review.json) records an unrun preparation change:
release numerical CPU/memory locks while waiting for the middle study,
then reacquire them before analysis. The numerical budget tail remains
byte-identical to the prior MUMPS queue. Prepared scripts in this archive
are not evidence that their long jobs have completed.

[330 files](manifest.json) were read back and hash-verified in seven
155,598,764-byte archives. [Capture metadata](archives.json) records two
omitted ELF copies by hash and capture commit638f75c. Original inputs,
meshes, partitions, complete three-mode checkpoints, profiles, logs,
resource receipts, controller source and the independent review are retained.
Long-period, analytic, time/tail/sampling and overall production gates are
still separate and incomplete.
