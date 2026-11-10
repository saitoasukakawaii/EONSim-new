# Fresh loaded two-rank elastic proof (completed)

The source is the freshly recomputed S24 level0 N800 case, with the same binary,
meshes, physical parameters and 16-cycle ramp. A separate two-rank trajectory starts
from zero and computes 19200 steps (24 cycles), then saves 32 fully loaded steps.
A same-partition restart replays the last 16 steps. No old raw data or serial
checkpoint is used as parallel initial state.

The explicit local `-mat_mumps_icntl_20 0` option is required by the independently
observed PETSc/MUMPS failure on this host. This does not qualify default parallel
MUMPS. Early output/checkpoint cadence is 800; every physical step is computed.
The process-tree RSS cap is 3 GiB, free-disk floor 20 GiB and phase timeout 24 h.

Original session97507 ended1 in a postflight assertion; no solver failure. The prepare receipt records
only successful partition construction. The analysis entry refuses incomplete
numerical phases before creating a result (captured preflight exit 1).

After completion, compare all five global fields to the existing fresh serial
loaded proof (node <2e-9, scaled P1 RMS <1e-8), exact v4 clocks, and every native
history dataset in both ranks for the 16-step replay. Serial and parallel native
layouts are different and are not compared as flat arrays. Output topologies,
pieces and consumed raw hashes are checked. Final comparison passed; see the completion section below.
This short loaded proof does not replace the full 32-cycle physical/budget gates
or establish speedup. Raw files remain locally under build/recompute-20261109.

## Completion and retained postflight failure

The first19,200 steps completed successfully with contiguous accepted-step logs.
The controller wrongly required positive KSP reason even when SNES converges
without a linear solve. Only step1 has KSP0: zero linear starts/completions and
zero nonlinear iterations, residual5.5402905e-14 below unchanged atol1e-13.
All remaining19,199 steps have positive SNES/KSP reasons. Original failure and
log hash are retained. The continuation script verifies every row, input hash
and complete native checkpoint, then computes only loaded/replay windows.
Session24073 completed0; field/history analysis35426 completed0.

Serial vsMPI:64 domain-frame pairs, maxnode5.5164206536e-16, scaled P1 RMS
7.8964679020e-14. MPI restart:32 domain-frame pairs, maxnode4.4061976290e-16,
scaled P1 RMS6.8727626309e-14. All below original2e-9/1e-8 limits.
Two ranks ×16 replay steps =32 native pairs,352 datasets; maxhistory
9.3794872043e-15, exact clocks/metadata. All consumed raw hashes in report.
No cross-layout flat-history assertion, default parallel-MUMPS claim, speedup,
or full32-cycle physical/budget qualification. The full transient was not rerun.
