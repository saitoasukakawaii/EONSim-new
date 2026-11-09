> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete alpha1 S96 coarse N400 study

This independent native one-rank member completed2400 steps, six cycles and
all analysis/tail jobs at22:51:35 UTC,2026-11-08. It uses S96r8a8level0,
6921 nodes/34560 tetrahedra,400 stored phases per sampled cycle and two warmup
cycles. The frozen60eb executable uses the explicitly selected MUMPS/chord
solver with LU reuse window32. Physical inputs and qualification limits are
unchanged; the earlier S48 failures remain separate evidence.

| Last-cycle metric | Measured | Existing limit | Result |
|---|---:|---:|---|
| Relative velocity L2 error | 0.7059441352% | <1% | PASS |
| Pressure RMS / amplitude | 0.8709598692% | <1% | PASS |
| Flow amplitude relative error | 1.4470282864% | <1% | **FAIL** |
| Flow phase error | 0.0596533544 degrees | <1 degree | PASS |
| Maximum net flux | 7.9697330e-18 | <1e-10 | PASS |
| Last two cycles, velocity / pressure | 4.0890e-15 /9.5769e-15 | <1e-6 each | PASS |

These are coarse-grid diagnostics. Periodicity and some analytical metrics
passing do not make the coarse member qualified, nor establish its matching
fine-grid space/time/tail/sampling budget. In particular, retain the flow
amplitude failure. The separate queued fine execution screen still needs actual
32-state comparisons and an independent raw review before any long fine study
can be adopted.

The study, analysis and tail resource receipts all returned0, with2GiB/swap0,
zero memory events and empty owned groups. Study wall time1667.157106123s and
peak301015040B describe a shared CPU14/nice19 run, not a hardware scaling or
performance comparison. Archive capture used shared CPU13/nice19.

The complete3279-file,12-part219475928-byte archive preserves all retained
fields and current/history, cycle receipts, inputs, meshes, frozen source,
commands, logs and clean resource receipts. ELF executables are identified by
their exact hashes; source and build provenance remain linked to the existing
coefficient-refresh validation. Capture finished23:02:36 UTC. All12 parts were
read back as ordinary100644 Git blobs against their SHA256 hashes before the
local commit; retained D-drive files do not replace repository content.

[Analysis](analysis.json), [tail comparison](tail-n400.json),
[producer completion](completion.json), [study definition](study-definition.json),
[controller definition](controller-definition.json), [summary](summary.json),
[raw manifest](manifest.json), [archive hashes](archives.json), and
[complete Git byte verification](index-staging.json) bind this result.
The [earlier preparation](../alpha1-next-grid-preparation-2026-11-09/README.md)
and [queued fine screen](../alpha1-s96-execution-screen-preparation-2026-11-09/README.md)
retain their narrower scopes. No new solver build, numerical rerun, PR or
whole-project acceptance is implied by this archive.
