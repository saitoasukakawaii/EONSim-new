> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S12 level1 EONSim trajectory

The EONSim side completed6400steps and its full stored-window audit at
07:25:39UTC.32cycles, N200, ramp16;800 stored states5601..6400 and the actual
preceding5600 endpoint are retained. Warmup/sample commands, all accepted-step
logs, input meshes, current/history checkpoints and frozen analysis source
accompany the fields. This archive excludes the separate reference directory
and its still incomplete recovery/audits at capture preparation.

Provenance source_head is c49c69caff9fd63db19cf142a7959d889fa0aef6;
the frozen executable SHA is2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12.
The run uses the original native serial path on WSL CPU18, without later
fluid-only LU caching changes. Exact source, input and binary identities are
recorded in provenance; no new build or host-core isolation claim is made.

| Completed stored-window check | Maximum/minimum | Gate |
|---|---:|---|
|five-field same-phase periodicity, last two cycles|1.0130743e-6|pass<1e-5|
|kinematic defect|0|pass<1e-12|
|stage total outward flux|6.7220535e-18|pass<1e-9|
|stage divergence-theorem defect|7.1757323e-18|pass<1e-12|
|fluid/solid minimum Jacobian|1.00000411 /0.99997421|positive|
|mean displacement versus circular infinite plane-strain Lamé|4.802660%|fail2%|

The mean-response failure is preserved. Periodicity and conservation passage
do not imply full elastic qualification. Independent spatial/time/tail/sampling,
finite-end/geometry and cross-program requirements still apply. Saved-window
metrics do not assert fields that were not stored during warmup.

Archive completion, exact part sizes, member hashes and ordinary Git blob
readback are recorded in the accompanying manifests and staging receipt.
