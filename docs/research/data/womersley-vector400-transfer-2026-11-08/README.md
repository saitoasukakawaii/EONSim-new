> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Accepted-step400 velocity-block metadata handoff

The alpha2 S48/level2/N200 continuation explicitly forked at a complete,
immutable accepted step400. The old study, logs and checkpoints remain.
The copied mesh, partition and seed hashes are recorded in
[checkpoint provenance](checkpoint-source.json). The new executable has
SHA256 `162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`;
the original executable hash is retained in [archive metadata](archives.json).

The same-state four-rank, four-physical-core, three-step check used locked
PETSc3.23.7 Release, single-thread libraries, the same physical input and
stopping criteria. [Measured local wall times](report.json) were
488.6902855 seconds for the original Schur/chord path and339.6922696 seconds
for the velocity-block3 candidate, a30.49% reduction. The maximum final
field difference was5.086627950443012e-12, below the predeclared2e-9 limit.
Solver reports retained positive nonlinear and linear convergence reasons.
This local comparison is not a scalability claim or physical qualification.

The frozen controller `handoff-womersley-vector400-retry2.py` was run with
`/usr/bin/python3 -u build/prod48-20261107/handoff-womersley-vector400-retry2.py`.
Its original source, failed predecessor, commands, complete probe outputs,
seed and continuation provenance are in the archives. The successor requests
six cycles to measure the fifth-to-sixth-cycle tail. This capture deliberately
excludes the growing long-run outputs; [scope](scope.json) identifies the
immutable inputs captured while that continuation was running.

[68 files](manifest.json) were hashed and verified by archive readback in
four parts, totaling48,934,952 bytes. Copied ELF executables are omitted and
identified by exact hashes. The capture was recorded at `30828c5`; the
original numerical controller/source identities are preserved independently.
All periodicity, analytic accuracy and error-budget gates remain unchanged.
