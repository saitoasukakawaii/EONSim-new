> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Explicit replacement of waiting controllers

At base `08718b9`, the real v3/v4 segmented execution checks had passed.
Only waiting Python controllers15446/15457/7639 were cancelled after
checking their identities, states and lack of fine/N400 numerical work.
The alpha1 outer parent1180 was resumed by the old watcher's `finally`,
then claimed by the replacement. Its active middle child5422 retained
the same process identity and command. No running solver was interrupted
by this completed scheduler replacement.

The [dated snapshot](summary.json) records these successors:

- Main alpha2 watcher20754 waits for complete checkpoint600 and the
  uninterrupted603 reference. Only then may it stop the identified owned
  process group, retain the original output, verify a three-step v3
  restart against603, and fork cycles4–6 with one cycle per invocation.
- Alpha1 watcher20806 waits for the middle study's natural end. Its
  existing three-step accuracy/cost screen remains mandatory before the
  optional fine candidate; the future fine run uses one-cycle segments.
- N400 successors20817/20825 wait without holding the main numerical
  locks and follow the new producer statuses. Both keep the same binary,
  options, mesh and original qualification rules, with one-cycle calls
  inside the existing five-then-six-cycle execution plan.
- Reference-nu0 S24 queue20277 still waits for existing MPI/clock work.
  Its frozen three physical cases match the original family byte for
  byte. The pending serial/two-rank20-step screen is an execution check;
  its ramp0 fixture is separate from the32-cycle ramp16 studies.

Main alpha2 controller7542 is still running its original frozen source
until the accepted600 handoff. The new watcher has not yet interrupted
or replaced that numerical trajectory. The three-step restart, alpha1
fine screen, both N400 solves and the S24 nu0 family remain unexecuted
in this snapshot. Failure records and original sources are retained.

The archive contains exact old/new controllers, frozen dependency hashes,
process identities, cancellation and post-replacement receipts, wrappers
and prepared reference inputs. [114 files](manifest.json) were read back
and hash-verified; the385,680-byte archive SHA256 is
`5d8f78326e10014cdac255ea3f243390600672e78b7362bc7bf977b3adf3841a`.
See [archive metadata](archives.json). This is scheduler evidence, not
completed scientific qualification. No push or PR occurred.
