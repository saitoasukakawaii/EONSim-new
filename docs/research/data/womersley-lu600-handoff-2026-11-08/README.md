> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Accepted600 fine-grid handoff: sealed inputs and original trajectory

This archive records the explicit alpha2 S48 level2 N200 handoff at
UTC2026-11-08T04:28:40Z. The independent
[eight-step screen and review](../womersley-fine-lu-screen-2026-11-08/README.md)
precede this adoption. [The receipt](adoption.json) selects the Release
`f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`
binary, MUMPS/chord and LU window8 from the complete legacy step600.
The target retains six cycles to1200; its last three cycles4–6 all use the
new strategy. Legacy v3 initialization does not reconstruct missing clock
compensation; subsequent v4 states preserve it.

The new controller25368 prepares its immutable inputs, seed and waiting
successor before retiring the original21873 family and unused21907 waiter.
[Cleanup](original-cleanup.json) confirms the original owner exited and its
entire scope was empty. The raw `Controller interrupted` status remains
with the planned handoff evidence. It is not a numerical convergence failure.
The original study is sealed through601, including the short resumed segment
after its driver was restored by the screen. Its142 checkpoint generations
from460 through601 are preserved; this is a partial trajectory, not a
completed1200-step study.

The recorded successor25369 was correct at this handoff. It was later
cancelled before any N400 numerical work and replaced by25665 when the
[middle-grid handoff](../womersley-middle-lu8-2026-11-08/README.md) selected
its matching spatial producer. Do not restart retired21873/22001/21907
or25369 from these historical receipts.

Execution used four ranks on WSL guest CPUs0–7, PETSc3.23.7, single-thread
libraries, a14GiB/swap0 whole-job scope,16GiB available-memory admission and
8GiB running guard. The frozen controller command is
`/usr/bin/python3 build/prod48-20261107/handoff-womersley-lu8-m600.py`;
its SHA256 is
`130e9c77f515d283b7c9718dc340a1fbc5878122246ffc7b9950b543752b4dfa`.
Source, actual commands and checks are in the archive. CPU labels mean
[guest affinity](../execution-topology-2026-11-08/README.md), without a
host-core isolation or scaling claim.

[855 files](manifest.json) were captured at source checkpoint2367903 and
read back from18 archive parts totalling681,216,796 bytes; [metadata](archives.json)
records two omitted ELF copies by exact hash. The full sealed original study
and its controller evidence are included. For the new running study, only
immutable definitions, source, seed, inputs and adoption/cleanup receipts
are included. Growing trajectories, logs and resource measurements are
excluded. Capture completed at UTC05:15:07. Long-period, analytic and
time/tail/sampling qualification remains separate and incomplete.
