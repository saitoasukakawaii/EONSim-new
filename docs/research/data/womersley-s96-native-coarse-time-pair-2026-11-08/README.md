> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S96 native coarse N200/N400 time pair

Complete alpha2, S96/R8/A8 level0 trajectories: N2001200 and N4002400
steps, six cycles, final three sampled. Frozen candidate60eb5cc0 uses native
one rank, MUMPS/chord, explicit LU window32.4,953files/17parts/335,118,176bytes
with full member readback retain current/history states, inputs, analysis,
the completed coarse MPI comparison and original failures. Fine outputs remain
active and are excluded. Exact source hashes and execution controls are archived.

| Metric | N200 | N400 | Gate |
|---|---:|---:|---:|
|velocity relative L2|0.691816%|0.615600%|<1%|
|pressure RMS/amplitude|0.679231%|0.542559%|<1%|
|flow amplitude error|1.058047% (fail)|0.518270%|<1%|
|flow phase error|0.136705deg|0.074227deg|<1deg|
|maximum net flux|8.2785e-18|1.0470e-17|<1e-10|

N400 last two same-phase cycles have field differences at most6.14e-15,
below1e-6. All six preliminary N400 gates pass; the original N200 flow failure
is preserved. [Summary](summary.json) records full_qualification=false.

At the200 common phases of cycle6, [same-grid time differences](time-n200-n400.json)
are U0.00163600936 and p0.00422570315 relative RMS. N400 cycle5/6 tail values
are6.38493e-16/2.35880e-15. These are budget numerators; fine-grid spatial
differences and independent time/tail/sampling ratios remain pending. No
budget denominator, sampling rule or acceptance limit was changed.

N400 completed10:22:34UTC, study wall2434.829914seconds, peak304652288bytes,
CPU15 shared/nice19 with2GiB/swap0; zero memory events and empty scope.
This is local execution evidence, not a host-core scaling measurement.
