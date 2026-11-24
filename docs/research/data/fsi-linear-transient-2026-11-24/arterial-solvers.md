# Field-split solves on the 20 mm tube

The fluid and wall of the 120 mm long tube start at rest. Both open ends follow a 1 s quintic pressure ramp to 80 Pa. All comparisons use 32 steps, generalized-α at spectral radius 0.5 after a backward Euler startup, the volume-based stabilization, and the same dimensional nonlinear limits of 1e−14 absolute and 1e−11 relative. Each accepted case recovers fluid pressure, velocity and ALE displacement together with wall velocity and displacement at eight phases. The reference is the one-rank monolithic direct solution on the same mesh. [Pressure, material and discretization](scaled-tubes.md) · [Every attempt and its resolved field errors](arterial-solvers.csv)

For every Newton correction, including exhaustion of the requested Krylov iteration budget, EONSim forms the matrix-vector product with the actual returned iterate. The reference target here is $T=\max(10^{-23},10^{-10}\lVert b\rVert_2)$. The tabulated ratio is $\lVert Ax-b\rVert_2/T$. It is an unweighted algebraic 2-norm with mixed dimensional rows. The mesh, continuity, momentum and wall row counts and RMS values independently reconstruct this 2-norm. Native svFSILS first applies its own matrix and right-hand-side scaling. The native residual comparison therefore uses its own scaled system and the physical observations are compared in SI units. [Separate native BIPN experiment](bipn-residual.md)

| 24 sectors, 1,027 global equations | MPI ranks | Corrections within target | Largest ratio | Total outer iterations on accepted steps |
|---|---:|---:|---:|---:|
| Direct MUMPS | 1 | 64 / 64 | 0.0170 | 64 |
| Field split, longer restart and unchanged inner solvers | 1 | 64 / 64 | 0.9995 | 24,057 |
| Inexact velocity and solid solves, classical Gram–Schmidt | 1 | 57 / 64 | 3.8070 | 3,101 |
| Same inner solves, modified Gram–Schmidt | 1 | 64 / 64 | 0.9994 | 3,016 |
| Same inner solves, classical Gram–Schmidt, 10× tighter outer tolerances | 1 | 64 / 64 | 0.6741 | 4,452 |
| Field split, direct MUMPS in the four diagonal blocks | 1 | 64 / 64 | 0.9576 | 481 |
| Inexact velocity and solid solves, classical Gram–Schmidt | 2 | 60 / 64 | 1.3145 | 2,948 |
| Same inner solves, modified Gram–Schmidt | 2 | 64 / 64 | 0.9760 | 2,948 |
| Same inner solves, classical Gram–Schmidt, 10× tighter outer tolerances | 2 | 64 / 64 | 0.7764 | 3,697 |

The inexact block experiment uses right-preconditioned FGMRES with a restart length of 100. Velocity and wall solves use GMRES, relative tolerance 1e−4 and limits of 10 and 12 iterations. Changing just the outer orthogonalization gives all 64 corrections within the independently recomputed bound on the two partitions shown. The coarse maximum field error with the modified scheme is 1.52e−10 of each field's own space-time peak across these partitions. The 32-step end area is 0.18680312%. Different iteration counts can lead to the same measured deformation. The complete PDE steps and the accuracy of the linear subproblem are reported separately. [Tested PETSc options file](arterial-fieldsplit.opts)

On the 48-sector mesh, the one-rank options-file run took 5,781 outer iterations. All 64 corrections met the target, the worst ratio was 0.99987 and the maximum field difference was 2.37e−10 of its own peak. On the coarse two-rank mesh, two passes of classical Gram–Schmidt gave 64/64, 2,946 outer iterations and a worst ratio of 0.97373. PETSc's per-rank KSPSolve log includes the nested field solves. Its measured operation counts are recorded with the reduced residuals and the per-rank event records. [Rank-resolved residual and work measurements](arterial-solvers.csv)

Two distinct failures occur on the same input. With the stock physics recipe the first nonlinear step stalls at a line search (SNES reason −6). Its third correction leaves a residual and right-hand side both equal to 9.96e−14 on one rank. A short-restart FGMRES experiment with stricter linear tolerances exhausts 500 iterations on its very first correction. On one, two and four ranks the true residual there remains 44.23, 69.49 and 57.03 times the target. On one rank 97.99% of the squared residual originates in the structure equations. The four fields have 243 mesh, 154 pressure, 357 structure and 273 velocity rows in this case. The returned iterate, terminal reason, right-hand side, four field contributions and accepted step count distinguish these failures. [Measured histories and input hashes](arterial-solvers.json.xz)

A coarse four-rank run of the options file emitted a signal 11 after four accepted steps. On the fine one-rank mesh, the two-pass classical run reached 32 steps, printed success and met all 64 residual bounds, but its launcher returned signal 11. That run is marked incomplete in the process column. An independent two-step repeat captured exit code zero for the EONSim child and signal 11 for its MPI launcher. This distinguishes a verified teardown failure from a signal during a solve. The cause of the latter remains open.

## Reproduction

Build through the repository Release script with PETSc 3.23.7. The two ready-to-run quarter-tube meshes and their original input decks reproduce the measured SHA-256 hashes. The first command below prepares the actual two-rank case after unpacking them. The field audit checks all 32 stage pressures and verifies rank binding. Replaying the measured comparison requires Python and NumPy. [Both complete input cases](arterial-inputs.tar.xz) [Release build script](../../../../scripts/cloud/run.sh) · [MPI trajectory runner](arterial_ksp.py) · [Independent field and residual audits](compare_arterial_ksp.py)

```bash
mkdir -p "$work"
tar -xJf "$data/arterial-inputs.tar.xz" -C "$work"
case="$work/s24-r3-w2-a6"
parts2="$work/parts2"
"$eonsim" -case "$case/case.json" -prepare "$parts2" -parts 2
"$petsc/bin/mpiexec" --map-by core --bind-to core -n 2 "$eonsim" -case "$case/case.json" \
  -partition "$parts2" -output "$work/tube.vtu" -solver_report -linear_report -options_file "$data/arterial-fieldsplit.opts"
python arterial_ksp.py --case "$case" --work "$work/runs/s24-r3-w2-a6" --executable "$eonsim" \
  --mpiexec "$petsc/bin/mpiexec" --ranks 1 2 4 --modes direct strict-short inner inner-mgs preset
python compare_arterial_ksp.py --archive arterial-solvers.json.xz --csv "$work/arterial-solvers.csv"
```
