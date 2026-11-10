# Fresh elastic fine N400: final-three-cycle physical audit passes

All12800 accepted steps,32 cycles/16-cycle ramp, from zero; snapshot92fef88
EONSim Release, macOS arm64/PETSc3.25.6, serial MUMPS/LU32. Controller52281
failed only after both successful solves while collecting the wrong restart
PVD name; original failure remains. `finalize-elastic-series.py` verified
contiguous logs and built indexes without another solve.

Audit32102 exit0, actual preceding endpoint11600 and every step11601..12800.
Worst five-field cycle maximum2.472978085e-07<1e-5; kinematics5.42102e-20,
stage mass7.06900e-17, divergence theorem1.18914e-17. Both Jacobians positive.
Lamé mid-ring mean0.000107381650327036, expected0.000108727272727273, relative error
1.237612575%<2%. Independent error budgets and matched reference remain
required; coarse3.195% failure is preserved, not replaced by this result.

Command: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case
build/recompute-20261109/elastic-s24-l1-n400/case.json --work
build/recompute-20261109/elastic-s24-l1-n400 --first-step 11601 --output
build/recompute-20261109/elastic-s24-l1-n400-audit.json`.

Full raw hashes remain in this evidence, raw data local. Complete audit is
losslessly compressed and read back; all consumed source inputs are bound.
No full physical or48h-completion claim.
