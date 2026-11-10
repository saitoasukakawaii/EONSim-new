# Fresh elastic fine N800 physical audit

All25600steps/32cycles from zero,16-cycle ramp. Original post-solve index failure retained; both numerical phases completed0, contiguous steps and corrected index input hashes independently checked. No numerical rerun. Full last2400frames plus preceding23200endpoint audited. summary.json records actual passed/failed physical gates without changing any threshold. Full audit compressed and decoded readback exact, complete raw manifest retained.

Audit command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n800/case.json --work build/recompute-20261109/elastic-s24-l1-n800 --first-step 23201 --output build/recompute-20261109/elastic-s24-l1-n800-audit.json`. All physical checks passing would still not establish independent budgets or final production qualification.
