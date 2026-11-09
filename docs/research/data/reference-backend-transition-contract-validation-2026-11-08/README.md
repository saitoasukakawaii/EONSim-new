> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Explicit reviewed backend transition provenance

At base27f5c82, the restart auditor adds an opt-in v2 chain. Every segment must
declare its executable digest. The supported transition changes only the FSI
preconditioner from FSILS to the pinned Trilinos-ILUT implementation with
Trilinos assembly disabled. Physical inputs, mesh, pressure tables, timestep,
tolerances and production output grid remain identical. Default v1 chains
continue to reject implicit backend changes.

The transition binds the original/candidate binary digests, exact case and
native rank layout,100-state original/candidate comparison,10-state exact
candidate replay, raw independent-review hashes, unchanged source, convergence,
clean resource receipts and the predeclared10% cost gate. It preserves the exact
preceding native seed and explicit excluded original tail. A short proof does
not qualify the resulting long trajectory; all full convergence/field/budget
checks still apply. No production handoff was performed by these tests.

The complete actual late-ramp raw proofs and independent reviews are now in
[this archive](../reference-trilinos-native-recovery-proofs-2026-11-08/README.md).

Final Linux validation36128 completed14:09:48UTC on shared CPU15/nice19,
2GiB/swap0 with zero memory events and an empty scope.23 reference and8 pressure
tests pass. Both actual reviewed fine serial and two-rank late-ramp proofs bind
successfully to the proposed unchanged production inputs; the original S12
v1 full6400-step chain still passes. Commands and frozen source accompany
[Linux report](linux-final-report.json). C++ binaries were not rebuilt or retested.

The first Windows run passed19 existing checks but one of four new checks
rejected its own short-path alias TFBLAB~1. Canonicalizing evidence paths fixes
this identity mismatch and rejects duplicate aliases. All four affected Windows
tests then pass; [report](windows-final-report.json) and
[first failure summary](windows-first-failure-summary.json) distinguish captured
tool-output facts from raw logs. The first Linux23+8 run also remains archived.

The first capture rejected a Windows-root input outside the helper's declared
evidence roots. The retry copied those three small files byte-for-byte into its
own research directory, preserving both copies and the failed capture record;
the helper's path checks were not relaxed. Final capture:78 files/one part/63840
bytes. [Manifest](manifest.json) and [Git readback](index-staging.json) retain
actual bytes, including both frozen source revisions. Final source SHA:
feb097ede2ad2a7a1a6e063d6fab4f7fcbdfd4c21e14e2dc7968517191671527;
test SHA442b906a972ede440dacd2f58ca6fbd1718ceb58d1edc130084a59b5ebd45eef.
