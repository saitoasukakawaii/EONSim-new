> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Natural-segment resource handoff: startup evidence only

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

The e435524 LU-cache candidate passed its small correctness checks in the
[separate verification archive](../lu-preconditioner-reuse-2026-11-08/README.md).
Before admitting another fine MUMPS solve, an actual process fixture proved
that a waiting parent can be stopped while its numerical child finishes
naturally, then resumed successfully. A real four-rank logging fixture also
verified the production profile parser: eight fresh LU factorizations versus
one with window8. The fixture inputs, commands, outputs and source are
included; these shared-core runs are not performance measurements.

At UTC 02:50:32, controller 24147 intentionally stopped only the existing
study driver 22001. Its MPI launcher/ranks continue to their already declared
step600 boundary. [The observation](waiting-observation.json) distinguishes
that waiting parent from the running numerical children. The old controller
21873 retains its CPU and direct-memory admission locks. No second large
factor is allocated while the original numerical children are alive.

The frozen [definition](definition.json) declares three sequential eight-step
comparisons from the same complete step600 seed: old default, new default,
and new cached LU. Each uses four guest-reported core groups, a private whole-job 14GiB
memory limit, no swap and a 1200-second timeout. Admission needs more than
16GiB available; less than 8GiB during a run ends its owned scope. Complete
field/history differences must be below 2e-9; old/new clock comparison keeps
the legacy 1e-12 allowance, while new/new clocks must match exactly.
Actual factor counts must be 8/8/1; at least 10% local cost reduction is
needed for eligibility. The original driver resumes only after all new
probe scopes are empty. This controller does not adopt a production policy.

If recovering after a controller crash, first check the exact process-start
identities in [the pause receipt](pause.json) and clear only its owned
`eonsim-lu-screen-*-24147.scope` jobs. Resume the same driver only once those
scopes have no members. Do not start a duplicate original MPI job.

[126 immutable files](manifest.json), including a dated observation rather
than growing logs, were read back and hash-verified in one 35,804-byte part.
[Metadata](archives.json) records capture e435524. The fine-grid screen is
still pending; this archive makes no claim of speedup, adoption or physics
qualification.
