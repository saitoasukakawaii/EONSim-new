> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Actual fine native restart proofs for the reference backend

Two bounded experiments compare the unchanged pinned reference with its built-in
FSI Trilinos-ILUT preconditioner, assembly0. Mesh FSILS/CG, physical parameters,
pressure history, timestep, convergence tolerances and rank count stay fixed.
Both use actual late-ramp checkpoints; neither is a full-load parallel or
long-cycle qualification. Earlier serial full-load S12 proof is retained
[separately](../reference-trilinos-serial-proof-2026-11-08/README.md).

| Experiment | Original100 seconds | ILUT100 seconds | Ratio | Replay10 seconds |
|---|---:|---:|---:|---:|
|Fine mesh nu.3, native serial2800→2900|2035.326083|1485.136532|0.729679899|148.146062|
|Fine mesh nu0, two ranks2600→2700|1839.648800|1407.776664|0.765242074|175.832042|

Each original100 run reproduces the actual original endpoint algorithm bytes.
The candidate's last10 states replay exactly, excluding only each rank's
elapsed runtime and non-state direct-record padding. Saved time is exact;
the reference does not use EONSim's v4 compensated clock.

| Maximum candidate/original difference | Serial | Two ranks | Gate |
|---|---:|---:|---:|
|five-field nodal|1.683e-16|2.012e-16|2e-9|
|normalized consistent P1 mass RMS|3.818e-14|3.164e-14|1e-8|
|all native Yn/An/Dn history|5.304e-14|6.614e-14|2e-9|
|saved equation norms|0|0|2e-9|

Every equation/step meets the unchanged strict printed relative1e-10 rule.
Two-rank records explicitly retain unequal local node counts4225/3600 and
their actual padded record layout; equal file size alone was not accepted as
partition evidence. The serial record has6625 nodes. Both candidates clear
the predeclared10% local-cost gate, but performance applies only to these shared
WSL placements: serialCPU16 and parallelCPU10/16, nice19,2GiB/swap0. All numerical
and independent-review resource groups ended empty with zero memory events.

Independent raw reviews34564/34585 completed12:04:48/13:10:22UTC. They re-opened
all110 compared states per problem, five fields/P1 norms, full native histories,
actual original endpoint restoration, exact input changes and source hashes.
The review is a separate execution/readback by the same implementing agent,
not an external human review. No producer was interrupted or backend adopted.

Pinned upstream commit7bdb74cdd517310d6bf32c0bb7d42072aeac8658. Original binary
SHA f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf;
candidate121678f9b7a84e2ae07e5061468fbeffb39cd0468d1141517bb5dd2d816a34e3.
Full fixed upstream source/build is in the earlier serial-proof archive;
ELF files here are identified by hash instead of duplicated.

Capture36093 completed14:15:03UTC:1104files/26parts/565348664B. Every member
was read back, then actual ordinary Git blobs were verified14:21:09UTC at
16aa5db. [Summary](summary.json), [serial screen](fine-serial-screen.json),
[serial review](fine-serial-review.json), [two-rank screen](two-rank-screen.json),
[two-rank review](two-rank-review.json), [manifest](manifest.json) and
[Git receipt](index-staging.json) accompany all inputs, raw outputs, commands
and frozen review code. Explicit full-chain transition validation is
[separate](../reference-backend-transition-contract-validation-2026-11-08/README.md).
