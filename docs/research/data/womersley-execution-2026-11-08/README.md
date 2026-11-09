> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Womersley execution policy: preparation and metadata checks

Runner source `cfa5d3cd4d4c81ee56cec895a53678e9a6973b96` adds explicit
`--fluid-coo` and `--chord` options. The latter requires the Schur path that
preassembles a valid Jacobian before each new SNES solve. The options are
saved as `solver_options` in the immutable study definition; default studies
retain their original definition. No production C++ code changed here.

## Actually checked

The existing completed coarse N100 study was read with a six-cycle no-op
resume. Its definition, receipt, current checkpoint pointer, mesh digest and
attempt list remained unchanged. Adding COO or chord while resuming that old
study was rejected. Chord without Schur was rejected before loading a study.
Four checks passed, with `--mpiexec /bin/false` ensuring no MPI solve could
start. This is metadata/continuation validation, not numerical option validation.

Actual command:

```sh
/usr/bin/python3 build/prod48-20261107/check-womersley-execution-metadata.py
```

All7 raw files were read back from `metadata-check.tar.xz` and SHA256-verified.
The archive includes exact commands/logs, the helper and studied runner source.
`metadata-check.json` and `files.json` retain the identities and archive hash.
The check's output-directory suffix618260d is its starting repository checkpoint;
the copied runner hash identifies the subsequently committedcfa5d3c source.
Replaying requires redirecting the helper's original work path to the restored
completed coarse study and choosing a fresh check output directory.

## Prepared, not executed

Two helpers are included with `prepared-` names and distinct status in
`files.json`; place them under their original unprefixed names in
`build/prod48-20261107` to use them. Their CLI loading/syntax was checked;
**no option probe or real checkpoint fork has run at this evidence point**.

The probe takes the same immutable physical checkpoint and frozen executable
through three accepted steps under standard, COO, within-step chord and combined
options. It preserves original tolerances and requires positive convergence
reasons, finite accepted fields, unchanged clocks, owner/ghost consistency and
maximum field difference below2e-9. Timing and peak memory are diagnostic;
three steps are not a general performance or long-time accuracy qualification.
The helper acquires the existing numerical-queue lock itself; do not nest it
inside the locking run-python wrapper.

The fork helper refuses to copy a checkpoint unless a complete matching probe
has passed for the selected option and the actual source hashes still match.
It copies the mesh, partition, binary and complete accepted history into a new
sibling study, verifies every copy and records the original definition/probe
hashes. It never changes the old study and never starts a solver. A subsequent
resume must explicitly supply the new flags. The prepared MPI command check
accounts for the partition arguments that follow the solver options.

This restricted chord policy relies on EONSim's inspected Schur preassembly
and per-step SNES construction. PETSc3.23.7's
[SNES implementation](https://github.com/petsc/petsc/blob/v3.23.7/src/snes/interface/snes.c)
returns without rebuilding at lag -1; it does not create a missing initial
Jacobian. Neither arbitrary solver paths nor cross-step Jacobian reuse are
covered. The current fine study remains on its original standard path until
the scheduled accepted-state handoff and actual probes are complete.

The prepared fork was subsequently restricted to a checkpoint no later than
the declared warmup endpoint: copying a later single generation would omit
the sampled history expected by the analyzer. Optional `--phases` explicitly
changes only the new study's saved-phase cadence and must divide its unchanged
steps per cycle. This supports a proposed200-phase fine continuation and its
100→200 sampling audit. No such fork or denser numerical run has happened yet.
