# Mesh-equation backend diagnostic (completed; all failed)

Session88443 runs bounded serial continuations401..540 from the fresh fineN800
native step400, before the first unproven convergence at491. The complete prefix
report proves every equation through400; its hash and seed hash are frozen.
No old-workspace data is used. Physical inputs, dt, nonlinear30/1e-10 and linear
1e-12/1e-26 remain unchanged. Three sequential cases are original meshCG/FSILS,
meshGMRES/FSILS, meshGMRES/Trilinos-ILUT (native assembly). FSI remainsGMRES/ILUT.
Source inspection confirms READFILES.f permits these explicit choices.

All cases save every accepted state and native checkpoint for later field/history
review. Each has a2GiB RSS cap,20GiB diskfloor and1800s timeout. The original
convergence auditor writes failures as evidence instead of aborting comparison
of remaining candidates. A diagnostic restart is not production eligibility:
no changed-backend continuation will be promoted without bounded independent
review and a fresh valid full trajectory. No option is adopted yet.

The concurrent fineN400 production prefix1..845 separately passes1690 final
equation rows with no iteration cap (MS max9.9e-11). This is only a frozen prefix,
not full convergence. Its full raw log remains local under the production workdir.


## Failed candidates retained; final candidate running

CG/FSILS completed401..540, failed convergence,1696.13s. GMRES/FSILS frozen
completed401..518 also fails26 MS steps, maxratio1.4e-10 with iteration cap.
Its exact owned solver was terminated after proof of failure. Original
controller88443 exits1, failure/log/partial state retained. A partial receipt
includes only401..518, never the unfinished tail or nominal540 endpoint.

Continuation66484 runs only the previously unstarted GMRES/ILUT401..540 from
the same verified original step400. It preserves the original controller
failure. Later field diagnostics must use each candidate's actual completed
range; comparison to a failed baseline is diagnostic only, never qualification.

## All three candidates failed

ILUT continuation66484 terminated1 after its frozen401..498 prefix failed9 MS steps
(maxratio1.1e-10). Original failed outputs and partial tail remain local.
Analysis25784 completed0: GMRES-FSILS118 pairs and GMRES-ILUT98 pairs versus
CG have maximum node differences2.66816e-19/1.75336e-19, relative P1 mass
5.67505e-17/5.29594e-17, native history1.32166e-16/9.86739e-17. Saved time and
equation norms are exact. These small differences do not qualify a failed
trajectory. No candidate is adopted. Frozen small evidence is in `completed/`;
all full raw fields/checkpoints remain local.

Command: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
build/analysis-venv/bin/python build/recompute-20261109/analyze-reference-mesh-diagnostic.py`.
Base svFSI7bdb74c, macOS arm64, GNU Fortran16.2, Trilinos13.2,1rank/1thread.
