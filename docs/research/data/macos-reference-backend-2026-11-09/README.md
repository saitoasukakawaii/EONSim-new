# Local pinned reference backend checks, 2026-11-09

Unmodified svFSI7bdb74c rebuilt with unmodified Trilinos13.2.0 tag commit
4a5f7906a6420ee2f9450367e9cc95b28c00d744 in project-local directories.
CMake3.31.10, AppleClang21, gfortran16, MPI, Accelerate, AztecOO/Ifpack/ML;
configure/build/install and independent svFSI build returned0. Original solver
and system dependencies were not modified. Compiler deprecation/legacy
Fortran warnings and duplicate-library link warning remain in actual logs.
Binary hashes and all local screen definitions are retained.

Actual screen command with one OpenMP/BLAS thread:

```sh
build/analysis-venv/bin/python build/recompute-20261109/screen-reference-backend.py
```

Seven numerical runs all returned0 and passed full equation convergence:
20-step startup old/new-FSILS/new-ILUT; 20 loaded steps from newly computed
native12400 with the same three modes; actual ILUT12410→12420 replay.
The first collector failed because startup filenames use zero padding.
Analysis-only recovery first encountered the nonnumerical stFile_last alias,
then reported an exact saved-norm assertion. Both failed attempts are retained;
no solver was rerun. The final analysis uses unique integer-step lookup and
reports every result, preserving **passed=false, adopted=false**.

New-FSILS equals original exactly. ILUT loaded maximum field node delta
2.3939e-16, relative P1 mass4.1888e-14, native-history delta7.5809e-14;
loaded replay is exact. Startup ILUT fields/history pass original2e-9/1e-8
limits, but saved equation norm differs8.0661e-28 and fails this screen's
extra exact-equality check. Do not erase or promote that failed check.

The repository's existing reviewed-backend native-norm limit is2e-9
(svfsi_restart_evidence.py), not bitwise equality. A separate actual fine
S24/L1/N800100-step screen explicitly uses that existing bound, retains
exactness as a diagnostic, and includes actual90→100 native replay. It is
running(session25864), not yet passed or adopted. Its initial input is freshly
exported from the actual EON fineN800 case; no old trajectory is used.

Raw files remain in build/recompute-20261109/reference-backend-screen. These
small reports/logs do not embed the raw snapshots. Full physics and independent
budgets remain pending. No source patch, tolerance relaxation or PR push.
