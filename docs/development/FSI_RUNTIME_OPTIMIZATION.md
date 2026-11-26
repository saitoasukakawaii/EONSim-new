# FSI runtime, partition and output optimization

## Scope and execution order

This work continues `codex/fsi-performance-runtime` from merged PR #52 / main
`2dcb06c26a0359175e4f5a771d5bbff6dfc928af`. The first runtime commit is
`47237a033820b53ceb19003d032bb50f70994bb0`.
The user explicitly requires source completion and remote synchronization before
running validation, followed by a PR merge after the required checks pass.
Every source fix follows that same order. The locked environment is PETSc 3.23.7
Release; no default full-suite, Debug or legacy-version rebuild is added.

## Implemented and validated changes

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
- `-vtu_format ascii|binary|hdf5` keeps ASCII as the default and offers standard VTK
  appended raw binary with little-endian data and UInt64 block lengths.
- `-vtu_compact_boundary false` restores full local point sets in boundary
  pieces for comparisons. The default keeps only nodes referenced by boundary
  cells, preserving their original local order.
- `-vtu_boundary false` omits newly written companion boundary pieces and their
  PVTU index. It does not delete stale files at a previously used prefix.

`jacobian_assemblies` counts completed physical tangent assemblies,
`jacobian_callbacks` counts SNES requests, and `initial_jacobian_reuses` counts
the one-use startup reuse. `user_schur_updates` counts this application's nodal
USER matrix construction/refresh, not PETSc's internal `PCSetUp` calls. For
nested KSP/PC event costs use a separate, explicitly logged `-log_view` sample.

## Verification and measured results

Production source `7e8868e433fb0040806a6faf3ba8cd289a2aa3f1` was pushed before
execution. Clean PETSc 3.23.7 Release local selection passed **17/17**; source
CI actually ran and passed **48 Release checks plus 24 Python checks**.
Weighted-driver `3e366c8` ran one affected Release check and reused 47 compatible
historical results; its 21 Python checks passed. I/O parser fix `7d86f38` leaves
production C++ unchanged and reuses 48 Release results. Final evidence-only
checks retain these original execution identities.

Four FSI campaigns include **88 runs, 880 accepted steps and 1,760 true linear
corrections**. Independent replay checked fields/history, iterations, raw logs
and 8,502 file hashes. Maximum physical difference is 4.440892098500626e-16,
history difference 2.9841559419667343e-15; numerical gates were not relaxed.
The initial-J same-binary control gives exactly equal fields/history and
**30 → 20 physical Jacobian/USER updates** per ten-step run; paired wall
medians fall 12.06%–25.59% on these cases.

Default baseline-to-candidate results are mixed: assembly medians range from
−12.54% to +0.14%, and wall from −3.81% to +0.47%. COO with two threads lowers
assembly but increases single-rank wall 3.90%; these remain explicit controls.
Case-calibrated `10:5,20:1` costs give two-rank wall −10.58% and assembly −29.09%;
this is an opt-in result for one mesh/material/solver combination.

P1 offline preparation of 82,944 cells into 2/8/32 shards gives paired wall
medians −12.25% / −16.54% / −32.70%. Independent checks compare 168 actual HDF5
shard pairs, explicitly handling matching zero-length datasets. These are serial
prepares, not 32-rank solve scaling. P2 space preparation retains existing
rank-global scans; no whole-path linear-complexity claim is made.

Independent decoding validates all 32 output experiments. Compact boundary
points cut total bytes 22.23%–23.18% relative to full ASCII. Holding compaction
fixed, binary reduces measured output time 81.34%–82.01% but increases bytes
0.815%–3.060%. ASCII remains the format default. Output timings include
application synchronization/index writes, not durable fsync latency.

The original I/O experiment's `KeyError('reason')` is retained as failed: the
solver succeeded and its driver expected the wrong convergence token. The
pushed fix reran only output; the completed partition stage was audited
separately. No full-suite, Debug or legacy-version run was added.

See [commands, sources, paired ranges, raw archive and limitations](../research/data/fsi-runtime-2026-11-26/README.md).
Performance measurements use one shared host with 1/2 MPI ranks; some
correctness paths use four ranks. Independent maximum-rank phase times must
not be added, and separate experiment percentages cannot be combined into a
universal speedup. Multi-node, GPU, nonmatching interfaces and a universal
optimal preconditioner are outside the implemented and measured scope.
Delivery and authoritative merge state are
[PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53).


## HPC-05 continuation (2026-11-26)

The five-track continuation adds bounded semantic aggregate coarse modes with a
GAMG auxiliary solve, optional owned/halo exchange overlap, stable fused field
reductions, AD SIMD/dataflow optimization, optional adaptive numeric PC updates,
and collective HDF5/XDMF result output. The exact Jacobian and physical acceptance
remain independent of PC reuse. Aggregate, overlap, adaptive reuse and HDF5 are
explicit options; they are not universal performance defaults.

[Implementation, controls, failures and independently audited evidence](../research/data/hpc-five-track-2026-11-26/README.md)
record the production binary source `2788970` and final verification driver `ceaa680`.
The generated case reduces actual USER Schur updates from 10 to 2–3 while retaining 10 J
assemblies, but the strongly changing arterial trajectory still needs 61/62 updates
out of 64. HDF5 improves on ASCII here but is slower than binary; small-rank data do
not establish multi-node scalability. The earlier per-J USER refresh description
above applies to the original nonadaptive mode.
