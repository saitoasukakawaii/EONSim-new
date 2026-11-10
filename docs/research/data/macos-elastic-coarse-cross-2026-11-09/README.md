# Fresh coarse N800 matched-program comparison

Both completed32-cycle coarse studies use identical mesh/physical case and complete final-three-cycle audits. Reference explicitly matches adopted binary/patch. Unchanged captured observable comparison kernel completed0, but `observable_gates_passed=false`: mid-pressure amplitude difference3.5987271% exceeds original2%; phase0.9010863deg is within1deg. Radial displacement and projected-area amplitude differences3.4847366% pass5%; left/right flow1.9043412%/1.8767219% pass5%, flow phases0.7322452/0.7587315deg pass2deg.

Both coarse Lamé errors remain above2%. This is failed coarse accuracy evidence, not target qualification. Full800-phase nodal-field comparison37985 is running separately. Fine target comparison and both independent budgets still required. Comparison program exit0 means report creation, not gate acceptance.

Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/compare-pressure-audits.py --eonsim build/recompute-20261109/elastic-s24-l0-n800-audit.json --svfsi build/recompute-20261109/reference-kinematic-long-elastic-s24-l0-n800-nu0-audit.json --output build/recompute-20261109/elastic-coarse-n800-cross-observables.json`.

Update:37985 completed0, all800actual final-cycle phases compared with exact P1 mass. Relative RMS differences: fluid velocity0.9120046%, pressure1.5856170%, fluid mesh displacement11.7467570%, solid velocity1.1992148%, solid displacement1.1991709%. These are pairwise differences without an invented field acceptance gate or causal attribution. Observable pressure-amplitude failure remains. Full consumed-file hashes retained in compressed report, decoded readback exact.
