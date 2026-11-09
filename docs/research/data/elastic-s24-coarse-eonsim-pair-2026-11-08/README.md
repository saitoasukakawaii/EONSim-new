> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S24 coarse EONSim trajectory and cross-program pair

Both original coarse N400/ramp16/32-cycle trajectories completed12800 steps.
EONSim completed its1200-state audit at10:21:54UTC; the reference had already
completed its full convergence and saved-field audits. Observable and400-phase
cycle32 field comparisons are now complete. This is a completed comparison,
not physical acceptance.

EONSim five-field periodicity passes (maximum6.28e-7), with zero kinematic
defect, stage mass4.55e-18 and positive Jacobians. Reference ALE periodicity
remains about2.2113e-5, above1e-5. Mean Lamé errors are3.195039% EONSim and
3.195042% reference, above2%. Mid-pressure amplitude difference3.112885%
also exceeds2%; phase difference0.872130degrees passes1degree. The unchanged
prerequisites make comparison_eligible=false. Finer grids and each program's
separate time/tail/sampling budgets remain required.

Capture33659 completed13:43:03UTC:4931 files/20 parts/153452668 bytes.
Actual Git byte readback passed13:55:51UTC at27f5c82. The archive retains the
full EONSim trajectory, checkpoints, meshes, commands, frozen source and final
cross-program analysis. The reference is bound to the existing
[complete reference archive](../elastic-s24-coarse-n400-reference-2026-11-08/README.md),
whose manifest SHA is recorded in [summary](summary.json).

See [EONSim audit](eonsim-audit.json), [observables](cross-code-observables.json),
[fields](cross-code-fields.json), [member manifest](manifest.json) and
[ordinary Git blob readback](index-staging.json). Original field definitions,
physical scales, phase conventions and numerical tolerances are unchanged.
