> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pending runtime-limit correction and actual CLI checks

At `a7a177e`, [70 files](manifest.json) were read back from a25120-byte archive.
[Hashes](archives.json) preserve both old and replacement frozen controllers,
planned cancellations, input-guard fixtures and actual CLI logs.
[Dated states](summary.json) are snapshots, not completed trajectories.

Self-review found `--timeout172800` in the waiting N400 controller, while
the actual study CLI permits at most86400 seconds per numerical segment.
Neither waiting job had acquired the numerical lock or launched a solve.
PIDs7843/7849 were explicitly cancelled after checking their identities,
waiting states and absence of children. Old sources and cancellation
receipts remain; no active producer was interrupted.

New commands are `/usr/bin/python3 -u
build/prod48-20261107/queue-womersley-time400-bounded.py --alpha 2` and the
same with `--alpha 1`. PIDs15446/15457 wait without holding the producer's
lock. Each uses a legal86400-second segment limit, first completes N400
cycle5/step2000, then explicitly resumes the unchanged definition through
cycle6/step2400. The new output name ends `paired-a7a177e`.

[Eight real CLI checks](cli-checks.json), run by `check-time400-cli.py`,
cover both frequencies' initial five cycles, sixth-cycle continuation,
N200 fallback tail and the original invalid timeout. Legal parameters
reach a deliberately reserved directory/definition guard before any mesh
or solver is created. The old timeout is rejected by argument validation.
The checks pass because each expected guard is observed; their nonzero
process returns must not be mislabeled as successful numerical solves.

All analytic, periodic, quality and10%-of-space criteria remain unchanged.
Original7822 and subsequently cancelled7843/7849 must not be restarted.
The included running MPI, boundary-handoff and nu0 reference states are
context only. No fine N400 trajectory has run in this evidence snapshot.
