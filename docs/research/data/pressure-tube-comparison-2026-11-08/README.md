> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Elastic-tube comparison analysis checks

Repository checkpoint `7a344a9`; production auditor and solver sources remain
`2189a8c` and frozen `b072cc8`, respectively. These are independent analysis
checks and manufactured outputs, **not new PDE solutions or elastic accuracy
acceptance**. System Python3.12, NumPy1.26.4, SciPy1.17.1 and VTK9.6.1 were used.
The four exact helper files are included here and inside their raw archives.

## Observable comparison: five checks passed

`compare-pressure-audits.py` consumes two complete reports from
`scripts/audit_pressure_tube.py`. It checks case/mesh/physical identity,
the accepted time grid, unchanged quality limits, periodic fields and the
reported harmonics against the actual stored scalar samples.

The comparison uses the svFSI amplitude as denominator and the original
absolute phase; wrapped phase differences are in [-180,180) degrees.
There is no fitted time shift. The previously prescribed gates are retained:
mid-ring radial/area amplitude5%, mid-pressure amplitude2% and phase1degree,
each end-flow amplitude5% and phase2degrees. Radial/area phase is reported
without adding an unprescribed phase gate. An amplitude below1e-12 times its
declared physical scale cannot define a relative amplitude or phase pass.

Actual checks recover the known4% amplitude change, .01-radian phase change
and unit mean difference; correctly wrap179.5 versus -179.5 degrees; reject
changed cases, nonfinite values, false quality/period flags and stale harmonic
summaries. Existing manufactured dual-reader histories yield identical
pressure harmonics, but their zero motion/flow cannot pass response gates.
Manufactured input is explicitly marked and is ineligible for a physical pass.

The circular infinite-plane-strain Lamé mean response and2% limit are reported
as diagnostics, pending separate finite-end and polygon-geometry budgets.
Passing these pairwise observables would still not complete PROD-02.

## Complete field comparison: three checks passed

`compare-pressure-fields.py` reads actual domain fields through the audited
EONSim/VTK readers. It verifies each input mesh by regenerating the declared
red refinements from the coarse mesh, including nodes, tetrahedra and boundary
tags. The independent affine patch checks the interpolation. Consistent P1
mass integrals on the finer reference domains give five field norms, both
cycle RMS and maximum phase RMS. Common phases must be actually stored;
there is no time interpolation or pressure-gauge adjustment.

Both fluid and solid affine fields reproduce within1e-12; the constant vector
(.05,-.02,.01) has exact volume-mean squared norm.003. Incorrect refinement
and changed boundary tags are rejected. Reading the existing48-snapshot
manufactured histories through both formats gives all five relative field
differences below1e-12. An unaligned seven-phase request is rejected.

These are reference-coordinate field comparisons. Across different ALE
algorithms they are not values at identical current spatial positions and
must not be called Eulerian physical-field equality. Within each program,
the same definitions support its spatial/time/tail/sampling study. Pairwise
differences are not automatically labeled as a particular error source.

## Fixed reference mesh algorithm differs

At svFSI `7bdb74cdd517310d6bf32c0bb7d42072aeac8658`,
`Code/Source/svFSI/MESH.f:CONSTRUCT_MESH` adds the previous displacement to the
element coordinates, subtracts it from the new displacement, then calls
`LELAS3D`. It uses the quadrature weight without the Jacobian multiplier used
by `CONSTRUCT_LELAS`. The prepared mesh equation uses Poisson ratio.3.
EONSim `src/physics/fsi_element.cpp` instead assembles vector Laplace
extension on the fixed reference geometry. The physical solid in both cases
uses reference-configuration linear elasticity, but the artificial internal
mesh operators are not identical. Their effect on actual periodic solutions
has not yet been measured; no gate is relaxed because of this distinction.

Pinned source hashes:

- MESH.f: `5f1f00e1bfa7ad5c979680b3739ff77cc2d0e46f7e496bb487ac4daeb6fb6d3d`
- LELAS.f: `fb69a80f1a5d1bf9e438c62c3f54d276b90c89c4bc46b24b9374db30fff5eedb`

## Commands and evidence

Actual commands, from the repository in Ubuntu24.04:

```sh
/usr/bin/python3 build/prod48-20261107/check-pressure-comparison.py
/usr/bin/python3 build/prod48-20261107/check-pressure-field-comparison.py
```

The helpers infer the repository from their original `build/prod48-20261107`
location. The check scripts also contain the original external work directory;
restore the [prior manufactured fixtures](../pressure-tube-audit-2026-11-07/README.md),
copy the four helpers to that repository-relative location, redirect the work
path and choose fresh output directories to replay elsewhere. No solver is
needed for these checks. Each helper's `--help` shows the actual-result inputs.

For the future real same-case result:

```sh
python build/prod48-20261107/compare-pressure-audits.py \
  --eonsim /path/eonsim-elastic-audit.json --svfsi /path/svfsi-elastic-audit.json \
  --output /new/cross-solver-observables.json
python build/prod48-20261107/compare-pressure-fields.py \
  --left-case /path/coarse/case.json --left-work /path/coarse \
  --left-audit /path/coarse-audit.json \
  --right-case /path/fine/case.json --right-work /path/fine \
  --right-audit /path/fine-audit.json --output /new/field-difference.json
```

Actual coupled comparison is still pending. All28 raw files were read back
from the two archives and SHA256-verified; `manifest.json` and `archives.json`
record exact bytes and hashes. No public push or PR at this checkpoint.
