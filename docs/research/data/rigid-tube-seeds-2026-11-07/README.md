# PROD-02 continuation: seed-mesh and field diagnostics (2026-11-07)

Source: `4113ab8300410459dbfb057db5d4978e7d106aa7` (same Git tree as locally tested
`40b8727`, tree `45019c8e3cad006f1da30bb5ae0502a6905a868c`). Numerical solver
source is unchanged from branch baseline `92d63f1`; main was `dc37852`.
This is a checkpoint toward PROD-02, **not full production-FSI acceptance**.
No new PR or automatic merge. Existing PR #38 remains the same branch's review vehicle.

## Actual results

Five new serial steady Stokes solves, unchanged R=1, L=2, rho=mu=1, drop=.02,
default stabilization and 1e-11/1e-13 solver tolerances. Seed meshes use the existing
conforming generator, with no red refinement or projection. No performance claim.

| Sectors/radial/axial | Nodes | Flow error % | Velocity relative L2 % | Pressure RMS/drop % | End-pressure-drop error % | Div RMS/(Umean/R) % |
|---|---:|---:|---:|---:|---:|---:|
| 48/4/8 | 1737 | 3.443716 | 2.494998 | 2.651264 | 15.962995 | 12.525451 |
| 48/8/16 | 6545 | 1.224779 | 1.017892 | 1.086669 | 8.855226 | 6.227308 |
| 96/8/16 | 13073 | 0.979268 | 0.566005 | 0.806285 | 7.058661 | 4.408183 |
| 48/16/24 | 19225 | 0.311138 | 0.714765 | 0.570462 | 5.790738 | 3.576921 |
| 96/12/24 | 28825 | 0.546409 | 0.320760 | 0.489014 | 5.140012 | 2.937791 |

The 96/12/24 case meets the isolated flow <1% and velocity L2 <2% targets.
This does not certify the full stage: end pressure is still 5.140012% off, local
divergence remains nonzero, and no transient/elastic-wall/svFSI qualification was
performed. A smaller flow error on the 48/16/24 case does not establish better
whole-field accuracy: geometry and discretization can cancel. No asymptotic order
or exact separation of geometry and field error is claimed.

The 96/8/16 mesh was actually solved on 1/2/4 ranks. Maximum serial-to-parallel
nodal field difference is 5.30825383648903e-16. Full metrics are in `mpi.json`.
The new pressure and divergence metrics are diagnostic outputs, not newly chosen
pass thresholds. Velocity L2 is integrated on each actual polygon domain, with
the circular analytic velocity restricted to that domain.

The previous eleven-state archive was relocated and all 110 extracted file hashes
verified. The four 48-side fields were reprocessed (not re-solved). At red level 3,
velocity L2 error is 1.979227%, pressure RMS/drop 0.928730%, and normalized divergence
RMS 3.069720%. End pressure and domain pressure RMS measure different errors.

## Verification and failures

- Restored pinned PETSc 3.23.7 using `scripts/cloud/restore.sh` in this fresh Linux
  container (8 CPUs, 8 GiB cgroup RAM). No PETSc 3.19.6 install or test.
- Repository Release explicit selection `rigid_tube_verification`: 1/1 passed,
  including serial/distributed smoke comparison. Runtime preflight passed after
  setting process-local OpenMPI/PRRTE root-run acknowledgement in this root container.
  The initial root-run rejection is retained in `initial-root-preflight.log`.
- `python3 tests/test_rigid_tube_fields.py`: 6/6 passed; all barycentric monomials
  through degree four, a skew affine tetrahedron, exact pressure moments, divergence
  cancellation, and invalid input. First zero-velocity oracle used an incorrect
  hand-computed integral 19/210; expanding the polynomial gives 1/9. Corrected the
  test oracle; the implementation and all degree-four moments already agreed.
- `python3 tests/test_rigid_tube.py`: 3/3 passed.
- `python3 tests/test_ci_selection.py`: 26/26 passed. New script paths are mapped.
- Existing C++ residual/Jacobian, stabilization, stopping criteria and defaults are
  unchanged. Debug historical evidence is reused, not a new Debug run. No new FSI
  cycle, restart, svFSI, physiological or multi-node verification is claimed.
- Source self-review: pressure offset is retained; squared-error quadrature is
  degree four; divergence is the exact constant P1 element divergence; owned field
  coverage and ghost agreement are checked by the existing reader. No independent
  reviewer was used.

## Reproduce

Activate the locked environment as in `scripts/cloud/run.sh`, then:

```sh
python scripts/study_rigid_tube_seed.py --executable build/cloud-3.23.7-release/eonsim --work /tmp/tube-seeds --seed 48 4 8 --seed 48 8 16 --seed 96 8 16
python scripts/study_rigid_tube_seed.py --executable build/cloud-3.23.7-release/eonsim --work /tmp/tube-seeds-fine --seed 48 16 24 --seed 96 12 24
# Raw evidence can be relocated; no executable is needed for the replay:
tar -xJf raw.tar.xz -C /tmp/replay
python scripts/study_rigid_tube_seed.py --work /tmp/replay/tube-seeds --seed 48 4 8 --seed 48 8 16 --seed 96 8 16 --analyze-only
python scripts/study_rigid_tube_seed.py --work /tmp/replay/tube-seeds-fine --seed 48 16 24 --seed 96 12 24 --analyze-only
```

For MPI, copy the 96/8/16 serial case to separate rank-specific directories; run
`eonsim -case case.json -prepare parts -parts N`, followed by
`mpiexec -n N eonsim -case case.json -partition parts` for N=2,4.
Read fields with `study_rigid_tube.fields(directory,N)` and audit with
`audit_rigid_tube_fields.audit(directory,96,0,N)`. `raw.tar.xz` includes those actual
partitions, original logs and fields, plus all five serial states; `manifest.json`
records every extracted file hash. Summary files preceding the final velocity-audit
extension are retained verbatim; `seed-coarse.json`/`seed-fine.json` are the final
reanalysis and supersede their diagnostic field lists, without modifying the solves.

Remaining work: pressure-trace/local-divergence convergence and a complete error
budget, Womersley/time convergence, elastic tube and wall accuracy, fixed-version
svFSI comparison, and full-stage acceptance/review. No full-stage completion claim.

Final relocation check: all 95 new archived files matched their SHA-256 hashes;
both fine seed states were reanalyzed from the relocated archive and every final
metric matched exactly. See `replay.json`. This is postprocessing replay, not a
repeat numerical solve.
