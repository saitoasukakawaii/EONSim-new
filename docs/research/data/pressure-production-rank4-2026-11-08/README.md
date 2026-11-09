> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed four-rank production field comparison

The original S12/level0/N400 elastic-tube study completed step 12800 with
the frozen b072 executable, SHA256
`2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12`.
The numerical controller/readers were frozen from f0422d0; capture e435524
is only the archive identity. Locked PETSc 3.23.7 Release used four MPI
ranks, single-thread libraries and explicit MUMPS/chord options. This run
reused the already verified partition/preflight and rank1/rank2 evidence.

The [rank1-versus-rank4 comparison](rank1-vs4.json) evaluates all 1200 common
accepted states from 11601 through 12800 for fluid velocity, pressure,
ALE displacement, solid velocity and solid displacement. Maximum nodal
difference is 8.604228440844963e-16 against the 2e-9 limit; maximum normalized
mass-norm difference is 7.7285555319829e-14 against 1e-8. No interpolation,
fitted phase shift or pressure gauge adjustment is used. The complete
[summary](summary.json) retains per-field values and original source/input
hashes; exact command JSON, mesh/partition, logs, VTU and HDF output are
preserved in the archives.

This validates the stated coarse production field equivalence on at most
four ranks. It is not fine-grid scaling or complete physical qualification.
The original legacy-clock failure remains in its
[separate archive](../pressure-mpi-original-clock-failure-2026-11-08/README.md);
the later [v4 clock replay](../pressure-clock-replay-2026-11-08/README.md)
has its own executable and acceptance scope.

[24,246 files](manifest.json) were read back and hash-verified in 14 parts,
totaling 89,811,864 compressed bytes. [Archive metadata](archives.json)
records exact part/file hashes and identifies omitted ELF executables.
