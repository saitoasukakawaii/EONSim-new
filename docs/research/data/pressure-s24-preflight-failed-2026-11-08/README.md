> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Preserved archive-verification failure

The original capture stopped at its regular-member assertion. Python's tar
writer had represented svFSI's `stFile_last.bin` as a hard link to
`stFile_005.bin` in the same archive. This is a valid source relationship,
not a numerical failure or evidence of corrupted fields.

[failure.json](failure.json) records the archive/source hashes and exact
member/target. The original archive, `original-capture.py`, and
[queue failure](queue-failure.json) are preserved without a successful
verification claim. The [separate corrected capture](../pressure-s24-preflight-2026-11-08/README.md)
uses dereference mode and verifies79 regular source members. Numerical solves
were not rerun; earlier completed N400/vector captures were reused unchanged.
