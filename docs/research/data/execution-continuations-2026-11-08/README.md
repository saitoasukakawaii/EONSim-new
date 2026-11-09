> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Explicit checkpoint continuations

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

This is a dated execution checkpoint, not a completed long-study claim.
At2026-11-07 21:52:37UTC, [116 files](manifest.json) were captured in two
archives totaling10372592bytes and read back against their original hashes.
[Archive verification](archives.json) records exact source roots, skipped ELF
hashes and controller sources. The source checkout was054b64a with the
optional standalone-fluid metadata changes still uncommitted.

The completed S24/level1/N400 confirmation uses the same frozen b072 executable
(SHA2562692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12),
PETSc3.23.7 and complete accepted checkpoint400. Both modes run steps401–403
on CPU22 after the original numerical process exits; other numerical jobs
remain on different guest-reported core groups. Commands, input hashes, all accepted
clocks and positive solver reasons are in [the report](report.json).

| Mode | Three-step wall seconds | Final maximum nodal difference | Largest normalized mass-norm difference |
|---|---:|---:|---:|
| Default SuperLU_DIST | 21.886264465 | 0 | 0 |
| MUMPS, step-local Jacobian lag=-2 | 14.335186361 | 7.45389e-20 | 1.12140e-17 |

Both field limits (2e-9 nodal,1e-8 normalized mass norm) and the predeclared
20% local cost reduction are satisfied; measured reduction is34.50%.
Only the final fields are compared. This is a bounded local measurement,
not a general performance or scaling claim.

The original EON process was deliberately interrupted after the durable
checkpoint400 was verified. Its log includes accepted steps401/402, which
are recomputed from400 in the new study. Original inputs, checkpoint,
output, command and planned interruption receipt remain archived. At21:48:12UTC
the explicit `elastic-s24-l1-n400-ramp16-c32-mumps_chord-m400` continuation
started with unchanged physical data and tolerances. It will reach12800steps,
retaining three sampled cycles. The reference continues in the original
S24 directory. Cross-program analysis must join those two actual paths.

The [state snapshot](summary.json) also preserves the pending Womersley400
boundary controller and alpha1's empty fine-output storage mapping. At this
snapshot the original Womersley numerical ranks are still running and only
their Python scheduler is held. Its separate four-core comparison has not
run, and no block3 long-study adoption is claimed here. Live continuation
logs and live reference fields are excluded from this immutable capture.

Long-run periodicity, mesh/time/geometry/end budgets and production MPI/restart
qualification remain open. Original failures and physical thresholds stand.
