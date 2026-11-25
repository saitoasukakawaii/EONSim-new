# FSI runtime, partition and output optimization

## Scope and execution order

This work continues `codex/fsi-performance-runtime` from merged PR #52 / main
`2dcb06c26a0359175e4f5a771d5bbff6dfc928af`. The first runtime commit is
`47237a033820b53ceb19003d032bb50f70994bb0`.
The user explicitly requires source completion and remote synchronization before
running validation, followed by a PR merge after the required checks pass.
Every source fix follows that same order. The locked environment is PETSc 3.23.7
Release; no default full-suite, Debug or legacy-version rebuild is added.

## Implemented changes awaiting execution

| Area | Change | Preserved contract |
|---|---|---|
| ALE tangent | 24 velocity/mesh AD directions plus four exact pressure columns | Complete cross-field and geometric derivatives, SUPG/PSPG terms |
| Sparse insertion | Compact physical blocks for ordinary AIJ, dense fallback for reordered aliases | Independent test/trial maps and contribution summation order |
| Element workers | One persistent OpenMP team across bounded batches | PETSc/MPI remain on the main thread; collective failure cleanup |
| Residual finalization | One fresh unprojected final residual provides reactions and projected acceptance | No cached acceptance residual; owned and ghost reaction values |
| Initial tangent | One-use first Jacobian reuse, then deferred numeric assembly in retained Schur sessions | New numeric Jacobian and USER Schur for each Newton state; invalidation on evaluation/failure/options changes |
| Partition construction | Stable cell/face buckets, owner prefix sums, single fingerprint | Existing default METIS result, numbering, source order and HDF5 schema |
| Explicit cost balance | Physical-tag-to-positive-integer costs supplied to METIS | No guessed material costs; weighted partition identity guards mixed shards/restarts |
| VTU | Compact boundary points, optional appended binary, optional boundary omission | Stable 64-bit IDs, topology, field components, physical tags and PVTU references |

## Runtime controls

- `-nonlinear_initial_jacobian_reuse false` retains the independent startup
  Jacobian assembly for a controlled comparison. The default is true only for
  eligible ordinary Newton sessions; nondefault or lagged solver policies retain
  their existing behavior.
- `-solver_rank_report` also enables `-solver_report`. It reports each rank's
  callback, failure synchronization, ghost, assembly and linear time together
  with owned/ghost counts and actual Jacobian/Schur work. Existing report maxima
  are independent rank maxima and must not be added as disjoint phases.
- `-partition_cell_weights 1:4,2:1` applies explicit costs when using offline
  `-prepare`. Unspecified cell tags cost 1. This is an example syntax, not a
  recommendation for fluid/solid cost ratios. Positive integer range, total
  range, duplicate and unknown tags are checked before writing partitions.
- `-partition_report` reports METIS, layout and write time, per-rank cells,
  owned/ghost nodes, boundary faces, tag counts and assigned costs. These timings
  start after source mesh input; `total_seconds` is the prepare function scope.
- `-vtu_format ascii|binary` keeps ASCII as the default and offers standard VTK
  appended raw binary with little-endian data and UInt64 block lengths.
- `-vtu_compact_boundary false` restores full local point sets in boundary
  pieces for comparisons. The default keeps only nodes referenced by boundary
  cells, preserving their original local order.
- `-vtu_boundary false` omits companion boundary pieces and their PVTU index.

`jacobian_assemblies` counts completed physical tangent assemblies,
`jacobian_callbacks` counts SNES requests, and `initial_jacobian_reuses` counts
the one-use startup reuse. `user_schur_updates` counts this application's nodal
USER matrix construction/refresh, not PETSc's internal `PCSetUp` calls. For
nested KSP/PC event costs use a separate, explicitly logged `-log_view` sample.

## Verification and measurement status

At this source-preparation checkpoint, new compilation, tests and benchmarks
have **not run**. Planned gates include exact pressure derivatives, actual
second-batch threaded faults, Schur lifetime/refresh controls, MPI topology and
weighted partition identity, and independent VTU decoding. Source and benchmark
drivers are pushed before execution. Actual commands, source SHAs, failures and
results will be recorded in
[`docs/research/data/fsi-runtime-2026-11-26`](../research/data/fsi-runtime-2026-11-26/README.md).

The performance claim will distinguish paired wall time from phase timers,
retained-session controls from baseline-to-candidate changes, and default ASCII
from opt-in binary output. Cost weights are user inputs rather than measured
universal speedups. Multi-node, GPU, nonmatching interfaces and a universal
optimal preconditioner are outside the implemented and measured scope.
