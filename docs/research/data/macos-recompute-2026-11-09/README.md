# Fresh macOS execution evidence, 2026-11-09

Source: `92fef88ec6c7dad48cfe8a25ecdb79db48f9a8cc` (snapshot), unchanged solver.
The user explicitly requested a new 48-hour continuation and fresh computation
where raw data is missing. Historical stopped Linux processes are not resumed.
No push, PR, merge, or physical qualification has occurred in this continuation.

## Build and runtime

See [environment.json](environment.json): macOS arm64, AppleClang 21, PETSc
3.25.6, OpenMPI 5.0.11, 24 GiB, 12 logical CPUs. These are not the locked
Linux/PETSc 3.23.7 environment. A successful build does not establish equivalence.

Actual configure/build commands (from repository root):

```sh
cmake -S . -B build/macos-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DEONSIM_PETSC_ROOT=/Users/chen/software/petsc-3.25.6-install -DCMAKE_PREFIX_PATH=/opt/homebrew
cmake --build build/macos-release --target eonsim verify_lu_reuse --parallel 2
```

Debug used `build/macos-debug` and `-DCMAKE_BUILD_TYPE=Debug`, with the same
remaining arguments. Both builds succeeded. Release emitted a pre-existing
misleading-indentation warning in `scalar_p2.cpp`; no unrelated edit was made.

Initial restricted MPI invocation failed to open local communication sockets.
After running with local communication permitted, Release `lu_reuse_mpi1` and
`fluid_pressure_time` passed; `lu_reuse_mpi2`, `fluid_lu_reuse`, and
`fsi_lu_reuse` failed. The latter two reached their two-rank MUMPS solves.
The smallest reuse case reported linear convergence with unchanged true
residual, then nonlinear line-search failure. No tolerance was relaxed.

## Independent dependency reproduction

[mumps_rhs_probe.c](mumps_rhs_probe.c) uses only PETSc, with three unknowns,
diagonal entries 2.3/3.3/4.3 and cyclic off-diagonal entries .1. It forms
`b=A*1`, solves with MUMPS, and explicitly checks both `||x-1||inf` and
`||Ax-b||2`. It includes no EONSim assembly, ghost update, or nonlinear solver.

Actual compilation:

```sh
mpicc docs/research/data/macos-recompute-2026-11-09/mumps_rhs_probe.c -I/Users/chen/software/petsc-3.25.6-install/include -L/Users/chen/software/petsc-3.25.6-install/lib -Wl,-rpath,/Users/chen/software/petsc-3.25.6-install/lib -lpetsc -o build/recompute-20261109/mumps_rhs_probe
```

Each combination ran once with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and
`PETSC_OPTIONS` removed. Exact commands/exit codes are in
[mumps-probe-results.json](mumps-probe-results.json), with adjacent raw logs.

| Ranks | MUMPS RHS option | Solution error | True residual | Exit |
|---|---|---:|---:|---:|
| 1 | default | 2.22e-16 | 8.88e-16 | 0 |
| 2, 4 | default | 1 | 6.056401571890688 | 2 |
| 1, 2, 4 | `-mat_mumps_icntl_20 0` | 2.22e-16 | 8.88e-16 | 0 |

This isolates an installed PETSc/MUMPS runtime-path problem. It does not yet
identify the upstream faulty line or establish that other builds have the same
defect. The system installation was not modified. Centralized RHS is an explicit
local execution workaround, not a new distributed scalability claim.

## Relevant EONSim checks

```sh
PETSC_OPTIONS='-mat_mumps_icntl_20 0' ctest --test-dir build/macos-release -R '^(lu_reuse_mpi[24]|fluid_lu_reuse|fsi_lu_reuse)$' --output-on-failure
PETSC_OPTIONS='-mat_mumps_icntl_20 0' ctest --test-dir build/macos-debug -R '^(lu_reuse_mpi[12]|fluid_lu_reuse|fsi_lu_reuse)$' --output-on-failure
```

Both passed 4/4. [Release log](release-centralized-rhs-ctest.log) and
[Debug log](debug-centralized-rhs-ctest.log) record the results. The fluid and FSI
checks themselves cover 1/2/4 ranks, actual factor counts, fields and restart;
they are not just process-launch tests. No full test suite was run.

## New production computation

The initial study uses the verified **serial default** MUMPS path, with no
`PETSC_OPTIONS` override, one BLAS/OpenMP thread, and fresh inputs/checkpoints:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 scripts/study_womersley.py --work build/recompute-20261109/alpha1-s96-l0-n400 --executable build/macos-release/eonsim --seed 96 8 8 --level 0 --alpha 1 --steps-per-cycle 400 --phases 400 --warmup 2 --cycles 6 --ranks 1 --mumps --lu-reuse-window 32 --chord --cycles-per-solve 1 --timeout 86400
```

The binary is frozen by the existing study definition. Completed-cycle receipts
and raw logs/checkpoints remain in that work directory. The first 400-step
cycle completed; the study is still running at this checkpoint. All analytic,
periodic and error-budget qualification remains pending. No original omitted
trajectory is used as an input, and no historical failure is overwritten.

## Continuation checkpoint

Both fresh coarse studies have now completed: [alpha1](../macos-alpha1-coarse-2026-11-09/README.md)
retains its failed flow-amplitude gate; [alpha2](../macos-alpha2-coarse-2026-11-09/README.md)
passes preliminary gates only. Fine-grid budgets remain pending.
[continuation-state.json](continuation-state.json) records a point-in-time inventory;
its process handles must be re-polled before any restart. Controller copies in
`controllers/` preserve actual running sources, not finished-run evidence.
`reference-nu0-prefix/` contains only the immutable first 100 steps of a running
reference study, not a completed convergence audit. The explicit exporter option
is covered by [seven passing tests](mesh-poisson-exporter-tests.log); it changes
only reference mesh-motion Poisson ratio, with physical solid and default unchanged.
