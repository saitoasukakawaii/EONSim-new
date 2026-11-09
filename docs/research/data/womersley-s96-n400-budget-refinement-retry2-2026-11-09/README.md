> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S96 failed N200 sampling budget and N400-target refinement

Source checkpoint `a3e1c87e071ce73f480b63a1144874cd75e3e1c5`.
45 files, one33876-byte part, with actual archive-member and ordinary Git-blob
SHA256 verification: [archives](archives.json), [manifest](manifest.json),
[index receipt](index-staging.json), [results and immutable plan](s96-summary.json).

The completed original six-cycle N200/N400 family has all fine analytic and
periodic gates passed. Its N200-target budget is nevertheless **failed**:
velocity sampling/space=.115648790529 exceeds.1. Velocity/pressure time ratios
.073911407822/.079631443096 pass, as do both tail and pressure sampling terms.
This original failed report is retained unchanged.

The new target is the existing full N400 fine trajectory paired with the
already complete coarse N400 trajectory and a fresh N800 time control. Same
60eb5cc0... native-rank1 executable, mesh, BDF2, default time-dependent tau,
MUMPS/chord/LU32, six cycles and full400/800 phases. CPU21,6GiB/swap0,
14GiB admission/8GiB floor. Independent plan review precedes actual producer
41187 adoption19:55:24UTC; N800 numerical work starts19:57:37.

The new400-phase space RMS is U.001823100329075899 and P.005360697553238737.
Existing N400 velocity sampling is8.709601113322095e-5, about4.78% of its new
space difference; this one term passes. N8004800 steps, new time difference,
full tail/sampling budget and final qualification remain pending.

Only resolution constants/labels200→400 and400→800 change in the original
budget body. Inverse substitution is byte-identical and AST-identical; all
formulas, norms and thresholds remain. The archive contains the complete old
budget and the new immutable definition/source/commands/review/adoption and
completed new space comparison, not growing N800 output. The full original
N400 trajectory is being captured separately.

First capture rejected repository helper files outside its declared evidence
roots before any archive part was written. Its failed controller/traceback and
empty destination are preserved. Retry2 copies those helper bytes into the
declared work root and then completes both member and Git readback. No numerical
work was repeated or changed by this archival failure.
