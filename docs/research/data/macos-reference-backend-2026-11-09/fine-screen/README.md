# Actual fine N800 reference backend proof and fresh adoption

Based on028d6aa; S24 level1, N800, physical32-cycle definition with16-cycle
ramp. 100 startup steps each for old FSILS, candidate FSILS and candidate ILUT,
then actual ILUT90→100 replay. Every numerical run and full equation audit passed.
100/100/10 state pairs satisfy the predeclared repository limits: nodes2e-9,
exact P1 relative mass1e-8, native history and saved equation norms2e-9. Exact
native time is required separately; actual replay is bitwise algorithm-identical
except elapsed diagnostic. Candidate FSILS equals old fields/history exactly.

Independent raw reread reconstructed tetrahedral volumes and mass integration
and decoded every full native record. It reproduced maximum ILUT node9.3306e-22,
relative mass1.15594e-19, history5.86888e-19 and saved-norm2.09443e-28; replay
all differences zero. All physical/nonlinear thresholds remain unchanged. The
previous coarse extra exact-norm failure is retained separately, not overwritten.

Actual commands (one OpenMP/BLAS thread):

```sh
build/analysis-venv/bin/python build/recompute-20261109/screen-reference-fine-backend.py
build/analysis-venv/bin/python build/recompute-20261109/review-reference-fine-backend.py
build/analysis-venv/bin/python build/recompute-20261109/run-reference-elastic.py --level 0 --n 800 --backend fsils
build/analysis-venv/bin/python build/recompute-20261109/run-reference-elastic.py --level 1 --n 400 --backend ilut
build/analysis-venv/bin/python build/recompute-20261109/run-reference-elastic.py --level 1 --n 800 --backend ilut
```

The last three are newly launched full zero-state computations, not completed
qualification. Each uses the actual frozen corresponding EON case, retains all
32cycles and16-cycle ramp, and saves all final three cycles plus the real preceding
endpoint. Original FSILS is retained for coarseN800; explicit ILUT is used for
fineN400/N800 after the reviewed correctness proof. Startup ILUT154.94s was
slower than old FSILS83.05s; no local speedup is claimed. The existing historical
fine-reference solver difficulties motivate this available backend, but its new
full convergence/physics/budgets must still pass independently.

Execution records bind source inputs, binary and proof hashes; guards enforce
3GiB RSS,20GiB free disk,24h/run. Raw proof remains locally available in
build/recompute-20261109/reference-fine-backend-screen; these reports do not
embed its snapshots. No old omitted raw data was used.
