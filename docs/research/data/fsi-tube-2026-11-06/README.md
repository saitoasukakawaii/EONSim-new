# FSI-PROD-01 evidence

Implementation: remote `718b7a6bb97fbb5eed09829a0bb7225d3963ee5f`, based on main `dd27eef`.
This has the identical Git tree `8b0adc8bd3b206576cefd9a0e90e5314397d24ec`
as locally tested implementation commit `31a04e642127182073109d1994b3982a917e5887`.
Uploaded with GitHub API after CLI push failed for missing HTTPS credentials.
Builds began before the implementation commit, so harness receipts report the
base SHA and a dirty tree. Source implementation is the committed patch above;
only test metadata labels changed after Release configuration. No solver
source changed between the accepted builds and the implementation commit.

Restore and build/run commands (repository root):

```bash
bash scripts/cloud/restore.sh 3.23.7 /workspace/scratch/eonsim-cloud
# build/tube-tests.json: {"tests":["fsi_tube","fsi_flow"]}
# build/tube-only.json: {"tests":["fsi_tube"]}
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 bash scripts/cloud/run.sh 3.23.7 release explicit /workspace/scratch/eonsim-cloud build/tube-tests.json
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 bash scripts/cloud/run.sh 3.23.7 release explicit /workspace/scratch/eonsim-cloud build/tube-only.json
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 bash scripts/cloud/run.sh 3.23.7 debug explicit /workspace/scratch/eonsim-cloud build/tube-tests.json
python tests/test_tube_mesh.py
python tests/test_ci_selection.py
```

The root-only MPI flags apply to this container. Normal users do not need them.
Build script pins PETSc 3.23.7 and one BLAS/OpenMP thread per rank. These are
single-node correctness runs, not performance experiments.

Release: original rectangle `fsi_flow` passed in first-attempt.log. The first
tube attempt reached its negative test after the actual time/MPI/restart/Jacobian
checks; it incorrectly expected checkpoint mismatch when increasing the radius.
The solver correctly rejected nonzero inlet velocity at a clamped interface.
The test file was revised while that earlier Python process still held its old
code; traceback source text can therefore show the newer label. The corrected
complete tube test passed in release-tube.log. Failed attempt retained.

The final tube test uses a waveform change to test physics-signature rejection
and a separate oversized-radius case to test constraint conflict. Release
maximum 1/4-rank field difference 5.42899e-14, same-partition restart difference
zero, maximum stage mass residual 1.56125e-17, full Jacobian relative difference
9.92097e-9. Positive wall response and geometry gates pass for all three time
schemes. See release-metrics.json for per-scheme values.

Mesh tests: 2 passed; independent positive volumes, boundary incidence,
interface triangulations and polygonal geometry refinement. CI selection tests:
26 passed. No PETSc 3.19.6 run. No full suite, patient data, physiological
accuracy, default-tau qualification, svFSI comparison or multi-node scaling.

Debug: isolated full tube test passed (1/1, zero skips), and rectangle flow
passed in debug-first-attempt.log. Thus each mode has two distinct affected
CTest checks passed; this is not a full-suite result. See debug-tube.log and
debug-metrics.json.

Additional inspection (not an accuracy acceptance): at the final alpha endpoint,
the coarse free-interface nodal signed radial displacement spans
-1.2676731649431099e-5 to +6.582154500251932e-5. The test intentionally establishes
nonzero coupled response, not uniform expansion or an analytical wall solution.
Spatial resolution, transient effects and reference agreement need PROD-02
investigation before using this case for physical prediction.

Debug first attempt: tube failed at a negative-input subprocess with LLVM
OpenMP z_Linux_util.cpp(2125) assertion and PMIx unreachable, not the expected
application rejection. Old rectangle flow passed. Debug-first-attempt.log is
retained. Applied the previously documented environment-only PID workaround:
inspect /dev/shm/__KMP_REGISTERED_LIB_* and sequentially spawn/reap /bin/true
until a fresh PID exceeds the recorded maximum (bound 20000), then exec the
repository build script for only fsi_tube. No shared objects were removed,
no tolerances changed, and the exact LLVM root cause is unconfirmed. The exact
launcher is archived as run-debug-isolated.py.

Archived log text has trailing whitespace removed for Git diff hygiene.
`original-log-sha256.json` records the hashes before this cosmetic normalization;
original logs remain in the local build evidence directories.

## PR acceptance

[PR #37](https://github.com/saitoasukakawaii/EONSim-new/pull/37):
[Core numerical validation](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42170183765)
passed PETSc 3.23.7 Debug **31/31** and Release **31/31**, zero failures/skips.
[Website/draft isolation](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42170183717)
and incremental receipt passed. The optional historical PETSc 3.19.6 job was
intentionally skipped under the repository policy.

Tested merge-preview `92a28b597d3022637c5fe29700f2385c99910e64` has exactly
tree `8ef42cd7e716aa995b03030fa7ed0617e7e2c449`, identical to accepted local
and remote head `29d8082d46de44b194b158f69285b560dda053c8`. Job-reported
receipts are preserved in ci-receipt.json. This final follow-up only records
acceptance and the next quantitative-study scope; numerical evidence is reused,
not reported as rerun. No automatic merge or draft publication.
