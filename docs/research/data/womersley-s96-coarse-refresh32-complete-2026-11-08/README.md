> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S96 coarse alpha2 study

The level0 S96r8a8 N200 study reaches1200 accepted steps and completes its
six-cycle analytic and cycle5-to6 comparisons. It uses the coefficient-aware
LU refresh binary, window32 and four ranks on CPU21. Full outputs, histories,
mesh, partition, commands, source and analyses are retained:4153 files in
7 parts,122,618,240 bytes. Archive member hashes and actual Git blob readback
are separately recorded in `manifest.json`, `archives.json` and `index-staging.json`.

Velocity/pressure relative errors are0.691816%/0.679231%; flow-amplitude error
is1.058047% and fails the unchanged1% gate. Last-period field changes pass.
This completed coarse trajectory does not establish fine-grid or whole-project
qualification. Its retained histories later serve as the independent MPI
comparison for the separately recorded native-serial coarse study.

The first fine controller failed before partitioning/solving when it observed
the producer's resource lock released before its completed status was published.
That original failure is included; later retries use separate directories.
Parts are ordinary Git blobs, with D originals retained and no required duplicate
files in the sparse checkout. No PR/push or relaxed physical gate is implied.
