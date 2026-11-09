> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Verified history reader and immutable follow-up definitions

This archive preserves 35 files in one 222,784-byte part. It contains the
completed alpha1 history-reader check, the queued actual-checkpoint screening
definition, and the running S96 coarse N400 companion's immutable definition.
It excludes their future checkpoint seeds, growing logs and simulation results.

The reader independently inspected 320 datasets from the already completed
alpha1 startup comparison: maximum nodal/current-history difference
5.427776067143397e-12 and normalized P1 mass difference 1.9164190833649605e-10,
below the unchanged 2e-9 and 1e-8 limits. Old v3 time is checked under its
existing approximate contract; only new-v4 versus new-v4 has exact full clock
equality. Source files were checked against commit8297a417 after the readback;
that order is explicitly recorded in the original definition.

The frozen reader divides velocity RMS differences by 0.02/(4*12), and
pressure RMS differences by 0.02. The actual tube has length2, radius1 and
viscosity1; its pressure-driven Poiseuille center-speed scale is 0.02/(4*2).
Thus the retained execution check uses a velocity scale six times smaller
than that center-speed scale. It is not the analytical velocity RMS used by
the production physical-error budgets. Neither the fixed screening scale
nor the original 1e-8 screening limit has been relaxed.

The real step200 alpha1 checkpoint screen is **queued, not passed or adopted**.
It waits outside resource locks for the original N400 completion, a genuine
original checkpoint200, and sufficient memory. The original alpha1 producer
and its N400 waiter remain unchanged. The S96 coarse N400 companion is a
separate six-cycle same-grid time comparison; the original fine-grid budget
arithmetic is unchanged and its numerical results are not in this archive.

`existing-input-references.json` maps byte-identical mesh/partition inputs to
the already verified members of
[the alpha1 startup archive](../womersley-alpha1-lu8-startup-2026-11-08/README.md).
`manifest.json` records every newly captured member. Executable hashes are
retained while ELF bytes are omitted under the existing source/build evidence
policy. `archives.json` records full extraction readback; `index-staging.json`
records actual ordinary Git-blob byte verification. No long-run qualification,
handoff approval, or numerical speedup follows from this preparation archive.
