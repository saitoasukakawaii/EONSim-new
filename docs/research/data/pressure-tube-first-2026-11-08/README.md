> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# First actual elastic-tube pair and affected checks

Source checkpoint2eabb47 repairs the reader; numerical source2189a8c adds the
optional fluid tau-time diagnostic, and the actual EONSim elastic calculation
uses frozen b072cc8. Reference svFSI is pinned at
7bdb74cdd517310d6bf32c0bb7d42072aeac8658, unchanged. PETSc3.23.7 is the main lock.
These results do **not** qualify PROD-02 or the elastic tube.

## Completed numerical checks

The preserved `acceptance` archive contains the exact commands, Release/Debug
environment/build/linkage/CTest receipts, selected raw outputs per configuration,
both coupled logs and the original failed reference audit. Each build ran only
`fluid_stabilization_time`: Release1/1 in2.78s, Debug1/1 in3.31s. The discrete
derivative maximum is2.12e-16 across BE/BDF2/alpha; MPI and restart differences
are2.78e-17. A changed tau-time value changes the spatial operator while default
behavior remains equivalent in the tested case. No old-version or full-suite
claim follows from these checks.

The explicit stage-pressure uniform test completed100steps. Maximum speed,
pressure range, endpoint recurrence and stage error are respectively
3.18e-15,5.40e-13,5.45e-13,1.45e-13 (all below1e-9). This establishes the
adapter's discrete pressure clock, independently of elastic accuracy.

## Actual coupled outputs and reader failure

Both programs completed600steps, six cycles at100steps/cycle, on the same
12-sector coarse geometry (fluid325nodes/1296tets; solid312nodes/864tets).
R=1, Rout=1.2, L=12, E=1000, nu=.3, both densities1, viscosity1,
P=.02+.01sin(t), clamped solid/ALE caps, free outer wall and reference-config
linear elasticity. Both runs use one rank and their own generalized-alpha
scheme with rho_infinity=.5. Actual cases and meshes are archived.

The first reference audit failed because the pinned writer explicitly stores
reference positions as Float32. Physical arrays are Float64. The original
manufactured fixtures used Float64 positions and missed this storage contract.
The fix matches the exact binary32 serialization of each input node, rejects
collisions/unmatched coordinates/topology and uses original input geometry for
integrals. It does not widen geometric or physical tolerances. Six unit checks,
including one-ULP and collision rejection, passed; independent VTK fixtures
cover both coordinate types without changing physical fields.

`fixed-reader` contains the unchanged-field reanalysis, both fixtures,
comparison and exact analyzer source. Both solvers pass interface/clamp,
positive Jacobian, stage-mass and divergence-theorem checks. EONSim/svFSI
maximum stage net flux is6.51e-18/2.28e-15. Neither is periodic: last-cycle
solid velocity differences are.04662/.04652 on the prescribed fixed scale,
far above1e-5. The comparison therefore explicitly reports ineligible.

Observed mid-pressure amplitude/phase differences are4.9021%/2.6578degrees,
above2%/1degree; radial/area amplitude differences4.8677%, end-flow amplitude
differences3.8860%/4.0739%. These last-cycle observations are not accepted
periodic comparisons. Both mean radial responses differ by8.3153% from the
infinite circular plane-strain Lamé value, before geometry/finite-end budgets.
No fitted phase shift, changed pressure gauge or relaxed acceptance gate.

## Replay and provenance

From the original repository root, with `work` denoting
`/home/tfblab633/EONSim-prod48-20261107`:

```sh
/usr/bin/python3 build/prod48-20261107/reaudit-first-elastic.py
/usr/bin/python3 build/prod48-20261107/capture-first-coupled.py
```

These helpers require fresh destinations; do not overwrite historical runs.
Original commands inside each archive are the exact execution record.
The capture helper reads every archived file back and checks size/SHA256
against `manifest.json`; all3423files passed. `archives.json` supplies their
archive hashes. No solver binaries or third-party sources
are duplicated here; the accepted binary hash and pinned build provenance
remain in receipts and the earlier[import evidence](../svfsi-import-2026-11-07/README.md).
Warmup duration, space/time/tail/sampling, geometry, MPI and restart still need
their own production-study evidence. Articles remain drafts; no push/PR yet.
