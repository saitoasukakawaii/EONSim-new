# FSI-PERF-03: runtime, partition and output evidence

Implementation and scoped validation are complete. Delivery is through
[PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53); GitHub is the
authoritative merge state. Every implementation/driver change was synchronized
to the remote branch **before** its build, numerical validation or measurements.
The final evidence/documentation commit does not change the measured C++ source.

The strongest controlled findings are removal of ten duplicate Jacobian/USER
Schur updates per ten-step trajectory, and lower MPI waiting after case-specific
partition cost balancing. Default-path gains are smaller and noisy. Binary
output saves conversion time but is slightly larger than compact ASCII in the
measured problem. Regressions and failure records are retained below.

## Evidence index

- [Implementation and runtime controls](../../../development/FSI_RUNTIME_OPTIMIZATION.md)
- [Machine-readable results/provenance](performance-summary.json) and [all paired metric statistics, percent](performance-summary.csv)
- [Independent FSI audit](independent-fsi-audit.json), [partition/output audit](independent-io-audit.json), [empty datasets and direct format comparison](independent-io-empty-datasets.json)
- [Local Release receipt](local-release-summary.json), [baseline build receipt](baseline-build-summary.json)
- [Source CI receipt](source-ci-receipt.json), [weighted-driver receipt](driver-ci-receipt.json), [I/O-fix receipt](iofix-ci-receipt.json)
- [Environment](environment.json), [weight calibration](partition-weight-calibration.json), [raw archive index](archive.json)
- [Unpublished development article](../../../../website/drafts/fsi-runtime-cost-and-output.md)

## Source and binary identity

| Role | Commit | Meaning |
|---|---|---|
| Main/baseline | `2dcb06c26a0359175e4f5a771d5bbff6dfc928af` | Merged PR #52; clean baseline binary |
| First runtime implementation | `47237a033820b53ceb19003d032bb50f70994bb0` | AD, compact insertion, persistent teams, final residual |
| Final production implementation | `7e8868e433fb0040806a6faf3ba8cd289a2aa3f1` | Candidate binary, local Release and source CI |
| Weighted experiment driver | `3e366c89e40af79019f31280dd2c47de02bda413` | Candidate-only weights and partition receipts; C++ unchanged |
| I/O experiment fix | `7d86f38b03e42615d7b1937580b105f3484f4eca` | Textual convergence reasons and stage selection; C++ unchanged |

Binary SHA-256:

```text
baseline  3399694877a426093cd1e8752ac26b2f63f7e9d826910db0b818b7911cb7af2b
candidate 1eb8ea57ac1a1d4c120bae5a1d79d2a228034cdbccb8da6272ecc0ea78a4cf27
```

Default and COO/thread campaigns used driver `7e8868e`; weighted and initial-J
used `3e366c8`. The completed partition stage belongs to the original I/O
attempt at `3e366c8`; the successful output-only rerun used `7d86f38`.
Both binaries are PETSc 3.23.7 **Release**, real double and 32-bit PETSc indices,
built with the same locked dependencies. The archive contains both actual
executables, CMake caches, source-specific driver snapshots and build receipts.

## Completed implementation

| Area | Change | Preserved contract |
|---|---|---|
| ALE kernel | AD width 28 → 24, four exact pressure columns | Complete geometric and cross-field derivatives |
| Sparse insertion | Compact AIJ physical blocks, dense alias-order fallback | Independent test/trial maps and contribution addition order |
| Workers | One persistent OpenMP team across bounded 64-cell batches | Main-thread PETSc/MPI, collective failure cleanup |
| Final residual | One fresh raw residual for reactions and projected acceptance | No stale residual acceptance; owned/ghost reactions |
| Jacobian-only callback | Omit unused scratch residual COO publication | Required residual evaluations remain intact |
| Initial tangent | One-use same-state startup reuse; deferred work in retained Schur sessions | Numeric Jacobian/USER refresh at every Newton state |
| Reporting | Actual Jacobian/USER counters and optional per-rank timings | Application work distinguished from PETSc internal setup |
| Partition | Stable buckets, owner prefixes, one fingerprint, earlier temporary release | Default METIS input, numbering, order and HDF5 schema |
| Explicit costs | Positive integer cell-tag weights with weighted partition identity | Input/overflow validation and mixed-shard rejection |
| VTU | Compact boundaries, borrowed views, streaming appended binary, optional boundary omission | Int64 IDs, fields, directed topology and PVTU references |

