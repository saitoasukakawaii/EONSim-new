# Fresh loaded elastic local proof, 2026-11-09

Controller/source checkpoint: `5d695b6`; unchanged solver `92fef88`, local serial
PETSc 3.25.6 MUMPS. The source is the newly computed S24 coarse N800 step 19200
(cycle 24), after the full 16-cycle ramp. No old omitted trajectory is used.
Its complete checkpoint is frozen and hashed; original production continues.

Actual commands, from repository root with one OpenMP/BLAS thread:

```sh
build/analysis-venv/bin/python build/recompute-20261109/review-loaded-elastic.py
build/analysis-venv/bin/python build/recompute-20261109/analyze-loaded-elastic.py
```

All five numerical runs completed successfully: 32 steps direct/window8/window32/
direct, and 16-step restart from the actual cached midpoint. Numerical LU counts
were 32/4/1/32/1. The first controller then failed collecting `solution.pvd`:
the driver correctly appends `_restart19200` (or `_restart19216`) to the output
stem. The original exit-1 log and failure report are retained. The second
command ran analysis only on the completed files with the actual filenames;
it invoked no solver and returned 0.

112 full checkpoint pairs / 1232 HDF datasets and 224 domain-frame pairs passed.
Clock/metadata are exact, maximum history node delta 1.1061e-14 and exact P1
field relative mass delta 8.0198e-14 are below unchanged 2e-9/1e-8 limits.
All history datasets were checked, including rates and accelerations.

The predeclared cost gate **did not pass**: window32/direct ratios .4998/.7494,
but window32/window8 .99915 exceeds .9. These few-second measurements include
one-second process polling on a shared host. Correctness and factor-count proof
stand separately; no superiority to window8 or whole-run performance is claimed.
This local loaded window is not final periodic/physics/budget qualification.

The same output-stem assumption exists in the three active elastic production
controllers' final index collection. Their numerical phases are unaffected.
`finalize-elastic-series.py` is an analysis-only postflight repair: it verifies
complete accepted-step logs, successful phase receipts and both original PVD
series before creating new root indexes; it refuses to overwrite existing
indexes and preserves any original failure. It has only been syntax checked;
actual production use is pending numerical completion. Do not restart a finished
numerical study because its index collection failed.
