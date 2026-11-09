> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed alpha1 and independent-reference execution preflights

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

These two completed checks selected execution arrangements for separate
long studies. They do not certify their unfinished periodic trajectories.
The archive includes frozen controllers/readers, exact commands, physical
inputs, partition/mesh data, complete preflight fields and original outputs.

The [alpha1 fine-grid check](alpha1-probe.json) compares three startup steps
on the same four guest-reported core groups and four ranks. With locked PETSc3.23.7
Release, the original Schur/chord path took804.987822037 seconds; explicit
three-component velocity metadata took426.417200324 seconds. The maximum
final-field difference3.813811462818895e-12 passes2e-9, and the local cost
reduction exceeds the declared10% gate. The candidate executable SHA256 is
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`.
Original output and prior execution identity remain; the fine-vector study
started only after this check and is independently tracked.

The [svFSI mesh-motion-nu0 preflight](nu0-reference-preflight.json) compares
20 full-load startup states using one and two ranks. It holds structural
Poisson ratio0.3 while the independent mesh-motion variant uses0. Across
all five fields, maximum nodal difference1.6653345369377348e-16 and maximum
normalized mass-norm difference2.4558182111500794e-14 pass the original
2e-9/1e-8 limits. Measured local times396.941948103 and261.554205039 seconds
selected two ranks for the separate long reference. The fixed svFSI source
is7bdb74cdd517310d6bf32c0bb7d42072aeac8658a. This allocation comparison
uses shared guest-reported core groups and is not a general MPI scaling result.

The twenty-state fixture is neither the production ramp history nor a
periodicity or physical-accuracy pass. The original mesh-motion-nu0.3
reference remains separate. Each production variant still requires its
own time, tail, sampling and spatial budgets.

[157 files](manifest.json) were read back and hash-verified in three parts,
totaling58,980,120 bytes. [Metadata](archives.json) records capture977b130,
which is distinct from the numerical controllers' original frozen sources.