The implementation guide documents controls and invalidation conditions. The
grouped baseline comparison does not establish a separate causal speedup for
every individual kernel change.

## Executed correctness validation

Clean `7e8868e`: **17/17 targeted local Release CTest checks passed**, no failed
or skipped tests. Configure 2.573 s, build 30.311 s, CTest command 210.080 s.
The locked linkage and four-rank runtime preflight also passed.

```bash
OMPI_MCA_smsc=^cma bash scripts/cloud/run.sh 3.23.7 release explicit .cloud \
  /workspace/scratch/ae740e1dde63/EONSim-new/build/runtime-validation-selection.json
```

Selected tests: `checkpoint_publication_mpi`, `nonlinear_acceptance`,
`nonlinear_acceptance_mpi`, `scalar_p2_verification`, `fsi_block_efficiency`,
`fsi_metric_stabilization`, `fsi_element_jacobian`, `scalar2d_space`,
`fluid_coo_verification`, `fsi_coo_verification`, `pc_added_mass_retry`,
`pc_twolevel_retry`, `pc_recipe_restart`, `pc_recipe_hybrid`, `domains_verification`,
`poisson_verification`, `poisson_parallel`.

New fault controls use an actual second worker batch: n=3, 162 fluid cells,
two ranks, team size 2, batch index 1, worker thread 1 and master thread 0.
Recoverable faults shorten dt 0.008 → 0.004 once; fatal cases publish no accepted
step. Solver tests cover coefficient/constraint changes, trial-evaluation
invalidation, rank-local faults, zero residual and incompatible policies.
Format tests independently decode appended blocks and check IDs beyond 2^53,
mixed Tri3/Quad4 offsets and boundary maps. Scope includes derivative controls,
retry/restart, weighted partition identity and topology/numbering oracles.

Scoped Python benchmark tests passed **7/7** at `7e8868e`, then **10/10** after
the pushed weighted-driver change. The clean baseline receipt says **built**,
not tested. No local full-suite, Debug or PETSc 3.19.6 run was added. Some
shared correctness paths use four ranks; performance uses only one or two.

### Remote CI: new execution and historical reuse

| PR head | Tested merge commit | New Release | Reused Release | New Python | Numerical run |
|---|---|---:|---:|---:|---|
| `7e8868e` | `d07ec648ac25444863a4fd9f6f2aa71d44775cbb` | 48 | 0 | 24 | [45711876709](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45711876709) |
| `3e366c8` | `4c924fd5fec4074ef736ab1065feb690425060a2` | 1 | 47 | 21 | [45714273854](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45714273854) |
| `7d86f38` | `2616c6042497d258742a8d0afd8e9109dc2109ee` | 0 | 48 | 0 | [45715315451](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45715315451) |

All three checkpoints passed selection, Release, incremental evidence and
website checks. Source Python execution was six Lamé-wall and eighteen profile
checks; weighted-driver execution was twenty-one profile checks. The I/O-fix
[selection log](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45715315451/job/139559760132)
records empty new numerical/Python selections. Later receipts preserve the
original passing test/run identities. Final evidence-only head checks and
merge status live on PR #53; a green reused Release gate does not mean 48
tests ran again. No CI bypass, permission change or numerical-gate relaxation.

## Measurement method

One shared Linux host, AMD EPYC 9V74, affinity CPUs 0–8, detected 9 CPUs and
10,451,427,328 bytes of memory. GCC/G++ 15.3.0, Open MPI 5.0.8, PETSc 3.23.7,
METIS 5.1.0, HDF5 1.14.6, OpenBLAS 0.3.34. Library threads are one; element
threads are one except the explicit two-thread campaign. Builds, MPI runs and
audits were separated so no other task-owned measurement ran concurrently.

