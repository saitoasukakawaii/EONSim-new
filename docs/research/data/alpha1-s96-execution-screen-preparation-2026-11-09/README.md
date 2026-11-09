> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Alpha1 S96 fine execution-screen preparation

This18-file,one-part2103340-byte archive contains the frozen controller,
separate reviewer, complete source subset, actual mesh, case and resource
guards. At capture22:36:13 UTC,2026-11-08, the screen waited outside all resource
locks for the existing S48 alpha1 family and new S96 alpha1 coarse study.
**No new fine numerical result, cost eligibility or long-run adoption exists
in this preparation archive.**

The planned32-state modes are four-rank/window8,native-one-rank/window32 and
four-rank/window32, with expected actual LU counts5/2/2. Each uses the same
60eb coefficient-refresh binary, alpha1,S96r8a8level1,N400 timestep,6GiB cap
and zero swap. Admission requires22GiB available and running global margin8GiB.
It takes the existing direct-memory,MPI and option-probe locks only after
both dependencies complete. The native mode uses CPU0; four ranks use0–7.

Eligibility requires complete current/history comparisons for all1440 HDF
datasets across the three pairs, node error<2e-9,normalized P1 mass<1e-8,
exact v4 time/metadata, positive convergence and the expected actual LU counts.
A candidate must reduce elapsed time by at least10% against both alternatives.
The inherited P1 velocity scale .02/(4*12) is six times smaller than this
L2 case's Poiseuille scale .02/(4*2), therefore stricter; it is not the analytic
production RMS normalization. A separate raw reviewer is queued. Neither
controller automatically adopts a long study or loosens any physical gate.

[Definition](screen-definition.json), [capture scope](summary.json),
[manifest](manifest.json), [archive hashes](archives.json), and
[Git byte readback](index-staging.json) bind the exact inputs.
The ELF executable is omitted as specified by the evidence policy; its exact
hash is recorded and its accepted source/build proof already exists.
The [coarse preparation and prior N200 diagnostic](../alpha1-next-grid-preparation-2026-11-09/README.md)
retain the S48 alpha1 velocity error1.0164446% above the1% gate.
This archive is not periodic, spatial, temporal or sampling qualification.
