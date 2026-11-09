> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Alpha1 bounded startup comparison

Three same-mesh eight-state runs compare the original vector path, new
default LU and cached LU on the predeclared CPU0..7/four-rank/14GiB/swap0
configuration. Times are1358.554362344,499.212951618 and184.667509988s.
Independent raw readback checks480 datasets; old/new absolute maximum is
5.4277765e-12 and default/cached maximum1.1540361e-12. New v4 clocks match
exactly; legacy time evidence retains its distinct contract.

This is startup eligibility only. The original long alpha1 producer was
neither stopped nor replaced; no full-study, restart-handoff or physical
qualification is inferred. The report, independent review, all raw fields,
commands, sources and resource receipts total189 files in7 parts
(106,014,248 bytes). Capture verifies every archived member. `archives.json`
and `manifest.json` give hashes; `index-staging.json` adds actual Git byte
readback. Parts are ordinary Git blobs; D originals remain, and the sparse
checkout need not contain duplicate part files.