Each configuration has one warmup pair plus **three alternating measured
pairs**. Tables report `candidate / baseline - 1`: median and `[minimum,
maximum]` across pairs. Negative means less time/memory/bytes. These ranges
are descriptive, not confidence intervals. The ratio of two independently
computed medians is not substituted for a median of paired ratios.

Wall time uses a blocking child wait with a separate timeout watchdog and
includes startup, input, solve, output and shutdown. Offline prepare is separate.
Phase times are independent maximum-rank observations and may overlap; **do
not add them** to reconstruct wall. Separate `-log_view` diagnostics are not
mixed into paired timing samples.

| FSI n | Fluid cells | Solid cells | Total cells | Active DoFs | Steps / dt |
|---:|---:|---:|---:|---:|---|
| 4 | 384 | 387 | 771 | 703 | 10 / 0.02 |
| 8 | 3,072 | 3,075 | 6,147 | 5,367 | 10 / 0.02 |

Independent conforming fluid/elastic-solid meshes save every accepted step.
Default, COO/thread and weighted campaigns use PREONLY/LU/SuperLU_DIST on both
sides. Initial-J uses identical twolevel semantic settings: outer FGMRES,
right preconditioning, unpreconditioned norm, rtol 1e-11, atol 1e-13, maximum
3,000, restart 100, nodal pressure and velocity PREONLY/MG. Complete options
and hashes are in the machine-readable summary and raw results.

Every FSI run checks independent true linear residual
`||b-Ax|| <= 1e-12 + 1e-10*||b||`, physical/constraint acceptance, identical
accepted times and Newton/Krylov trajectories, and physical/history agreement
within 2e-9 absolute. Timing never changes these acceptance gates.

## FSI paired results

`default` and `coo-threads` compare main `2dcb06c` to candidate `7e8868e`.
COO/two threads are enabled on both sides. `weighted` compares the same new
binary with default versus `10:5,20:1` partitions. `initial-jacobian` compares
the same new binary/solver with reuse false versus true. Gains from these
different experiments cannot be added together.

| Comparison | n / DoFs | MPI ranks | Assembly change | Total wall change | Peak max-rank RSS change |
|---|---:|---:|---:|---:|---:|
| default | 4 / 703 | 1 | -2.24% [-17.36%, -0.32%] | -3.81% [-8.70%, -2.67%] | -1.84% |
| default | 4 / 703 | 2 | -12.54% [-20.14%, -12.47%] | +0.47% [-7.86%, +1.16%] | +0.26% |
| default | 8 / 5,367 | 1 | +0.14% [-2.87%, +3.45%] | -0.91% [-3.82%, +1.26%] | -0.74% |
| default | 8 / 5,367 | 2 | -8.90% [-17.36%, -5.48%] | -3.56% [-11.10%, -3.04%] | +0.68% |
| coo-threads | 8 / 5,367 | 1 | -3.88% [-5.17%, -0.69%] | +3.90% [-3.07%, +4.39%] | -0.54% |
| coo-threads | 8 / 5,367 | 2 | -13.35% [-14.58%, -8.65%] | -4.38% [-4.69%, +0.48%] | -0.32% |
| weighted | 8 / 5,367 | 2 | -29.09% [-30.15%, -26.54%] | -10.58% [-15.98%, -9.54%] | -2.48% |
| initial-jacobian | 4 / 703 | 1 | -31.36% [-31.82%, -25.07%] | -12.06% [-15.11%, -7.14%] | +0.03% |
| initial-jacobian | 4 / 703 | 2 | -39.55% [-42.32%, -33.42%] | -17.37% [-22.21%, -12.39%] | -0.77% |
| initial-jacobian | 8 / 5,367 | 1 | -30.97% [-35.36%, -22.73%] | -18.08% [-23.38%, -12.52%] | +0.17% |
| initial-jacobian | 8 / 5,367 | 2 | -36.29% [-36.77%, -31.98%] | -25.59% [-25.76%, -21.43%] | +0.40% |

