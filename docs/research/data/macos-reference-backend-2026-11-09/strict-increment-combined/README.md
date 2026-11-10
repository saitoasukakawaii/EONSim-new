# Combined strict relative stop and mesh increment: diagnostic only

Separate derivative of fixed svFSI7bdb74c with exactly PIC.f strict-stop and
MESH.f stable stage-increment changes. Neither original source nor component
binaries are overwritten. Configure20492 and build90046 completed0; same
CMake3.31.10/GNU Fortran16.2/Trilinos13.2 Release settings as component proofs.

FineN800600 steps from zero: session82743 completed0,1200 final equation rows passed; a fresh-process audit also passed. Field/native140-pair comparison50574 is running. CoarseN800100 steps from
zero:26407 completed0, all200 final equation rows passed, no cap. Both use exact original physical inputs and relative
tolerances, explicit2GiB RSS/20GiB disk/3600s bounds,1rank/1thread.
No old raw seed or continuation; original failed trajectories are retained.
This tests interaction/startup of the two separately verified modifications,
not a production run or full reference qualification. The user now permits recorded validated patches. Formal adoption still needs
the combined fine startup and field checks; permission is no longer pending.

Run scripts bind component convergence, normal-path equivalence, independent
native review and140-pair fine-field evidence by SHA before solving.
Commands: `build/analysis-venv/bin/python build/recompute-20261109/
screen-reference-strict-increment-startup.py` and analogous coarse-startup.py
with OMP_NUM_THREADS/OPENBLAS_NUM_THREADS/VECLIB_MAXIMUM_THREADS=1.
