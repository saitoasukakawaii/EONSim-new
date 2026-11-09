> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Accepted clock compensation in checkpoint v4

The production N400 restart exposed a missing piece of algorithm state:
`TimeStepper` used compensated time summation, but checkpoint v3 did not
store the correction and `restore` reset it to zero. Physical fields still
agreed within their tolerances, while183 of400 restarted clocks differed,
including a final2.842170943040401e-14 difference. The earlier contract
promised tolerance-level replay, not bitwise clocks. The stricter production
clock check is retained, and v4 now supports it explicitly.

This is a modification of base `6f202a1`, not a claim that that commit
already contained the fix. [Exact tested source hashes](source.json)
identify the implementation: v4 saves time, next step and summation
correction in the manifest and HDF clock. All six physics drivers save and
restore it. Legacy v3 remains readable with an explicit missing-correction
diagnostic and zero fallback; v1/v2 remain rejected. Missing legacy
floating-point history cannot be reconstructed.

PETSc3.23.7, WSL Ubuntu24.04, Debug and Release each passed these8 checks:
`time_integration`, `checkpoint_publication`, `checkpoint_publication_mpi`,
`restart_block_verification`, `ale_time_verification`, `scalar2d_time`,
`scalar_p2_restart`, `time_retry_verification`. CTest elapsed times were
233.16s and192.24s respectively. MPI checks include1/2/4 ranks as specified
by the individual test; P2 restart remains1/2 ranks. All numerical checks
used one logical CPU and single-thread libraries for correctness only.
There was no full-suite or historical-PETSc run.

The archived controller executes the repository entry point:

```text
bash scripts/cloud/run.sh 3.23.7 release explicit /home/tfblab633/EONSim/.cloud /home/tfblab633/EONSim-prod48-20261107/clock-checkpoint-validation-6f202a1/release-tests.json
bash scripts/cloud/run.sh 3.23.7 debug explicit /home/tfblab633/EONSim/.cloud /home/tfblab633/EONSim-prod48-20261107/clock-checkpoint-validation-6f202a1/debug-tests.json
```

The independent [reader checks](reader-checks.json) use an actual completed
four-rank Womersley step600 snapshot. A separately converted v4 fixture
reads identically to v3; correction mismatch, clock-size mismatch,
metadata-version mismatch and a nonfinite manifest are rejected. Original
snapshot hashes are unchanged. This does not add a new PDE trajectory.

[10464 files](manifest.json) were read back and hashed from the archive.
The1,468,504-byte archive has SHA256
`f706f832865d2a5a1dd2fe89ce4527e6d1db851f8fb0c44627917dec63b95980`.
[Archive metadata](archives.json) records the two omitted ELF binary hashes.
[Actual test directories](actual-test-directories.json) include
`scalar-p2-restart` and `restart_verification`, whose names differ from
their CTest names. This avoids silently omitting their raw artifacts.
An archived resource receipt records moving only the low-priority capture
worker after it was starved; numerical affinity stayed unchanged.

A separate real-production replay has passed all400 exact clocks and
full HDF histories, and all400 restart field states. Its physical periodic
and quality audit also passed at23:53:06UTC. [Four exact follow-up
receipts](production-receipts.json) include the complete result summary,
clock/history comparisons and execution definition; they were copied
separately after the10464-file test archive. The larger production raw
archive is still being captured. This evidence does not qualify the unfinished production
space/time/geometry studies, cross-code comparison or rank4 trajectory.