Default n8/r1 assembly is +0.14% and wall spans zero; default n4/r2 wall is
+0.47%. COO/two-thread single-rank wall is +3.90% despite reduced assembly.
Memory is not uniformly lower: weighted max-rank peak RSS is −2.48%, while
the sum of rank peaks is +0.27%. Matrix COO and threads remain explicit options;
the default element thread count remains one.

### Initial-J causal control

All 32 runs preserve exactly equal physical fields/history and identical
iteration trajectories. Per ten-step run:

| Counter | Reuse false | Reuse true |
|---|---:|---:|
| Physical Jacobian assemblies | 30 | 20 |
| Application USER Schur updates | 30 | 20 |
| SNES Jacobian callbacks | 20 | 20 |
| Pre-SNES initial assemblies | 10 | 1 |
| One-use initial reuses | 0 | 1 |
| Deferred initial assemblies | 0 | 9 |

This control ties wall reductions of 12.06%–25.59% to removed duplicate J/USER
work. `user_schur_updates` counts application nodal USER construction/refresh,
not all PETSc `PCSetUp`; `schur_setup_seconds` covers only pre-SNES work and
does not include every later USER refresh.

### Case-specific weighting

The independent unweighted diagnostic has fluid/solid counts 2875/247 and
197/2828. Ten-step callback time is 0.730807/0.194794 s; the lighter rank waits
0.537749 s in failure synchronization. Fitting
`T_rank = c_fluid*N_fluid + c_solid*N_solid` gives a ratio about 4.85, rounded
to integer weights 5:1. This two-point model includes callback overhead; it is
an approximate calibration, not universal single-element kernel timing.

Weighted diagnostic counts are 1794/0 and 1278/3075, callback times
0.440770/0.479388 s and synchronization times 0.050929/0.009386 s. Formal pairs
give assembly −29.09%, callback −37.90%, failure synchronization −95.99%,
linear time −6.07% and wall −10.58%. Some work grows: assembly finalization
+76.08%, finalization +24.56%. Diagnostic samples explain the likely load
balance mechanism; they do not replace the three paired samples. Weights
remain opt-in and need recalibration for another workload.

## Offline partition preparation

Warped Poisson P1 fixture: 15,625 nodes, 82,944 Tet4 cells. **Serial offline**
preparation produces 2/8/32 shards, not a 32-rank solve. There are 24 paired
prepare runs: six warmups and eighteen measured runs (nine measured pairs).
Three additional profiling prepares are excluded from these statistics.

| Output shards | Baseline wall median (s) | Candidate wall median (s) | Paired wall change |
|---:|---:|---:|---:|
| 2 | 0.538125 | 0.447697 | -12.25% [-42.16%, -7.24%] |
| 8 | 0.578714 | 0.481333 | -16.54% [-24.72%, -2.54%] |
| 32 | 0.791478 | 0.577649 | -32.70% [-35.76%, -16.57%] |

Wall includes mesh input and process startup/shutdown; internal prepare reports
start after input. Independent checks re-read 168 actual HDF5 shard pairs:
objects, types, extents and nonempty values match; manifests/other metadata
match byte for byte. Four p32/rank_27 comparisons have empty `boundary_tags`,
`face_ids`, `face_nodes`, `face_tags` that h5diff labels not comparable.
Supplementary checks confirm equal types and zero extents on both sides,
without unexplained noncomparable values. Default layout, numbering, identity
and schema are therefore supported by actual-file comparisons. P2 space
preparation retains existing rank-global scans; no whole-path P2 linear
complexity is claimed.

## Output results

The same 82,944-cell Poisson fixture and candidate binary run 32 output solves:
eight warmups and twenty-four measured runs. Within each rank count, all four
modes have the same solver and input representation. One rank reads Gmsh;
two ranks read HDF5, so cross-rank total wall is not strong-scaling evidence.

