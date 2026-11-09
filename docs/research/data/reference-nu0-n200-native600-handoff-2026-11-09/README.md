> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Actual mesh-nu0 N200 continuation at native step600

The reviewed continuation actually began at22:51:40 UTC,2026-11-08, from the
original two-rank native600 state. This is evidence of a completed handoff and
the sealed original prefix, **not completion of the new6400-step trajectory**.
The source preparation used local checkpoint `fcc2956`; the evidence was
captured after local checkpoint `20d9f25`. No repository upload accompanied it.

The old solver honored its native `STOP_SIM` at600 and returned0 naturally.
All original producer, consumer and numerical identities exited or became
zombies before adoption. Its2GiB/swap0 group was empty, with zero memory events;
peak93605888B and7616.420802265s are the old segment's resource observations.
The original controller then truthfully failed because its frozen postcondition
expected `stFile_6400.bin`; its consumer also failed. Those failures and their
logs are preserved. They are neither OOM failures nor completed6400 studies.

The sealed1–600 prefix contains1200 final FS/MS rows. Maximum relative residuals
are5.6e-11 and9.3e-11, both below the unchanged1e-10 threshold. The exact native
seed has1419728B, two709864-byte rank records, step600 and saved time
18.849555921538826. Its SHA256 is
`a2917e245ce1b8e83dbe8faa5fda80078b2e4f793501063aecad7a99b9687701`.
Rank1's105000-byte padding is excluded from algorithm state, as established by
the separately validated native-record reader.

The new run retains the mesh, physics, time step, tolerances, target6400 and
output contract. It explicitly uses the independently checked121678 ILUT build
on two ranks, CPU10/12,2GiB/swap0, with10GiB admission and8GiB runtime memory
floor. Its newly routed budget consumer waits without holding the analysis
lock. The original N400 producer continues unchanged. The previously completed
coarse member is bound to its existing archive. The future N400 join requires
its complete numerical/audit evidence and the exact already-owned-directory
guard failure; another failure cannot be treated as that planned retirement.

The separate handoff self-review was performed by the executing agent, not an
external reviewer. It checked the actual two-rank native STOP proof, the complete
100-state backend comparison plus10-state replay, and the unchanged numerical
budget kernel. The [earlier backend proof](../reference-nu0-n200-ilut-backend-proof-2026-11-09/README.md)
remains an early-ramp result with `adopted:false`; actual adoption belongs to
this later receipt. It does not establish full-load or long-period accuracy.

This complete183-file,three-part7868104-byte archive includes the sealed old
prefix and failures, native600 seed, immutable continuation inputs, frozen
source, controller/consumer definitions and self-review. Growing new solver
outputs, resource receipts and consumer logs are excluded. Prior complete
coarse and proof archives are bound by hashes in the [summary](summary.json).

- [Actual adoption](adoption.json), [old completion](old-completion.json),
  [old resource receipt](old-resource.json), and [prefix convergence](prefix-convergence.json).
- [Handoff definition](handoff-definition.json), [family definition](family-definition.json),
  [separate self-review](independent-handoff-review.json), and [restart chain](restart-chain.json).
- [Raw manifest](manifest.json), [archive hashes](archives.json), and
  [complete ordinary Git byte verification](index-staging.json).

All three parts are regular100644 Git blobs, fully read back against their
SHA256 hashes. Retained external copies are not pointer substitutes. New full
history, periodicity, cross-program comparisons and each solver's error budgets
remain required. No thresholds were relaxed and no PR was submitted.
