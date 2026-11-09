> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed S24 coarse N400 reference with failed ALE periodicity

The original mesh-Poisson-ratio 0.3 svFSI run completed all 12,800 steps and
the full field audit at 2026-11-08 08:45:10 UTC. The fixed upstream commit is
`7bdb74cdd517310d6bf32c0bb7d42072aeac8658`. The audit includes the actual
11,600 boundary state and all 1,200 saved states from 11,601 through 12,800.

Every printed final equation residual passes the original strict relative
tolerance: 25,600 FS/MS rows, maximum final ratios 4.1e-11 and 9.4e-11 against
1e-10. Kinematics, stage mass balance, the divergence theorem, and positive
Jacobian checks also pass. These checks do not establish physical qualification.

The ALE mesh-displacement cycle differences are **2.211333152140734e-5** and
**2.211282780069421e-5** for cycles 31 and 32. Both exceed the unchanged 1e-5
periodicity limit. The other four fields pass their periodicity checks, but
the aggregate result remains `periodic=false`. This run cannot supply a
passing periodic reference or a passing error budget. The separate mesh-nu0
series has a different mesh-motion definition and is not mixed into this series.

All 1,377 selected source, mesh, input, log, checkpoint, field, and audit files
are preserved in three ordinary Git archives totaling 109,010,096 bytes.
The still-running EONSim side of the shared study directory was excluded.
`manifest.json` records every member hash; `archives.json` records archive
hashes and completed extraction checks; `index-staging.json` records actual
Git-blob byte readback. The archive is complete evidence of this failed
periodicity result, not evidence of overall acceptance.

Commands and frozen audit sources are retained with the run. This capture
did not rerun numerical tests. The original controller 6673 is complete;
its queue continued with controller 29899 for S24 fine N200 on CPU20.
