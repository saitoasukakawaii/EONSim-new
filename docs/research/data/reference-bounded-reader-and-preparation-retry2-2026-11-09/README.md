> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Exact bounded reference-reader review with the failed comparison retained

122 immutable files, one376324-byte part; full member and actual Git-byte
verification. The original1200-state reference history already belongs to the
[complete coarse reference archive](../elastic-s24-coarse-n400-reference-2026-11-08/README.md).
[Every input is SHA-mapped](raw-evidence-references.json) to that ordinary Git archive.

The bounded reader completed all1200 stored states from11601..12800. Its first
comparison failed because an in-memory cycle dictionary has integer keys while
the old JSON report has string keys. The complete new report was already saved.
The original reader receipt remains exit1: 335.850544305 seconds,
81088512 bytes peak,2GiB/swap0,zero memory events,empty scope.
The failed original controller and failed capture are retained verbatim.

A separate review read both serialized reports, reproduced the key-shape issue,
and verified every physical/quality value and all1200 rows exactly. Every old
convergence value is also exact; the only new metadata explicitly states the
full1..12800 range, no restart and no excluded tail. It rehashed all immutable
raw inputs without rerunning the field audit or numerical solver. That review
finished cleanly in6.442423139 seconds with12775424
bytes peak,2GiB/swap0,zero events and empty scope. Original ALE periodicity remains
**false**, including its old maximum2.211333152e-5. No physical gate is relaxed.

Three earlier reference producers still freeze the dense reader. New static
contingency plans bind their identities, inputs and sources, but launch nothing.
Only an actual audit OOM after complete numerical/native-chain evidence can
permit sealing inputs and reviewing a separate recovery controller. A planned
nu0 duplicate-directory guard failure is explicitly not such a trigger. Old
plans bound to the failed validation are preserved; v2 binds the separate review.

[Summary](summary.json), [targeted self-review](targeted-self-review.json),
[manifest](manifest.json), [archives](archives.json),
[actual Git readback](index-staging.json). The source review is by the executing
agent; no separate human/model review or completed project acceptance is claimed.
No core change, solver rebuild or repeated numerical test was needed.
