> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bound pressure audit memory without changing metrics

56 immutable files, 1 parts, 249,028 bytes. Source base6bce127; new analyzer SHA
`6fdd2a4a8d82c4a40a51235c51129f1c4bc0a26d2609793540ee4402849e5e3d`.

The original S24 fine N400 solve completed12800, but its1200-state audit exceeded
2GiB: max36/oom1/oom_kill1, return-9,876.028295 seconds. The old reader retained
400 complete phase frames. Retain immutable paths instead and reread the same
previous phase; all integral formulas, accumulation order and gates are unchanged.

The new live-frame/nonzero-drift regression fails against the old source and passes
with the fix. Windows and WSL each pass9 affected tests. A complete1200-state
coarse audit is exactly identical in every report value except analyzer SHA:
566.535979 seconds,36,995,072-byte peak,2GiB/swap0,zero memory events,empty scope.
The numerical solver was not rebuilt or rerun. Fine-grid re-audit is separate and
still pending at this checkpoint; no new physical qualification is claimed.

[Validation](validation.json), [frozen source](validation-definition.json),
[Windows tests](windows-tests.json), [original coarse report](coarse-original.json),
[old OOM receipt](old-oom-resource.json), [old failure](old-failure.json),
[summary](summary.json), [manifest](manifest.json), [archives](archives.json),
[actual Git bytes](index-staging.json). Full coarse raw states are already in the
[coarse pair archive](../elastic-s24-coarse-eonsim-pair-2026-11-08/README.md).
