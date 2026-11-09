> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Alpha1 driver retirement — actual process-control fixtures

Five isolated synthetic-process scenarios passed: an active segment, natural
child completion while the driver is held, an idle boundary, stubborn children
requiring bounded cleanup, and an injected failure before retirement. The last
case resumes the same driver and leaves the original waiting task alive. Every
scenario verifies that an unrelated process continues and that a committed
retirement cannot launch a new segment.

Only the exact extracted handoff functions act on fixture-owned PIDs, bound to
their start identity and session. No production process received a signal.
The fixture completed in 8.655825856 seconds with 85,270,528-byte peak memory,
2 GiB/zero-swap limit, zero memory events and an empty scope. Its 81 files are
preserved in one 20,304-byte lossless part.

The real alpha1 checkpoint screen is still running. This evidence validates
process handling only, and neither permits a solver handoff by itself nor
constitutes numerical or physical qualification. A concrete family definition,
full numerical readback and separate handoff review remain mandatory.

- [Completed fixture scope](summary.json)
- [Every fixture file](manifest.json), [part hashes](archives.json)
- [Complete ordinary Git blob](part001.tar.xz)
- [Actual index verification](index-staging.json)
