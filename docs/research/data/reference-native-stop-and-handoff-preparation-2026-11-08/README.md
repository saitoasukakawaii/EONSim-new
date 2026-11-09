> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Native normal-stop proof and initial handoff preparation

This archive contains257 verified files in8 ordinary Git archive blobs,
62478896 bytes in total. The source checkpoint is `abec003`.

The pinned reference solver checks `results/STOP_SIM` after an accepted step,
writes its native checkpoint, and exits normally. The corrected serial
2800→2810 and two-rank2600→2610 trials each reproduce all10 uninterrupted
oracle states: five fields, native history, saved norms and time agree
exactly, excluding elapsed time and nonstate rank padding only. Both resource
scopes returned normally with zero memory events and no remaining processes.
The first wrong-directory trial, its partial output and controlled cancellation
are also retained.

Independent review reread the proof and regenerated the complete coarse EONSim
and reference reports with the same frozen analyzer. Every physical report
value remained identical. The initial4000-boundary handoff preparation is
included, but it was **never executed**: its original budget waiter later
failed because the old EON sampling controller rejected occupied siblingCPU23.
A fresh recovery-specific handoff supersedes that preparation. This archive
does not claim that a reference backend transition or physical qualification
has completed.

The archive excludes active continuation logs and future adoption records.
Existing uninterrupted oracle data are in the
[native backend proof archive](../reference-trilinos-native-recovery-proofs-2026-11-08/README.md).
See [the archive manifest](archives.json), [raw member hashes](manifest.json),
[stop report](stop-report.json), [independent review](handoff-review.json),
[preparation definition](preparation-definition.json) and
[Git byte verification](index-staging.json).
