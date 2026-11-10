# Fresh fine-grid startup validation, 2026-11-09

Source solver: snapshot `92fef88`; controller prepared on `e6a01a7`, persisted
in `f1defb3`. Serial default MUMPS, PETSc 3.25.6, one thread. This is startup
execution validation only; no periodic or physical qualification is claimed.

The controller ran 32 fresh steps on S96 level 1 (50,609 nodes), with direct
factorization before and after window-8/window-32 trials, then replayed steps
17–32 from the window-32 checkpoint. All five runs succeeded with respectively
32/5/2/32/1 numerical factorizations. Window 32 took 74.89 s versus direct
470.00/471.33 s and window 8 114.30 s; shared-host timings are local evidence.
Peak RSS stayed below 3.84 GB (predeclared 6 GiB limit).

All 112 state pairs / 560 datasets were read and compared. Metadata and clocks
are exact; maximum node difference is 7.46e-17 and normalized mass difference
5.61e-15, below unchanged 2e-9 / 1e-8 limits. An independent raw reread rebuilt
tetrahedral volumes and linear mass integration and reproduced those results.
The first invocation of that reread script had an unclosed-parenthesis syntax
error; it executed no comparisons. The corrected retained script returned 0.

Actual commands from repository root:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/screen-alpha1-fine.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/review-fine-screen.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/run-womersley-fine.py --alpha 1 --n 400
```

The last command launched a **new zero-state six-cycle fine study**, not a
continuation from the 32-step screen. It is still running. The guard monitors
its entire process-group RSS, free disk and elapsed time; no tolerance changes.
The full raw screen remains locally available at the manifest location; only
small logs, definitions, checksums and review scripts are committed here.
