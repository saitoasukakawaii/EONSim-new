# Default FSI N1600 complete error budget — FAILED

Source checkpoint: 552274d. Native macOS arm64, PETSc3.25.6 production inputs, serial numerical runs; analysis uses analysis-venv Python with OMP/OPENBLAS/VECLIB threads1. Main-lock PETSc3.23.7 not verified by this result.

Executed: `build/analysis-venv/bin/python build/recompute-20261109/analyze-elastic-n1600-budget-streaming.py --solver eonsim --output build/recompute-20261109/elastic-n1600-budgets-streaming`. Session65569 terminated with exit1 and explicit `Independent N1600 error budget failed`; complete reports exist, rather than an interrupted analysis.

All producer periodicity/quality/positive geometry prerequisites pass. Space1600/time800/tail1600 phases and sampling1600 dense phases use original norms and10% gates. Time/space ratios: fluid velocity15.49172685%, fluid pressure37.34021239% FAIL; solid velocity7.83666780%, solid displacement2.35844069%, mesh displacement2.27562635% PASS. Every tail and sampling term passes. Overall passed=false. These are discrete difference budgets, not a proof of exact-solution error or convergence order; no attribution to stabilization alone is established.

All JSON reports are retained as gzip with uncompressed byte counts/SHA and compressed SHA in verification.json. Independent capture checked all4800 restored members against source receipt SHA, member SHA/size and absence after cleanup: coarseN1600 3200, timefineN800 1600. Peak restored frame597422/4479210B. Complete physical validation remains separate; it previously passed for fineN1600.

Next: retain failure, complete held tau-time diagnostic and remaining reference/length/Womersley tasks; do not relax gates or claim qualification. Final fine-volume archival now allowed after consumer exit, but its independent archive verification is a separate pending task.
