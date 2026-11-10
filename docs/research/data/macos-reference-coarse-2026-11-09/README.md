# Fresh reference coarse N400 mesh-nu0, 2026-11-09

Fixed svFSI7bdb74c, serial Mac executable recorded in execution.json, physical
solid nu=.3 and separately selected mesh-motion nu=0. All12800 steps/32cycles
were computed from zero with the complete16-cycle ramp. Solver returned0.

Actual full equation audit (exit0):

```sh
python3 scripts/audit_svfsi_convergence.py --work build/recompute-20261109/reference-elastic-s24-l0-n400-nu0 --log build/recompute-20261109/reference-elastic-s24-l0-n400-nu0/solve.log --output build/recompute-20261109/reference-elastic-s24-l0-n400-nu0-convergence.json
```

All25600 final equation rows pass the unchanged relative1e-10 criterion;
maximum ratios FS3.7e-11/MS9.6e-11, maximum3iterations, no iteration-cap rows.
This is convergence evidence only. Final-three-cycle full-field audit is
running(session51289), not yet qualified. The full new raw trajectory remains
local. Historical mesh-nu.3 failures and physical/error-budget gates remain.

The field audit(session51289) has now returned0: five-field cycle maximum
6.6115e-6<1e-5, kinematics0, stage mass5.4210e-18, divergence defect5.3816e-18,
and positive Jacobians. Lamé mean error3.1950432% still fails2%; fine and
independent budgets are required. This result does not qualify the coarse grid.
