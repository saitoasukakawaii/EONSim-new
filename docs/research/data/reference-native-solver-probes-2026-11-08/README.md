> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Rejected reference solver feasibility probes

Two bounded trials changed only the selected pinned svFSI linear solver option,
under one shared low-priority CPU and2GiB/swap0. Both reached their600s limits:
NS/BIPN completed only about9 states with repeated conditioning warnings;
RCS completed no state. Neither provided the required20-state convergence and
field proof. Neither was adopted, and original production solvers continued.

All failed-run logs, inputs, outputs, source, commands, resource receipts and
definitions are retained in158 files, one6,671,580-byte archive. Resource scopes
were emptied after timeout; failure remains distinct from numerical success.
`archives.json` and `manifest.json` record member hashes, and `index-staging.json`
verifies the actual ordinary Git blob bytes. No speedup or physical-agreement
claim is made from these failed probes.
