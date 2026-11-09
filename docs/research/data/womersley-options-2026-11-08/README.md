> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bounded Womersley execution-option probes

Actual3-step continuations from immutable four-rank checkpoints, with frozen
b072cc8 executable, locked PETSc3.23.7, unchanged physical residual/tolerances
and explicit positive SNES/KSP convergence. Coarse:1737nodes/8064tets, N100,
step600. Fine:91905nodes/516096tets, N200, step200. CPU-heavy audits waited on
the same queue lock, outside these timing probes. These are bounded local
observations, not scaling or general speedup claims.

|Screen|Mode|Wall seconds|Max final physical-field difference from its standard run|Result|
|---|---|---:|---:|---|
|Coarse original|standard|1.11870|0|passed|
|Coarse original|COO|.96704|8.67e-19|passed|
|Coarse original|lag=-1 and COO+lag=-1|.11416/.16413|not computed|PETSc option rejection|
|Fine COO|standard|158.79626|0|passed|
|Fine COO|COO|159.75247|1.35e-17|passed|
|Coarse corrected|standard|1.16950|0|passed|
|Coarse corrected|lag=-2|.71606|2.60e-15|passed|
|Fine corrected|standard|156.53721|0|passed|
|Fine corrected|lag=-2|148.06009|1.03e-14|passed|

Field limit2e-9 was fixed in the probe helper before execution. All fields,
owned/ghost agreement, accepted clocks and solver-report associations are
checked; exact commands, logs, original helpers, checkpoint copies and final
VTU fields are retained. Every failure remains in its own directory.

Fine COO did not improve end-to-end time and raised peak rank RSS from
1,186,082,816 to1,784,369,152bytes, so it was not adopted. Fine lag=-2 lowered
observed wall time by5.42% and peak rank RSS to992,702,464bytes, versus
1,184,391,168 in its standard run. This only supports a documented continuation
choice; periodic accuracy and longer-run behavior remain separately checked.

The original lag=-1 interpretation was incomplete. PETSc3.23.7's
[SNESSetFromOptions implementation](https://github.com/petsc/petsc/blob/v3.23.7/src/snes/interface/snes.c)
explicitly rejects -1 from the command line, even though the separate API can
express never-rebuild semantics. Source2eabb47 uses -2: build the first Newton
Jacobian, then reuse within that step. EONSim constructs a fresh SNES per step,
so this does not reuse across accepted physical times. Schur-only scope is
retained; default studies remain unchanged.

The handoff archive records the original fine job's complete step200
generation hashes, verified four-rank histories and planned SIGINT at
2026-11-07T17:24:14Z. This was a scheduling interruption, not nonconvergence.
The original study/attempt remains intact. The subsequent controller first
runs the accepted tau-time diagnostic at coarse N200, then explicitly forks
the fine study from200steps with200saved phases and the selected execution
policy. The fork requires the passed probe and unchanged source hashes.
It does not declare the numerical or physical study complete.

Exact replay uses the archived original probe with `--study`, `--restart-step`,
`--work`, `--steps 3` and `--modes`; see each `command.json`/`report.json` and
the preserved controller. Destinations must be new. `manifest.json` and
`archives.json` record raw-file and archive read-back verification. The helper
copies frozen binaries locally but excludes them from these public archives.
