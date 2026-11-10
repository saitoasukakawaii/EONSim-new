# Fresh elastic coarse N800 numerical completion, 2026-11-09

Unchanged solver snapshot92fef88, fresh Mac serial MUMPS, S24 level0, N800,
32 full cycles with 16-cycle pressure ramp. All25600 accepted steps completed
contiguously: early1–23200, dense23201–25600. Both solver phases returned0.
The original controller subsequently returned1 while opening the wrong fixed
PVD name; original failure and logs remain. This was collection failure, not
an incomplete numerical solve.

Actual analysis-only repair, with no solver invocation:

```sh
python3 build/recompute-20261109/finalize-elastic-series.py --work build/recompute-20261109/elastic-s24-l0-n800
```

It returned0 after verifying phase receipts, every contiguous step and both
actual output series, creating root indexes referencing existing files only.
The copied completion-postflight record hashes those inputs and indexes.
The previous failure is not rewritten as success. Raw trajectory remains local.

Full final-three-cycle audit completed with exit0:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l0-n800/case.json --work build/recompute-20261109/elastic-s24-l0-n800 --first-step 23201 --output build/recompute-20261109/elastic-s24-l0-n800-audit.json
```

All physical and independent error-budget qualification remains pending.

The final2400 states pass five-field periodicity (worst relative maximum
6.3223e-7), interface kinematics5.4210e-20, stage mass7.3726e-18 and divergence
defect5.5580e-18; both Jacobians stay positive. The mid-ring mean displacement
is0.0001052534094804 versus plane-strain Lamé0.0001087272727273: **3.1950247%**
relative error, which **fails2%**. This is coarse-grid failure, retained for the
matched fine-grid study; completion is not full qualification.
