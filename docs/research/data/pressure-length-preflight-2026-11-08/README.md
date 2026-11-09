> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Matched-mesh L24 startup verification

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

At source `fa9646d`, [66 files](manifest.json) were read back and hashed from
two archives totaling 28609752 bytes; [archive identities](archives.json)
include the frozen controller, inputs, meshes, outputs and executable hash.
The command was `/usr/bin/python3 -u build/prod48-20261107/run-pressure-length24.py`.
The [dated scope](scope.json) separates this completed preflight from the
still-running 6400-step dynamic study.

The S24/level1 mesh doubles length12 to24 and axial seed12 to24, preserving
the local mesh. Translating the central interval [6,18] by -6 gives exactly
the short tube's 20736 fluid and 13824 solid tetrahedra, checked using all
tetrahedron coordinate sets. The long mesh contains 8281 fluid nodes/41472
tetrahedra and 7056 solid nodes/27648 tetrahedra. [Provenance](provenance.json)
binds these checks to actual mesh and input hashes.

Both three-step runs use frozen b072, PETSc3.23.7, one rank and identical
load/time/stopping criteria. Default SuperLU_DIST and explicit MUMPS with
`-snes_lag_jacobian -2` have positive convergence reasons and correct clocks.
Their [final fields](preflight.json) differ by at most2.843434e-25 nodally;
the largest normalized mass RMS difference is1.268526e-23, passing the
declared2e-9/1e-8 limits. Only final fields, not all intermediate states,
were compared. Local times73.353/42.746s share a guest-reported core group with CPU18;
they are not a scaling result.

The EON-only dynamic study uses N200,16 ramp cycles,32 total cycles, and
saves the final three cycles. It runs on CPU19 under
`elastic-budget-analysis.lock`, then releases that lock before waiting for
the matched L12 audit. No dynamic L12/L24 result exists in this capture.
Length changes fluid inertia as well as end distance; its total dynamic
difference must not be labeled purely a clamped-end discretization error.
The existing2% Lamé mean gate remains, without inventing a new dynamic gate.
