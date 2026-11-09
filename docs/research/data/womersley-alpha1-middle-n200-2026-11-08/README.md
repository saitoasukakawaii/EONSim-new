> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed alpha1 middle grid at200 steps per cycle

The S48/level1 rigid-tube study completed1000 accepted steps, sampling the
last three cycles at100 phases per cycle. It used four ranks, the original
Schur path and locked PETSc3.23.7 Release executable SHA256
`2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12`.
The [immutable definition](definition.json) fixes the default transient
stabilization, BDF2 input, density/viscosity1 and pressure amplitude0.02.
The mesh has12,257 nodes and64,512 tetrahedra.

The [field audit](middle-analysis.json) reports:

| Quantity | Observed | Original gate | Result |
|---|---:|---:|---|
| Relative velocity L2 error | 1.6636599947% | <1% | Fail |
| Pressure RMS/amplitude | 0.6626461213% | <1% | Pass |
| Flow amplitude error | 0.0674338993% | <1% | Pass |
| Flow phase error | 0.0576103603 degrees | <1 degree | Pass |
| Maximum net flux | 1.3392833346e-13 | <1e-10 | Pass |
| Last-cycle velocity/pressure differences | 1.31645e-15 / 4.98304e-15 | <1e-6 | Pass |

The original solve commands, complete fields, checkpoints, logs, frozen
analysis scripts and exact analysis command are preserved. Analysis took
14.965313483 seconds and [returned0](middle-analysis-completion.json).
The completed [step1000 receipt](receipt.json) alone is not qualification.
Velocity still fails; finer-grid and separate time/tail/sampling budgets
remain required. No criterion was relaxed.

[1,563 files](manifest.json) were read back and hash-verified in five parts,
totaling171,588,648 compressed bytes. [Metadata](archives.json) records
capture5091b68 and omitted ELF hashes. This is the completed original
middle study, not a result from the later fine-grid execution optimization.
