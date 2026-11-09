> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Independent mesh-nu0 N200 backend proof

The actual two-rank native checkpoint100 was continued through200 with the
original FSILS backend and with the fixed upstream Trilinos FSI-ILUT backend.
The latter was replayed from190 through200. The complete110 compared states,
five nodal fields and P1 mass norms, every rank's native current/history records,
saved equation norms, times, inputs, sources, logs and resource receipts are
preserved in561 files/11 parts/283180048 bytes. This is an **early-ramp local
execution proof**, not full-load or long-period physical qualification.

The screen completed at22:05:46 UTC; separate raw-data self-review completed at
22:13:37 UTC,2026-11-08. The executing agent performed that separate review;
it is not an external reviewer. Both report eligible=true/adopted=false.
The original production process continued during the proof. Subsequent
native600 handoff decisions and actual execution belong to separate evidence.

| Measurement | Result |
|---|---:|
| Original100 steps | 1501.603722845 s |
| ILUT100 steps | 902.451790098 s |
| ILUT/original elapsed ratio | .60099197702319 |
| ILUT10-step replay | 98.278060453 s |
| Maximum backend nodal difference | 1.7618285303e-19 |
| Maximum normalized P1 mass RMS | 5.2222660669e-17 |
| Maximum native algorithm-state difference | 2.7511630127e-17 |
| Saved equation-norm difference | 0 |

Original restoration matched the actual historical200 checkpoint algorithm
bytes exactly, apart from recorded elapsed time and unused rank padding.
The candidate replay also matched exactly under that same explicit rule;
native saved times were exact. The backend comparison is numerical agreement,
not bitwise agreement. All final equation residuals met their unchanged limits.
Each numerical mode and the independent review used a2GiB cap,zero swap,
zero memory events and an empty scope at completion. CPUs14/16 were shared,
nice19: this local cost result does not establish isolated-host performance.

The original binary SHA256 is
`f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf`;
the candidate is
`121678f9b7a84e2ae07e5061468fbeffb39cd0468d1141517bb5dd2d816a34e3`.
Both use the pinned svFSI upstream source. Geometry, material values, timestep,
nonlinear/linear tolerances and mesh solver are unchanged within each pair;
only the reviewed FSI backend selection changes.

The first preparation check mistakenly retained checkpoint_interval when
comparing the N200 and N400 scale contracts. It failed before any numerical
screen. The corrected check explicitly verifies the factor2 relationship
for dt,steps and checkpoint interval, then compares every remaining physical
value exactly. No actual study input or gate was changed. The
[original preparation record](screen-preflight-history.json) is retained.

See [screen report and commands/resources](screen-report.json),
[separate full raw review](review-review.json),
[input binding](review-static-input-check.json), [complete manifest](manifest.json),
[archive hashes](archives.json) and [ordinary Git byte readback](index-staging.json).
[Previously archived source/build proof](../reference-trilinos-serial-proof-2026-11-08/README.md)
is bound by hashes and ordinary blob identifiers in [summary](summary.json).
All11 parts are regular100644 Git content; retained D files are not pointers.
No whole-project acceptance, upload, PR, merge or article publication is claimed.
