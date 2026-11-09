> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed prefixes of three live reference studies

This read-only inspection ran at22:47:36 UTC,2026-11-08, from local checkpoint
`4f9bf6f3927cb47620f99383dc2994142cf85042`. It copied each selected native record
below the highest potentially writing checkpoint, then copied only the log
prefix preceding the first later step. Source prefix bytes and native hashes
were verified again after analysis. No producer was signaled or modified.

| Continued segment checked | Steps | Worst final FS /MS ratio | Maximum iterations |
|---|---:|---:|---:|
| Mesh-nu0.3 fine N400,4001–5900 | 1900 | 6.1e-12 /4.2e-11 | 3 /3 |
| Mesh-nu0 fine N400,5001–7100 | 2100 | 6.2e-12 /4.1e-11 | 3 /3 |
| Mesh-nu0.3 fine N200,1101–2700 | 1600 | 1.0e-11 /3.2e-11 | 3 /3 |

Every final FS/MS row in these explicit segments passed its unchanged relative
convergence gate. These are segment-prefix checks, **not complete12800/6400-step
studies**, whole restart-chain acceptance, periodicity, physical accuracy or
error-budget qualification. Earlier original segments retain their separate
evidence; the ongoing later tails are excluded.

The24-file,one-part2383288-byte archive includes the frozen analyzer/parser,
native snapshots, byte-exact log prefixes, individual reports, and the full
readonly progress-reader dependency chain. It also preserves the static
controllers for two queued captures: complete L24/L12 samples and their length
comparison, and the independent S96 alpha1 coarse member. Those waiters do not
prove their future inputs or results have completed.

[Summary](summary.json), [queued-capture scope](capture-preparation.json),
[raw manifest](manifest.json), [archive hashes](archives.json), and
[ordinary Git byte verification](index-staging.json) bind the evidence.
The executable commands and source hashes are in the archive. The part is a
regular100644 Git blob; its retained D-drive copy is not a pointer substitute.
No new solver build, numerical rerun, upload or qualification claim accompanies
this inspection.
