> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Tube mesh interpolation screen: no PDE solve

Six meshes were examined offline at repository checkpoint
`4fc5002db03ce3b72c8b86d4af6b29ef6fce5fc5`. The relevant mesh/reference/analysis
sources are unchanged from `2189a8c`; their exact hashes are in `report.json`.
R=1, L=2, rho=mu=1, pressure-gradient amplitude .01. The analysis uses the
complex Womersley velocity at alpha=1 and 2, its P1 nodal interpolant, and
positive order-4 Gauss/Duffy tetrahedral quadrature on each actual polygonal
domain. System Python3.12, NumPy1.26.4 and SciPy1.17.1 were used; no solver,
MPI job or new dependency installation was involved.

## Measured interpolation quantities

Errors below are percentages. They are **not numerical-solution errors,
best-approximation errors or bounds on circular-domain geometry error**.

| Seed sectors/radial/axial; red level | Nodes | Tetrahedra | Alpha1 interpolation | Alpha2 interpolation | Minimum / median tet quality |
|---|---:|---:|---:|---:|---:|
| 48/8/16; 0 | 6545 | 34560 | .755234% | .831558% | .273866 / .672757 |
| 48/8/16; 1 | 49137 | 276480 | .248471% | .274394% | .160496 / .504090 |
| 48/12/24; 0 | 14425 | 79488 | .496068% | .526353% | .273866 / .710134 |
| 48/16/32; 0 | 25377 | 142848 | .411018% | .427212% | .273866 / .681419 |
| 96/8/16; 0 | 13073 | 69120 | .559151% | .645770% | .174664 / .487260 |
| 48/4/8; 2 | 91905 | 516096 | .186213% | .214038% | .160496 / .390638 |

The tetrahedron mean-ratio quality is
`12*(3*V)^(2/3)/sum(squared_edge_lengths)`; an equilateral tetrahedron has
value1. The archive retains minimum, fifth percentile and median.
Different seeds are separate mesh families; this table does not establish
a nested-mesh convergence rate. The last row uses the exact mesh of the
currently running fine study, not a newly generated replacement.

For diagnosis only, `report.json` also records the volume mean of
`a_time^2/(a_time^2+a_visc^2)` at zero advection, where
`a_time=2/(2*dt/3)`, `a_visc=4/(6*V)^(2/3)` and `dt=(2*pi/4)/N`.
This measures the temporal contribution inside the default BDF2 tau formula;
it is not a field-error estimate. At N200 it is .0808095 for the 49137-node
mesh and .0350045 for the 91905-node mesh. No time-step or stabilization
qualification follows from either value.

The screen identifies possible cheaper mesh families for subsequent actual
studies. No new family has been selected as a qualified substitute; neither
runtime nor accuracy of a PDE solution was measured here.

## Reproduce and verify

Actual command, from the repository in Ubuntu24.04:

```sh
/usr/bin/python3 build/prod48-20261107/screen-tube-interpolation.py
```

`original-screen.py` preserves the helper exactly as executed. It contains
the original absolute study directory and infers the repository from its
location; redirect these two paths and choose a fresh output directory before
replaying elsewhere. The current fine mesh is included in the archive, so it
can be supplied without rerunning that solver. The helper's `base` case files
are generator side effects, not cases that were solved.

`manifest.json` identifies all34 raw files. Every file was read back from
`meshes-and-interpolation.tar.xz` and SHA256-verified. `archive.json` records
5597956 bytes and SHA256
`83059af46a946245d39ca66935c5db2f268cc488222d7d17ce09bd2f599983ef`.
The report and original helper are also provided outside the archive.
