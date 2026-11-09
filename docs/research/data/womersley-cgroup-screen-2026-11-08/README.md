> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed fine MUMPS versus Schur screen under a whole-job limit

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

At source5091b68, both configurations restart the identical alpha2 fine
S48/level2/N200 accepted step453 and compute steps454–456 on the same four
guest-reported core groups with four MPI ranks. They use locked PETSc3.23.7 Release
executable SHA256
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`,
the same mesh, physical problem and stopping tolerances. Original processes
were paused only for this screen and all six resumed at UTC01:28:58.

The [complete report](report.json) gives MUMPS/chord181.986027972 seconds
versus Schur/vector/chord353.399878907 seconds: ratio0.514957811, a48.50%
local reduction. Maximum final-field difference5.296499350215811e-12 and
maximum complete-history difference5.810796288585607e-12 pass2e-9. The
legacy clocks happened to match exactly; their declared tolerance remains
1e-12. Positive nonlinear/linear reasons are retained in the raw logs.

Each separate whole-job cgroup had memory.max14GiB, swap.max0 and a900-second
timeout. Per-rank guards read the live cgroup limits before executing the
solver. Observed cgroup peaks were10,821,701,632 bytes for MUMPS and
3,319,377,920 for Schur. A terminated transient unit's later inactive
properties are not the live limit measurement. The prior allocation failure
under [per-rank virtual-address limits](../womersley-direct-bounded-failure-2026-11-08/README.md)
remains a separate result; these resource policies are not interchangeable.

This screen marked eligibility only. The later
[460-step handoff](../womersley-mumps460-handoff-2026-11-08/README.md) made
the independent execution adoption. The screen is not general scaling,
long-cycle accuracy or the later LU-factor-reuse experiment.

[76 files](manifest.json) containing the frozen controller, commands, seed,
fields, histories and resource records were read back and hash-verified in
three parts, totaling58,674,092 bytes. [Archive metadata](archives.json)
records capture e435524 and omitted executable hashes.
