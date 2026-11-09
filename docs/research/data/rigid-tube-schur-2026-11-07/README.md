> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Steady tube: Schur refinement and field gates

Local evidence only; the complete PROD-02 transient/elastic qualification is
still in progress. Solver source: `c218c18c7b11396ed177d91c631a278bdf0cb2a9`.
Runner: `b072cc81e29160488e5c08044d8aee3b0245078f`.
The frozen Release binary SHA256 is
`f7e694748f37dbaaed15096f7b140c96eddaadac66d5bc78eac38e2677c82613`.
The dependency environment is the repository PETSc 3.23.7 lock, Ubuntu 24.04
WSL, one host, at most four MPI ranks. These are accuracy results, not a
performance or multi-node scaling study.

## Problem and unchanged criteria

Radius 1, length 2, density/viscosity 1, pressure drop .02; no-slip wall,
zero transverse velocity and axial pressure traction at each end. The
stabilization, nonlinear tolerances (`rtol=1e-11`, `atol=1e-13`, maximum 30)
and existing Schur/GAMG tolerance remain unchanged. The larger Krylov restart
and iteration budgets below only permit more work before failure.

All errors below are percentages. Velocity and volume pressure norms use the
actual polygonal domain; the circular analytical flow is a separate reference.

| Seed sectors/radial/axial | Nodes | Flow | Velocity L2 | Pressure RMS/drop | End drop | div RMS/(Umean/R) |
|---|---:|---:|---:|---:|---:|---:|
| 96/24/48 | 112945 | .133114 | .189354 | .218287 | 3.087918 | 1.467790 |
| 96/48/96 | 447073 | .048834 | .164996 | .101786 | 1.899080 | .733242 |
| Prespecified limit | — | 1 | 1 | 1 | 2 | 1 |

The finest grid has 2,626,560 tetrahedra. Its net outward flux is
`2.38015411931386e-16` (limit `1e-10`), and the independently evaluated
divergence-theorem defect is `1.5746323267901247e-17`. All six finest field
criteria pass; the preceding grid fails the end-pressure and divergence gates.

The first 96/24/48 attempt stopped with `DIVERGED_ITS` after the default 500
Krylov iterations, residual `2.446172668461508e-8`. That failed directory is
preserved. A fresh run with restart 120 / maximum 2000 converged with 539+86
iterations. The finest grid used restart 120 / maximum 4000 and converged with
1012+187 iterations, final nonlinear residual `9.93657707411516e-14`.

## MPI/reference scope

The 48/4/8 pilot (1737 nodes) was actually run with Schur on 1/2/4 ranks and
compared node by node with the historical direct solution. All 95 files in the
historical reference archive were hash-verified before reuse. Maximum field
differences are `5.652110723897152e-13`, `2.514551067367421e-13` and
`3.832437839301761e-13`; the limit is `2e-9`.

There is **no** finest-grid direct solve or 1/2-rank result in this archive.
Fixed 96-sector radial/axial refinement is not uniform angular h refinement;
no asymptotic convergence order is inferred. The geometric flow bounds are
reported in `summary.json`, separately from field errors. No transient,
elastic, patient-specific or large-scale qualification follows from this data.

## Reproduce and inspect

Use the locked Release executable and MPI environment described in
`scripts/cloud/run.sh`. In a new output directory, the successful finest run is:

```sh
python scripts/study_rigid_tube_seed.py --executable /path/to/eonsim \
  --work /new/steady-schur-finest --seed 96 48 96 --ranks 4 --schur \
  --krylov-restart 120 --krylov-iterations 4000 --timeout 21600
```

Use seed `96 24 48` and maximum 2000 for the preceding successful run. The
pilot uses seed `48 4 8` with each rank count and the default Krylov budgets.
Every archive contains the actual `run.json` command and solver log, case,
mesh, original VTU fields, geometry metadata and, for successful runs, summary.
Rebuildable partition HDF5 and unused generator meshes are omitted.

`summary.json` contains numerical gates and archive hashes; `manifest.json`
contains byte sizes and SHA256 for every archived member. All 78 members were
read back from the six archives and hash-verified. After extracting into a new
directory, the same analysis can be replayed without solving:

```sh
python scripts/study_rigid_tube_seed.py --analyze-only \
  --work /extracted/steady-schur-finest --seed 96 48 96 --ranks 4 --schur \
  --krylov-restart 120 --krylov-iterations 4000
```

Analysis of the original fields was executed. Extraction/hash verification was
executed. A second full field-analysis pass on the extracted largest archive
has not been executed; it is not needed to claim the hash identity.