`ascii_full` explicitly restores the full boundary point set. Current default
is `ascii_compact`; `binary_compact` keeps that layout; `binary_volume` also
omits companion boundary files.

| MPI ranks | Mode vs full ASCII | Output time change | Total wall change | Bytes change |
|---:|---|---:|---:|---:|
| 1 | ascii_compact | -24.53% [-32.73%, -23.91%] | -2.75% [-22.42%, +1.53%] | -22.23% |
| 1 | binary_compact | -86.50% [-87.45%, -85.71%] | -17.88% [-31.56%, -14.32%] | -21.59% |
| 1 | binary_volume | -87.00% [-89.38%, -85.96%] | -13.10% [-27.43%, -9.24%] | -28.74% |
| 2 | ascii_compact | -29.45% [-36.41%, -27.10%] | -2.94% [-8.15%, +4.05%] | -23.18% |
| 2 | binary_compact | -87.31% [-93.61%, -84.71%] | -12.10% [-16.26%, -0.58%] | -20.83% |
| 2 | binary_volume | -88.15% [-95.07%, -86.87%] | -20.14% [-20.62%, -11.63%] | -28.09% |

Holding compact boundaries fixed, **binary versus current default ASCII**
reduces output time **81.34% / 82.01%** and total wall **15.56% / 8.83%** at
one/two ranks. Bytes increase **0.815% / 3.060%**. The size reduction versus
full ASCII comes principally from point compaction, not a general guarantee
of binary encoding. Even the small affine fixture writes 30,227 binary bytes
versus 22,822 ASCII bytes. No compression is claimed.

The output timer includes application synchronization and rank-zero indices,
but not fsync/durable storage throughput. Independent XML/struct decoding
checks all **84 VTU and 28 PVTU**: exact numeric volume arrays, exact boundary
fields and directed topology by stable IDs, UInt64 appended lengths/offsets,
Int64 IDs and piece declarations/references. Source Gmsh coverage, ownership
and algebra numbering are independently checked. This is exact numeric
agreement, not a claim of identical floating-point bit encodings.
Boundary omission is checked in fresh directories; it does not delete stale
files at a reused prefix.

## Independent replay and retained failures

FSI audit re-read **88 runs, 880 accepted steps, 1,760 true linear corrections,
968 physical snapshots and 8,502 file hash receipts**. Counts include 22 warmup
runs; formal stats use 66 runs / 33 pairs. Raw logs, aggregates, pairs and
min/median/max agree. Maximum physical difference 4.440892098500626e-16;
history difference 2.9841559419667343e-15; initial-J differences exactly zero.
Worst true-linear residual/gate is 0.0906395256835613; maximum field
acceptance/gate is 0.47449454750603043; constraint/gate is zero.

Default and COO/thread predate the added partition-shard hash receipts.
Recorded input/output/binary hashes match and present partitions are archived,
but absent historical hashes cannot retrospectively prove unchanged shards
during execution. Weighted and initial-J have complete contemporaneous
partition receipts. Archive hashes verify delivery, not missing past observations.

Two failures remain visible in raw evidence:

1. Baseline timing wrapper initially required unavailable `/usr/bin/time`,
   before CMake execution. The attempt receipt is retained; the successful
   build uses Python monotonic timing and the same locked tools.
2. `io-partition/results.json` retains overall **failed**, `KeyError('reason')`.
   All 24 prepare runs had finished; the first output solver exited zero with
   `CONVERGED_RTOL`. Its subsequent driver expected the wrong token. The fix
   at `7d86f38` recognizes textual convergence and adds `--stage`; it was
   pushed before rerunning **only output**. Independent audit accepts the
   completed partition stage separately without relabeling the old overall
   run or counting the abandoned output sample.

All solver runs in final FSI/output statistics succeeded. Injected faults in
correctness tests remain labeled expected failures/retries. Independent audits
passed on first full execution; the empty-dataset supplement clarifies HDF5
semantics without changing data, thresholds or original results JSON.

