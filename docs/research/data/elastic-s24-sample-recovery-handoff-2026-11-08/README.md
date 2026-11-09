> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 sample recovery and revised reference handoff

This archive preserves283 verified files in3 ordinary Git archive blobs,
27683596 bytes. Source checkpoint: `abec003`. Every part was read back from
the actual Git index and matched its declared SHA256.

The old EONSim controller completed all accepted steps401..11600 successfully,
then failed its requirement that logicalCPU22 and23 both be free. The already
authorized independent reference run occupied23. Its dependent budget waiter
also exited failed. Both failures, the original frozen controller, complete
available warmup output, current11600 native history and original inputs are
retained. Warmup had output_interval0; this archive does not invent field
files for steps that were never written.

The fresh sample controller uses the same2692 binary, case, dt, tolerances and
MUMPS/chord options. Actual11600→11602 and11600→11601→11602 runs compare exactly:
22 HDF datasets across the two states, all saved histories, legacy v3 clock,
five nodal fields and normalized P1 differences are zero. Independent review
verified clean2GiB/swap0 scopes before allowing11601..12800 sampling onCPU22.
Shared guest sibling23 is explicit; no physical-core isolation, performance,
v4 clock or final physical qualification claim follows.

The revised reference handoff was independently reviewed after the old budget
failure. A new consumer binds the recovered EON path and prospective reference
continuation with unchanged error-budget arithmetic. The original reference
received `results/STOP_SIM=4000` for a normal accepted-step boundary. At the
captured snapshot it was still computing with the original solver; candidate
adoption had **not** occurred. No signal was sent to the original reference
solver or the already exited budget waiter. The shared init.scope must never
be signaled.

Growing1200-step sample output, future native4000 adoption and subsequent
reference results are deliberately outside this immutable archive. See
[sample proof](sample-proof-result.json), [independent sample review](sample-review.json),
[sample adoption](sample-adoption.json), [revised handoff review](handoff-review.json),
[normal-stop request](native-stop-request.json), [preserved budget failure](old-budget-failure.json),
[archive list](archives.json), [member hashes](manifest.json) and
[actual Git byte verification](index-staging.json).
The earlier checkpoint400 execution change is preserved in
[execution continuations](../execution-continuations-2026-11-08/README.md);
normal-stop and same-analyzer proofs are in
[the preceding archive](../reference-native-stop-and-handoff-preparation-2026-11-08/README.md).
