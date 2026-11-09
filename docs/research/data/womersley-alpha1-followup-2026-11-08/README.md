> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Alpha1: completed level1/N100 and level0/N200 studies

Frozen b072cc8, PETSc3.23.7, default stabilization, four ranks restricted to
CPU10–17. The alpha1 controller/source snapshot originates at0b9e980;
capture checkpoint054b64a preserves exact hashes. Both studies use the same
48-sided seed, BDF2, two warmup cycles and three sampled cycles,100 phases
per cycle. These are separately completed studies from a still-running queue.

[3126 original files](manifest.json) were read back from five archives totaling
110327840bytes. [Archive/executable hashes](archives.json), frozen sources,
commands, accepted-state receipts, meshes, partitions, all sampled checkpoint
states and analysis logs are retained. The executable is omitted by content
type and identified by its exact digest; no raw result was deleted.

| Diagnostic | level1 / N100 | level0 / N200 | Gate |
|---|---:|---:|---:|
| Velocity relative L2 error | 1.66523% | 2.29153% | <1% |
| Pressure RMS / amplitude | .668879% | 1.58464% | <1% |
| Flow amplitude error | .0511967% | 2.46513% | <1% |
| Flow phase error | .0495306degrees | .127672degrees | <1degree |
| Maximum absolute net flux | 5.23266e-14 | 1.73555e-13 | <1e-10 |
| Last-two-cycle field periodicity | pass | pass | <1e-6 |

Full values and numerical-library versions are in
[level1/N100](womersley-a1-s48-l1-n100-analysis.json) and
[level0/N200](womersley-a1-s48-l0-n200-analysis.json).
The two columns differ in both space and time resolution; their difference
cannot be attributed to either one alone. The level1 velocity gate still
fails, and all three level0 amplitude/field gates fail. Periodicity and global
mass do not establish accuracy. Fine-level, time, geometry, tail and sampling
budgets remain separate and incomplete. No MPI scaling or full Womersley
qualification is claimed. The earlier
[level0/N100 six-cycle evidence](../womersley-alpha1-first-2026-11-08/README.md)
is preserved separately, not rerun for this capture.
