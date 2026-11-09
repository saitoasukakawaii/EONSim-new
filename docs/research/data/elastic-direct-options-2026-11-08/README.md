> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bounded elastic direct-solver and step-local chord screen

At054b64a, the frozen b072 executable was run from the same complete
S12/level1/N200 ramp16 checkpoint1400 for steps1401–1403. Meshes, physical
case, time history, accepted-step criteria and stopping tolerances are
unchanged. Only explicit PETSc direct-solver/lag options differ.
Both MUMPS and serial SuperLU are available in the pinned PETSc3.23.7 build.
The ordinary direct path uses SuperLU_DIST.

[103 original files](manifest.json) were read back from one7841216-byte
archive, with [hashes](archives.json). They include the original controller,
exact accepted state, meshes, frozen field readers, per-mode commands/logs
and all short-run outputs. The excluded executable's exact hash is retained.

| Mode | Total seconds | Maximum final nodal difference | Largest normalized field norm |
|---|---:|---:|---:|
| Default SuperLU_DIST | 17.9562 | 0 | 0 |
| MUMPS | 11.1938 | 1.30105e-17 | 5.42341e-15 |
| Serial SuperLU | 60.1280 | 2.16841e-17 | 8.44452e-15 |
| MUMPS, lag=-2 | 6.63337 | 3.46945e-17 | 1.20943e-14 |

[Full report](report.json) preserves all three accepted clocks, positive
SNES/KSP reasons, positive endpoint geometry, iteration counts and timing
components. The final third-step fields are compared against the ordinary
direct path. Each mode passes both predeclared criteria: maximum nodal
difference below2e-9, and each of the five physical-scale-normalized consistent
P1 mass norms below1e-8. This comparison does not claim that every intermediate
output was independently compared or that long-cycle accuracy is established.

The process uses logical CPU21 while reference work occupies its physical
sibling CPU20. Their logical affinities are disjoint and recorded, but these
are concurrent local observations, not isolated-core or general performance
results. The selection rule requires at least20% lower local total cost plus
both field checks, then a separate S24 fine-grid confirmation before any
explicit continuation. No running study is modified by this probe. The later
checkpoint400 confirmation/continuation is not part of this completed package.

Lag=-2 rebuilds at the first Newton evaluation and reuses that Jacobian within
the current step. EONSim creates a new SNES per accepted-step solve, so this
does not reuse a Jacobian across physical time steps. No C++ modification or
additional unrelated regression was needed for these existing runtime options.
