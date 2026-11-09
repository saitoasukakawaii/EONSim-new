> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 fine N400 bounded audit — completed report evidence

The 12,800-step EONSim trajectory was already complete. Its new full audit of
states 11,601–12,800 finished at 2026-11-08 19:11:27 UTC without rerunning the PDE.
All immutable numerical inputs retained their original SHA256 values.

The maximum five-field phase difference over cycles 31 and 32 is
2.472977721614709e-7, below 1e-5. Kinematic defects are zero; stage mass is
9.540979117872439e-18 and stage divergence-theorem defect 9.387627690520927e-18.
Minimum fluid and solid Jacobians are 1.0000041479888504 and 0.9999771321682042.
Mean mid-ring radial displacement is 1.0738165032703641e-4 versus the circular
infinite plane-strain value 1.0872727272727274e-4: relative error
0.012376125754681944, passing the unchanged 2% mean-displacement criterion.

The audit took 3313.361035552 seconds, peaked at 90,243,072 bytes under 2 GiB
with zero swap, returned zero, recorded no memory events and left an empty
scope. The original full-window OOM and failed downstream jobs remain failures.
Reference comparisons and each solver's space/time/tail/sampling budgets remain
incomplete; this is not full FSI-PROD-02 qualification.

This archive contains all 34 audit metadata/source/log files (360,280 bytes in
one lossless part). It does not duplicate the numerical VTUs/meshes: their full
separate archive is still being captured by `bounded-audit-boundary-capture-current`.
The report hash is `433f0bd1ec9cba994fbbd57dc633851bceb4d9e0894ca1aeab6baa5db1f9cc87`.

- [Metrics and scope](summary.json)
- [File manifest](manifest.json), [archive hashes](archives.json)
- [Complete ordinary Git blob](part001.tar.xz)
- [Actual index byte verification](index-staging.json)
- [Original bounded-memory fix and equivalence validation](../pressure-audit-bounded-memory-validation-2026-11-09/README.md)
