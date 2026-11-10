# Patched reference long-prefix review — 2026-11-09 07:03 UTC

Source at review: 8c0095b. Exact per-case auditor commands, frozen logs, source/binary bindings and reports are retained in this directory. All runs are fresh zero-state, serial, with the previously adopted combined patch; no tolerance was changed.

Coarse N800 prefix 1..4917 FAILS: 1620 final equation rows reached the iteration limit; MS maximum relative residual 1.6e-10 against strict <1e-10. First unproven step474 prints equality1e-10 at iteration30. The exact owned solver PID67171 was terminated after freezing evidence; controller18416 exited1 and all raw retained. The startup100 pass did not establish long-run convergence. This trajectory cannot enter the formal error budget or supply a restart after the failed segment.

Fine N400 prefix1..571 and fine N800 prefix1..617 pass all equations without iteration caps, MS maximum9.9e-11. These are prefix checks only; both production trajectories remain active.

Next investigation: the stage-increment rearrangement still subtracts absolute Dn-Do. Inspect predictor/corrector and boundary coupling before proposing a mathematically equivalent increment evaluation. Root cause is not yet proven; no further patch has been adopted. Existing full studies and original failure evidence remain separate.
