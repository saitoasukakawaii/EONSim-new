> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Original production MPI and restart clock failure

This preserves the completed original S12 level0/N400 production attempt,
including the failure that motivated checkpoint v4. The frozen b072 binary
SHA256 is `2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12`.
It used MUMPS with step-local Jacobian reuse, PETSc3.23.7,32 cycles and the
unchanged16-cycle ramp. Rank1 and rank2 completed all12800 steps; their
last1200 stored states passed periodic/quality and cross-rank field checks.
The rank1 backend comparison also passed. The original rank4 evidence here
is only the short preflight; its full trajectory was scheduled separately.

The rank2 restart from12400 completed400 states, passing the2e-9 nodal and
1e-8 normalized mass-norm field limits. However, the full HDF checker stopped
at `rank0/clock`. [Diagnosis](diagnosis.json) records183/400 differing clocks,
first at12404, and a maximum/final difference of2.842170943040401e-14.
Both rank clocks show that difference. Later HDF datasets were not reached
by the failed checker and must not be called passed.

V3 omitted the compensated time-summation correction, which restore reset
to zero. Its prior contract promised tolerance-level replay, not exact
clocks. The stricter production gate is retained. The subsequent
[v4 repair and validation](../checkpoint-clock-v4-2026-11-08/README.md)
save that accepted algorithm state; the original failure is not rewritten.

[24,550 raw files](manifest.json) include commands, frozen source, mesh,
partitions, accepted histories, output fields, checkpoints and comparisons.
All26 archive parts were read back and checked against per-file hashes;
their total size is194,715,212 bytes. [Archive metadata](archives.json)
lists each part's SHA256 and the omitted ELF binary hash. Source paths and
failure identity are preserved. Archive completion does not qualify the
unfinished fine-mesh, reference, geometry or error-budget studies.
