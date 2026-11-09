> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Fine direct solve under a per-rank address-space bound

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

This completed diagnostic was not adopted. At source30828c5 it used the
same alpha2 fine-mesh step400 seed, four MPI ranks on four guest-reported core groups,
and executable SHA256
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`.
The locked PETSc3.23.7 Release MUMPS/chord candidate had a900-second limit
and3.5GiB of virtual address space per rank. The frozen controller, exact
command, seed, limits, output and cleanup receipt are in the archive.

The [recorded attempt](report.json) returned1 after7.085086033 seconds,
with allocation failures during solver setup and no accepted step. The
Schur comparison was skipped, so there is no valid performance ratio or
field-equivalence result. Cleanup found no remaining owned-session member.
The current continuation was kept.

The later [whole-job memory-cap study](../womersley-mumps-entry-2026-11-08/README.md)
is a separately declared resource policy. A per-process virtual address
limit is not a measurement of total resident memory; its failure must not
be rewritten as physical nonconvergence or erased by that later result.

[16 files](manifest.json) were read back and hash-verified in one
4,603,812-byte archive. [Metadata](archives.json) records capture5091b68,
the omitted executable hash and all copied-file hashes. No production
controller or numerical acceptance criterion changed in this diagnostic.
