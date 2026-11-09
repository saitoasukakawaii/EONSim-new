> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 fine N400: complete EONSim sample and recovered field audit

The numerical trajectory reached step12800. The complete final1200 stored states
(11601–12800, three periods,400 phases per period), their current/history fields,
the actual11600 boundary, inputs, commands, frozen sources and controller records
are sealed here. This is **not complete FSI-PROD-02 qualification**: matching
reference trajectories and each program's spatial/time/tail/sampling budgets
remain incomplete.

The capture contains **4995 files in143 parts,1420132176 bytes**. The numerical
source and binary identities are preserved in the frozen run definitions;
`6bce1276e14eda1f937a94a4c1156a502ee8058b` is the capture/audit preparation
checkpoint, not a claim that every trajectory used that source revision.

## Results and limitations

The bounded reader completed the full1200-state audit with an observed peak of
90243072 bytes,3313.361036 seconds,2GiB memory cap,zero swap,zero memory events,
return code0 and an empty scope. All raw input hashes remained unchanged.
The original audit was killed by its2GiB memory limit; that failure and its
failed consumers remain in this archive. No numerical trajectory was rerun.

| Check | Result | Original gate |
|---|---:|---:|
| Maximum five-field period difference, cycles31/32 | 2.4729777216e-7 | <1e-5 |
| Kinematic defect | 0 | <1e-12 |
| Stage mass defect | 9.5409791179e-18 | <1e-9 |
| Stage divergence-theorem defect | 9.3876276905e-18 | <1e-12 |
| Minimum solid/fluid Jacobian | .999977132168 /1.000004147989 | >0 |
| Mean radial displacement vs infinite plane-strain Lamé value | 1.2376125755% | <2% |

The mean radial displacement is .00010738165032703641; the analytical value is
.00010872727272727274. These passes concern this mesh and sampling window only.
Earlier coarse-mesh Lamé and reference ALE failures are not superseded.

## Reproduction and complete evidence

[Audit completion and exact command](audit-completion.json),
[complete field report](recovered-audit.json),
[accepted-step coverage](accepted-stage-checks.json),
[manifest](manifest.json), [archive hashes](archives.json), and
[ordinary Git blob readback](index-staging.json) bind the evidence.
Every listed part is an ordinary100644 Git blob; the local D-drive files are
retained originals, not substitutes for committed contents.

The earlier warmup trajectory and original restart-guard failure are in the
[complete warmup/handoff archive](../elastic-s24-sample-recovery-handoff-2026-11-08/README.md).
Its archives.json SHA256 is
`fd94c2d9b657d3d90ae1729449e1dbff782eebf1f1e1181c5f0278b3e61a0b03`.
The bounded-reader regression and exact coarse-report comparison are in the
[reader validation archive](../pressure-audit-bounded-memory-validation-2026-11-09/README.md).

This archival update runs no additional numerical tests or builds. Existing
unaffected tests are reused as documented in the linked validation evidence.
No upload, PR, merge or public article publication accompanies this checkpoint.
