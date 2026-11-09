> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Alpha2 fine single-cycle diagnostic

The diagnostic freezes its source definition at2367903 and is archived at
d844e40. Unchanged analysis from the active f7bf9f3d executable study was
applied to the complete fourth cycle: accepted
steps601–800, all200 phases, 91,905 nodes and516,096 tetrahedra. The mesh is
S48/r4/a8 with two red refinements, N200, four MPI ranks, BDF2, default
stabilization, MUMPS/chord and retained-LU window8.

The [result](result.json) is a diagnostic, **not full qualification**. Velocity
relative L2 error is0.01046822249592082 (1.046822%), above the1% finest-field
gate. Pressure error is0.00196569459483794, flow-amplitude error
0.0050686455545440046, phase error0.09922716874403971 degrees, and maximum
net flux1.2990309037328764e-17. Three sampled cycles, periodicity and the
spatial/time/tail/sampling budgets remain separate requirements. No gate or
production source changed; the full six-cycle producer continues.

The immutable snapshot retains each rank's complete state/history HDF, VTU
mapping, case, mesh, definition and accepted-step receipt. HDF files were
hard-linked within D for read-only analysis; every before/after SHA256 in the
[snapshot manifest](snapshot-manifest.json) agrees. The archived tar members
store regular file bytes, so they can be restored without the original links.
The [definition](definition.json) records exact source and executable hashes.

Actual invocation: `/usr/bin/python3 build/prod48-20261107/diagnose-womersley-cycle4.py`
under Ubuntu24.04, followed by `capture-cycle4-diagnostic.py`. The frozen
controller and analyzer sources are included in the archive. The worker calls
the existing `Study.cycle(4)` and order4 metric implementation. Analysis
completed UTC05:38:11 on2026-11-08; [resource evidence](analysis.resource.json)
records138.517218742s, CPU17 at nice19, 2GiB memory/swap0, observed peak
1,320,521,728 bytes, no memory events, and an empty completed scope.

The [member manifest](manifest.json) contains1,023 verified files. The
[archive record](archives.json) lists20 parts totaling474,290,060 bytes;
capture completed UTC06:12:14. Parts remain locally on D to avoid duplicate
working copies. They are ordinary complete Git blobs, not path pointers:
[actual index readback](index-staging.json) completed UTC06:23:17, verifying
every full byte count, SHA256, mode100644 and sparse-worktree flag. The
[staging script](stage-external-archives.py) retains all D originals.
The command was native Python3.13 with
`build/prod48-20261107/stage-external-archives.py womersley-cycle4-diagnostic-2026-11-08`.
No push or PR accompanies this local preservation.
