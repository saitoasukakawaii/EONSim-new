> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S96 alpha2 N400 trajectory and N200-target budget

The native serial family completed all2400 N400 steps, six cycles and its
matched N200-target analyses at19:48:31 UTC,2026-11-08. Full capture finished
23:03:10 UTC. All84 ordinary Git archive parts have now passed complete byte
readback. This preserves the original outcome: **the N200 velocity sampling
budget fails**, although analytical and periodic metrics pass at both time
resolutions. The new N400-target budget using N800 is a separate running study.

| Last-cycle diagnostic | Fine N200 | Fine N400 | Existing limit |
|---|---:|---:|---:|
| Velocity relative L2 error | 0.475825763% | 0.471077545% | <1% |
| Pressure RMS / amplitude | 0.360074480% | 0.336758859% | <1% |
| Flow amplitude error | 0.234326215% | 0.181696731% | <1% |
| Flow phase error, degrees | 0.060445160 | 0.056303977 | <1 |
| Maximum net flux | 1.0871986e-17 | 1.2420362e-17 | <1e-10 |
| Last-period velocity / pressure field difference | 4.9457e-15 /5.5243e-15 | 6.3479e-15 /6.1552e-15 | <1e-6 each |

All entries in that table pass their gates. They do not override the required
budget below, whose denominator and target belong to N200.

| N200-target field | Last spatial relative RMS | Time / space | Tail / space | Sampling / space |
|---|---:|---:|---:|---:|
| Velocity | 0.003011999724 | 0.073911408 | 2.1661e-13 | **0.115648791 FAIL** |
| Pressure | 0.008512214043 | 0.079631443 | 2.7650e-13 | 0.040999521 |

Every term must be strictly below0.1. Five pass, but velocity sampling consumes
11.5648791% of its final spatial difference. The complete family therefore
records `eligible:true, passed:false`. The coarse N200 flow-amplitude failure
also remains in its separate complete archive. No criterion was relaxed.

The independent N400-target study recomputes its own same-resolution coarse/fine
space difference and uses a fresh six-cycle4800-step N800 time control. Those
future results cannot be substituted into this old budget. N800 itself does
not gain independent spatial qualification merely by being the finer time grid.

This3323-file,84-part3591041640-byte archive contains every retained N400
current/history state, cycle receipts, meshes, inputs, frozen source, commands,
logs and the complete family analyses/resources. Every resource returned0 with
swap0, zero memory events and an empty owned group. Earlier full N200 and coarse
trajectories are SHA-linked through the [summary](summary.json), not replaced
by pointers or copied selectively. The executable is identified by its exact
60eb SHA; ELF files are excluded under the existing source/build evidence rule.

The84 parts are regular100644 Git blobs. Two intermediate local storage commits
contain1–29 and30–58; the remaining26 parts and complete metadata are finalized
only after all parts have passed readback. This controls commit size without
dropping raw evidence. Retained D-drive copies do not substitute for Git bytes.

[N200 analysis](n200-analysis.json), [N400 analysis](n400-analysis.json),
[time comparison](time-n200-n400.json), [space comparison](space-n200.json),
[N200 sampling](sampling-100-200.json), [N400 sampling](sampling-200-400.json),
[N200 tail](tail-n200.json), [N400 tail](tail-n400.json), [budget](budget.json),
[raw manifest](manifest.json), [archive hashes](archives.json), and
[whole-archive Git byte verification](index-staging.json) bind the outcome.
The [next target's reviewed preparation](../womersley-s96-n400-budget-refinement-retry2-2026-11-09/README.md)
and [N800 capture waiter](../n800-capture-and-l24-retirement-2026-11-09/README.md)
describe their own limited scopes. No numerical rerun, upload, PR or full
project qualification accompanies this storage completion.
