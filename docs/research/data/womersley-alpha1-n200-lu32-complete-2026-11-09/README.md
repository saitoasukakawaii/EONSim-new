> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S48 alpha1 N200 LU32 trajectory

This sealed stage contains4116 files in79 compressed parts, totaling1920613192B.
It preserves the completed1200-step numerical stage, retained current/history
states, input meshes, frozen sources, commands, resource receipts and analysis.
The actual native200 handoff and earlier failures are linked by exact hashes in
[summary.json](summary.json); no original failed attempt is rewritten.

The6-cycle S48 level2 case uses alpha1,200 steps/phases per cycle,2 warmup cycles,
four ranks, fixed60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07
binary, MUMPS/chord and explicit LU reuse window32. The mesh has91905 nodes and
516096 tetrahedra. Definitions and numerical results are in
[n200-analysis.json](n200-analysis.json).

Velocity relative field error is1.016444554197648%, failing the1% gate.
Pressure error.2160891315219282%, flow-amplitude error.6402408209449373%,
phase error.04045160746086848degrees and maximum net flux1.5931101551077288e-17
pass. The last two field-cycle comparisons pass. Periodicity does not erase
the velocity failure. N400 and complete spatial/time/tail/sampling budgets are
separate work; this completed N200 archive is not whole-family qualification.

[archives.json](archives.json) binds every compressed part;
[manifest.json](manifest.json) binds all original member bytes. Storage is in
bounded local Git batches: parts001–048, then049–079 and complete metadata.
The [final index receipt](index-staging.json) verifies every part as an ordinary
100644 Git blob by full byte readback. The sparse worktree avoids another copy
of large parts; original D files remain present. These are real Git objects,
not path pointers. No remote push, PR or final acceptance is implied.
