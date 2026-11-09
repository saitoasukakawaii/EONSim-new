> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pinned reference backend: bounded serial proof

Fixed upstream svFSI `7bdb74cdd517310d6bf32c0bb7d42072aeac8658`, unchanged
source; local base1374b625. System Trilinos13.2, Release flags and exact
compiler/link commands accompany the archived source and build logs. Original
binary f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf is unchanged.
Candidate121678f9b7a84e2ae07e5061468fbeffb39cd0468d1141517bb5dd2d816a34e3
is not adopted. ELF binaries are identified by SHA; source/build evidence is retained.
Capture completed11:00:24UTC:973files/5parts/127,695,968bytes, all archive
members read back and matched by SHA. Actual Git blob readback is separate.

Only the FSI linear preconditioner changes from FSILS to built-in Trilinos-ILUT,
with Trilinos assembly disabled. Mesh CG, physical input, pressure tables and
all tolerances remain unchanged. Output controls add every-step native states.
The upstream ILUT zero-diagonal handling requires measured evidence, not an
assumption of equivalence based on the preconditioner name.

| Completed check | Original seconds | Candidate seconds | Result |
|---|---:|---:|---|
|20-state startup, explicit same-build FSILS versus ILUT|588.202296|340.256496|ratio0.5784684942|
|actual full-load S12 seed6000→6020|265.064113|127.283612|ratio0.4801993405|
|candidate6010→6020 replay|—|63.782413|exact algorithm bytes except elapsed|

All five fields, normalized P1 mass, complete Yn/An/Dn, saved equation norms
and exact native time were independently read back. Mature candidate maxima:
node1.8388069e-16, mass4.5457445e-14, history3.1856462e-14, norm difference0.
Original recovery reproduces20 actual original fields exactly; replay10
is bitwise identical excluding elapsed. Every selected FS/MS step satisfies
the original strict printed relative criterion below1e-10.

Runs used one WSL logical CPU16, nice19, shared workload, one MPI rank and
single-threaded libraries. Each solve had a2GiB/swap0 private scope; memory
events0 and no surviving members. Independent mature readback completed
10:53:00UTC in90.446409s, peak98,418,688bytes. These local timings do not
establish host-core isolation, scalability or long-cycle physical accuracy.

Capture includes completed source/build, inputs/oracles, full output/history
and independent reviews. It excludes the active two-rank screen and production
outputs. Full-run convergence provenance and all physical/error budgets remain
pending; there is no production handoff or publication claim.
