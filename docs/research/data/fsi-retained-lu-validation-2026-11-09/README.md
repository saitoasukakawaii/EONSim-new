> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Optional FSI retained-LU validation

Completed 2026-11-09 01:42 UTC. The explicit `-fsi_lu_pc_reuse_window` option
defaults to zero and is restricted to linear elastic, periodic-pressure,
conforming dual-mesh generalized-alpha FSI. It reuses the existing explicit
MUMPS/FGMRES preconditioner. Current coupled residuals, field acceptance and
the selected per-step Jacobian policy remain active. All three effective time
coefficients control refresh; a rejected post-solve step clears the coefficient
marker. Restart does not serialize the LU factor.

Locked PETSc 3.23.7, actual command:
`scripts/cloud/run.sh 3.23.7 <release|debug> explicit <locked-state> <tests.json>`.
Both configurations passed three selected CTests: `fsi_lu_reuse`,
`fsi_pressure_state`, `fluid_lu_reuse`. CI selection checks passed 26/26.
The new check compares all five stored fields at 1/2/4 ranks, MPI solutions,
native restart, changing steps, an event, finite windows and rejected invalid
options. Actual PETSc LU counts for ten constant-step states are 10 default
versus 2 cached, including startup refresh. Window4, event and varying-step
sequences each perform four actual factorizations.

The separate full-HDF audit compared 1848 datasets per configuration, 3696 total.
Maximum current/history difference: `9.731798700229888e-15`; all v4 clocks and
time metadata exact. See [Release](release-histories.json),
[Debug](debug-histories.json), [summary](histories-summary.json),
[completion](completion.json) and [frozen sources](definition.json).
Existing pressure-state nonlinear retries pass; an actual geometry-rejected
cached solve was not separately triggered.

Release/Debug jobs took 213.852994248/207.916037714 seconds, observed peaks
513843200/369856512 bytes. All groups used 2 GiB/zero swap, zero memory events,
return zero and empty owned scopes. These shared-CPU validation times are not
production speed measurements.

Release SHA: `6993d7f29778524317de991af58af6287a3c9d813ba81337299f4089e0d611c9`.
Debug SHA: `2123b71659d78895d15907d9c1d5f23f59bfa43ff07f8bf510ef9e5eedb9ce4e`.

[Manifest](archives.json) preserves 8950 files, one 1433180-byte part; ELF files
are identified by hash. Current LU invocations contain their full raw results;
older fluid run directories are excluded using current.json. Existing
pressure-state outputs, build/CTest records and 21 source files are included.
[Git readback](index-staging.json) verifies ordinary Git bytes, part SHA
`f1fad8d6c029b1528df4a916ff646545d31c43e3cf19d15a21dbbcf395a397ca`.

This establishes tested numerical behavior only. The separate full-load S24
checkpoint cost/history screen is running. No production adoption, finer-time
qualification, scaling or performance gain is claimed. Original time-budget
failures remain unchanged.
