> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete cross-drive Git storage proof

Source checkpoint: `224aad53d012f8aa4c661b61089eb0b070ce16e9`.
55 immutable files in one265116-byte archive were captured at18:49:30UTC;
the real project index was byte-verified using the new D-store staging helper.
`index-batch-001-001.json` records staging; `index-staging.json` records complete
finalization. The part is a complete ordinary100644 Git blob.

The archive contains the isolated fixture's necessary Git metadata and objects,
the complete separate D object database, the independent clone's metadata and
objects, commands/results, first preflight failure, and actual store-adoption
receipts/source. Generated sample hooks and the junction itself are excluded;
the target blob bytes and relative alternate definition are preserved.

Commands executed: `validate-cross-drive-git-objects.py`,
`adopt-external-git-object-store.py`, `capture-git-cross-drive-proof.py`, then
`stage-external-archives-dstore.py git-cross-drive-storage-proof-2026-11-09
--first 1 --last 1` and the same archive with `--finalize`.
Windows Git2.39.2.windows.1 and WSL Git2.43.0 read the same complete payload.
The independent `--no-local` clone has no alternates and passes strict checks.
See [actual storage contract](../git-external-object-storage-2026-11-09/README.md).

This validates local byte preservation and independent Git transfer, not physical
acceptance or remote delivery. No numerical tests were rerun for this storage work.
