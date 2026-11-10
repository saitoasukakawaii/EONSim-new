# Fresh Womersley budget preparation and independent arithmetic checks

Based onb9dff4c. `audit-womersley-budget.py` consumes the actual six-cycle
coarse/target/dt-half studies and their completed analytic reports. It refuses
missing or partial receipts before loading fields or creating output. Physical
and solver definitions must agree except red level, timestep and full phase
count; the time-control mesh must be byte-identical to the target mesh.

Space/time/tail differences use the existing exact P1 compare_womersley
implementation. Sampling is the field difference between every accepted target
phase and linear reconstruction of every-other actual phase, including the real
cycle5 endpoint. The cache retains only neighbouring frames. Each time/tail/
sampling relative RMS must be strictly below10% of the spatial field difference;
there is no Richardson rescaling, pressure gauge fit, or subtraction of scalar
analytic error norms. Original analytic and periodic gates are checked separately.
A numerical budget pass will not establish independent circular-geometry gates.

Every state read by the actual budget will be bound by checkpoint/manifest
SHA256 along with mesh, definitions, receipts, analytic reports and source hashes.
Failed budgets will be written as failed before the process exits nonzero.

Actually ran with one OpenMP/BLAS thread:

```sh
build/analysis-venv/bin/python build/recompute-20261109/test-womersley-budget.py
```

Four independent checks passed: analytic sinusoidal interpolation error on a
unit tetrahedron (E[x²]=1/10 and E[(1+2x)²]=12/5, N8/16/400 and two phases),
exact affine-time reconstruction, mandatory use of a perturbed real preceding
endpoint, and rejection of incomplete/mismatched families. These establish
arithmetic and guards, not production budget values.

The subsequent CLI preflight was actually invoked with running alpha1 fineN400
and fineN800 inputs. It rejected incomplete fineN400 before creating
alpha1-n400-budget.json. The refusal log is retained. The mathematical helper
functions were unchanged by the CLI preflight addition; no solver or unrelated
regression was rerun. All production budget results remain pending.
