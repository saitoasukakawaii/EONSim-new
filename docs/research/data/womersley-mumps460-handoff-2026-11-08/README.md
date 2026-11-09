> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Accepted-step460 explicit MUMPS continuation handoff

This archive records the completed handoff that followed the independently
eligible [step453 fine screen](../womersley-cgroup-screen-2026-11-08/README.md).
The same frozen executable SHA256
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`
and locked PETSc3.23.7 Release ran four ranks. From the complete old460
checkpoint, the MUMPS/chord probe reproduced the original uninterrupted463
state. The [complete HDF comparison](handoff-probe.json) has maximum current
field difference4.043210211079895e-12 and history difference
4.42640715747622e-12, both below2e-9. Clock differences were0; the old format
retains its1e-12 allowance, not the v4 exact-clock guarantee.

Only after this check did [adoption](handoff-adoption.json) occur at
UTC01:50:05. The old7542/20170/20171/20174–20177 family exited completely;
unused20754/20817 waiters were cancelled before numerical work. These
historical processes must not be restored from the earlier pause receipt.
The new study retained the original grid, physical final time and all
physical tolerances, explicitly recording MUMPS/chord in its
[checkpoint provenance](new-study-source.json).

The study driver and all nested MPI sessions run inside one private14GiB,
swap0 scope. Its matched N400 successor waits without holding the producer's
queue lock. Frozen controllers, source, seed, original continuous463 state,
probe, commands, cleanup/adoption receipts and successor inputs are included.

[77 immutable files](manifest.json) were read back and hash-verified in
two parts, totaling29,916,128 bytes. [Metadata](archives.json) records capture
977b130, separately from the earlier numerical source. The
[capture scope](scope.json) excludes growing continuation logs and future
analyses. Dated state snapshots are not current process-control instructions;
consult the latest task queue. This archive certifies the execution handoff,
not completion of the1200-step trajectory or its physical/error-budget gates.
