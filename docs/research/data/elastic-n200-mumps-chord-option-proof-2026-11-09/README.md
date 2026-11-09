> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Elastic N200 same-state option proof

Complete356 immutable files in six parts (64292392 bytes), captured17:48:56UTC.
The archive includes all numerical modes, checkpoints/current-history, five-field
outputs, original input/seed, performance logs, independent review and its first
failed attempt. Executable bytes are identified by SHA; source evidence is retained.

Same1400 seed, frozen2692 binary, CPU16 shared/nice19,2GiB/swap0. Old-first8,
MUMPS/chord8, split4+4 and old-last8 were evaluated. Wall times170.780458337,
50.510200381 and161.065220538 seconds for the bracketing modes; candidate ratios
0.29576100727713567/0.3136009140414601 meet the original20% minimum reduction.
All24 paired states/264 HDF datasets passed: maximum history5.0923281976e-16,
node7.4593109467e-17, normalized P1 mass3.3598051376e-14, legacy-clock difference0.

First reviewer required MatLUFactorNum for SuperLU_DIST and failed; its log/resource
remain. SuperLU_DIST actually reports MatLUFactor16, MUMPS reports numerical8
(or4 in each replay segment). Fresh independent reader passed17:40:52 in78.776539s,
peak89337856 bytes, zero memory events, empty scope. This is bounded mid-ramp
execution evidence, not automatic adoption, exclusive-host benchmarking or full
physical qualification. No production tolerances or equations changed.

[Summary](summary.json), [screen](screen-report.json), [definition](screen-definition.json),
[independent review](independent-review.json), [first failure](first-review-failure.json),
[manifest](manifest.json), [archive checks](archives.json), [actual Git readback](index-staging.json).
All listed parts are ordinary Git blobs; the sparse local checkout keeps originals
on D without replacing archive contents with external pointers.
