# Elastic FSI assembly and preconditioner costs

On the 48-sector two-ended tube, a fluid cell contributes 28 fluid/ALE slots and a wall cell contributes 12 solid slots. The earlier assembly inserted a 40-by-40 matrix for either Tet4. The compact implementation uses each region's actual slots for sparse preallocation and insertion. At the interface the fluid velocity, mesh lifting and solid velocity still refer to their shared reduced unknown. Local residuals and the ALE chain factors use the same trial state.

For the 3,024-DoF problem the reported Jacobian stored 192,628 entries after this change, down from 194,350. In all 60 pairs of final fields (five pairs, two logging modes, three rank counts, two PCs), the maximum cross-build change over all output components was 3.47e−18 in the fluid file and 1.96e−18 in the solid file. Both Newton solves completed and the linear iteration counts matched across builds. [All paired comparisons and binary hashes](pair-results.json.xz)

## Phase measurements

PETSc 3.23.7 Release, Open MPI, AMD EPYC 9V74 in a nine-vCPU shared environment. Each MPI process used one OpenMP/BLAS thread. The same 1,512 fluid and 1,728 solid cells, partition, tolerances and two steps of 0.25 s were used in each pair. Five independent pairs alternated the build order. Each build/rank/solver combination received one warmup, one ordinary solve with solver diagnostics, and one solve with PETSc events. The ordinary wall measurement includes launch and final field output. Concurrent spatial studies introduce timing noise. Times for a PETSc event use the largest local total over ranks. The ranks contributing each maximum can differ. PC/KSP events are nested.

| MPI ranks | Linear solve | Compact insert time (s) | Median paired insert change | Median paired wall change | Compact PC setup (s) | Compact PC apply (s) |
|---:|---|---:|---:|---:|---:|---:|
| 1 | direct | 0.0483 | -17.8% | -0.9% | 0.2435 | 0.0061 |
| 1 | schur | 0.0694 | -21.8% | +2.5% | 0.0131 | 0.3949 |
| 2 | direct | 0.0350 | -28.2% | -6.5% | 0.1883 | 0.0100 |
| 2 | schur | 0.0457 | -33.9% | -3.8% | 0.0168 | 0.5448 |
| 4 | direct | 0.0252 | -21.3% | -7.3% | 0.1883 | 0.0164 |
| 4 | schur | 0.0362 | -27.5% | -10.1% | 0.0182 | 0.7960 |

The direct case spends a larger fraction of its time in numeric setup. The tested Schur configuration spends more time in application, with 488, 483 and 449 outer linear iterations summed over both steps at 1, 2 and 4 ranks respectively. A speedup of the insertion loop does not guarantee an end-to-end gain for every solver/rank combination. [Phase medians and full ranges of paired changes](phase-medians.csv)

## Reproduce

The new PETSc events are enabled by `-log_view`. The benchmark requests `-log_view :events.csv:ascii_csv`. It reads rank-local rows for the fluid residual, full fluid/ALE Jacobian, solid residual, solid residual with tangent, local vector/matrix insertion, and the postsolve replay of interface forces. `FSIFluidAleJac` includes the derivatives with respect to fluid and mesh unknowns from the single AD evaluation. `FSIInsert` includes multiplication by the interface trial weights and calls to PETSc insertion. `MatAssemblyBegin/End`, `PCSetUp` and `PCApply` use PETSc's existing events. A rejected geometric evaluation closes any active event before error propagation. Event time is inclusive of the instrumented callbacks, including the two final residual evaluations made by the nonlinear driver. The postsolve replay has its own event.

Use independent checkouts of the [instrumented baseline](https://github.com/saitoasukakawaii/EONSim-new/commit/e74fe3c2de4758650827f79e020ce44483277f39) and [compact assembly](https://github.com/saitoasukakawaii/EONSim-new/commit/c4a78efbb1609f1d5d415d299e4eefefdf36ea7a). Build both using `bash scripts/cloud/run.sh 3.23.7 release explicit <locked-prefix-directory> <selection.json>` with the `fsi_tube` test selected. Set `case_dir` to the PR 42 archived `coupled/sv05-s48` case, `data` to this directory, and `pairs` to an empty absolute working directory.

```bash
for pair in 0 1 2 3 4; do
  variants=(baseline compact)
  if ((pair % 2)); then variants=(compact baseline); fi
  for version in "${variants[@]}"; do
    binary="$compact_eonsim"
    if [[ "$version" == baseline ]]; then binary="$baseline_eonsim"; fi
    LD_LIBRARY_PATH="$prefix/lib" OPENBLAS_NUM_THREADS=1 python3 "$data/profile_case.py" \
      --case "$case_dir" --work "$pairs/r$pair-$version" --executable "$binary" \
      --mpiexec "$prefix/bin/mpiexec" --ranks 1 2 4 --pcs direct schur --repeats 1
  done
done
python3 "$data/compare.py" --work "$pairs" --output "$pairs/audit"
```