## Raw archive and reproduction

The [archive index](archive.json) describes nine 4 MiB-or-smaller chunks of a
standard tar.xz stream, **33,761,824 bytes**, containing **14,435 logical files /
955,282,684 payload bytes**. Every member was read back and checked for SHA256,
size and mode; inputs remained unchanged during packing. Full stream SHA256:

```text
ba3a8363d6ab145b830343ffebf8997db14f319a3c0428c494256e7bfba16026
```

The archive retains `EONSim-new/` and `EONSim-baseline/` paths, actual binaries,
campaign inputs/partitions/results/history/logs, local test work directories,
CI receipts, failures, audits and actual driver snapshots. Its internal
`manifest.json` is the complete per-file hash/size/mode manifest (SHA256
`8b40450db670e989009b5713139a8b1d69477d3c2289ddfd3f1b216ebc10c41a`).
Restore dependencies from repository locks; their installed prefix is not
duplicated in the archive. The standalone receipts/summary are convenience
copies; full raw evidence is in the compressed stream.

In the directory containing all nine chunks, reconstruct and verify:

```bash
cat eonsim-runtime-7e8868e-raw.tar.xz.part?? > /tmp/eonsim-runtime-evidence.tar.xz
sha256sum /tmp/eonsim-runtime-evidence.tar.xz
# Require the exact stream hash above before extraction.
mkdir -p /tmp/eonsim-runtime-evidence
tar -xJf /tmp/eonsim-runtime-evidence.tar.xz -C /tmp/eonsim-runtime-evidence
```

Original absolute paths occur in CMake caches and command arrays; adjust them
for another workspace. Each raw `results.json` contains actual commands,
exit codes and durations. To recreate experiments with source-specific builds
and the locked wrapper, use new work directories; define the following
`FSI_*` variables for the restored baseline/candidate binaries and prefix:

```bash
bash build/locked.sh python3 scripts/benchmark_fsi_assembly.py \
  --baseline "$FSI_BASELINE_BIN" --candidate "$FSI_CANDIDATE_BIN" \
  --baseline-commit 2dcb06c26a0359175e4f5a771d5bbff6dfc928af \
  --candidate-commit 7e8868e433fb0040806a6faf3ba8cd289a2aa3f1 \
  --mpiexec "$FSI_PREFIX/bin/mpiexec" --work build/new-default-campaign \
  --subdivisions 4 8 --ranks 1 2 --steps 10 --repeats 3 \
  --baseline-assembly-report

bash build/locked.sh python3 docs/research/data/fsi-runtime-2026-11-26/benchmark_io_partition.py \
  --baseline "$FSI_BASELINE_BIN" --candidate "$FSI_CANDIDATE_BIN" \
  --baseline-commit 2dcb06c26a0359175e4f5a771d5bbff6dfc928af \
  --candidate-commit 7e8868e433fb0040806a6faf3ba8cd289a2aa3f1 \
  --mpiexec "$FSI_PREFIX/bin/mpiexec" --h5diff "$FSI_PREFIX/bin/h5diff" \
  --work build/new-output-campaign --stage output \
  --subdivisions 24 --parts 2 8 32 --repeats 3
```

For COO add `--baseline-options '-fsi_coo -fsi_threads 2'` and identical
candidate options, n8/ranks1,2. For weighting use the candidate for both
binaries/commit labels, n8/rank2, and `--candidate-partition-weights '10:5,20:1'`.
For initial-J use candidate on both sides, `--solver twolevel`, baseline
options `'-nonlinear_initial_jacobian_reuse false'` and candidate options
`'-nonlinear_initial_jacobian_reuse true'`. I/O `--stage partition` runs only
prepares. Actual historical driver snapshots are preserved; the corrected
driver naturally does not reproduce the old parser error.

The completed scope is the identified CPU/MPI work with recorded acceptance.
These single-host experiments do not establish multi-node/GPU performance,
universal weights/preconditioners or production-mesh scaling.
