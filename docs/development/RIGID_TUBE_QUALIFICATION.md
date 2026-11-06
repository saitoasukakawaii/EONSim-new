# Rigid tube: mixed end conditions and steady flow qualification

FSI-PROD-02A is a bounded first increment of PROD-02. It verifies the steady
pressure-to-flow quantity in a fixed tube. It does not qualify transient FSI,
the pressure field, elastic-wall response, physiological parameters or svFSI
agreement. The full production stage remains open.

## Boundary interface

Fixed-grid `fluid.boundaries` may contain several entries for the same positive
physical tag when their Cartesian `components` are disjoint. Pressure now accepts
`components`, just as velocity and traction do. An omitted list means `[0,1,2]`.
Overlapping entries fail even if their values agree; components omitted from all
entries retain zero natural traction. Constraints on intersecting tags retain
the existing value/ramp consistency check. Solid tags remain distinct.

For a tube along x, the inlet at x=0 uses:

```json
[
  {"tag": 1, "type": "pressure", "value": 0.02, "components": [0]},
  {"tag": 1, "type": "velocity", "value": [0,0,0], "components": [1,2]}
]
```

The outlet uses the same split with pressure zero. The side wall has all three
velocity components zero. These conditions prescribe normal stress and zero
transverse velocity; they are compatible with fully developed Poiseuille flow.
Prescribing full pressure traction on both ends would additionally prescribe
zero tangential traction, which is not the same exact reference problem.
Components are global coordinates, not projections onto an arbitrary face frame.

Pressure normalization is checked after component constraints are merged on the
actual mesh: a closed normal-velocity boundary needs a gauge/mean normalization;
a free normal trace must not have one. Tangential natural data alone do not remove
the pressure nullspace. Diagnostics integrate each physical tag once. Checkpoint
signatures include every entry; reordering entries is allowed, changing selected
components or values is rejected.

## Reference and refinement

Internally consistent synthetic units: R=1, L=2, rho=mu=1, imposed normal-stress
drop 0.02. Steady Stokes, no time stepping, Re=0.0025 and alpha=0. The circular
reference is

\[
u_x=\frac{\Delta p}{4\mu L}(R^2-y^2-z^2),\quad
p=\Delta p(1-x/L),\quad Q_\circ=\frac{\pi R^4\Delta p}{8\mu L}=\frac{\pi}{800}.
\]

See the derivation in [UC Berkeley Bioengineering, §43, Flow rate from the velocity profile](https://ucb-bioe.github.io/textbook/chapters/05_diagnostics/07_poiseuille.html).

The mesh starts from `cases/fsi/generate_tube.py` (two radial and two axial
subdivisions). Every red refinement splits each tetrahedron into eight, preserves
the polygon and does not project boundary midpoints back onto a circle. A separate
12/24/48-side comparison changes geometry. These comparisons are not an exact
decomposition of total error: residual field error remains in every geometry.

An independent continuum geometry bound follows by including the inscribed
polygon between disks of radii R cos(pi/s) and R. The cross-sectional Poisson
problem and domain monotonicity give

\[
Q_\circ\cos^4(\pi/s)\le Q_{\mathrm{polygon}}\le Q_\circ.
\]

This is a bound on the continuum polygon solution, not on the stabilized FE
solution. Domain monotonicity and disk scaling are stated in
[Briani, Buttazzo and Prinari (2021), §1, equations (1.2)–(1.4)](https://doi.org/10.1007/s00245-020-09727-7).
Using them for pipe conductance is the deduction above.

The production Tet4/P1 velocity-pressure residual is unchanged. Default steady
stabilization is tau=h²/(4 mu), h=(6 V)^(1/3); the transient dt-dependent term is
absent in this problem. Solver tolerances remain relative 1e-11, absolute 1e-13,
maximum 30 iterations. No stabilization/solver threshold was tuned to pass.

## Acceptance and replay

The predeclared flow gates are circular-reference error <2% at the finest
48-side state; decreasing fixed-polygon successive flow changes, with the last
change <1% of Q_circle for both 12 and 48 sides; 1/2-rank field difference <2e-9;
net outward flux <1e-10. The 12-side grid extends to level 4 and the 48-side grid
to level 3 because the original level-2 stop failed the unchanged 1% gate.
The small CTest is only a regression smoke test, with its own 20% flow limit;
it is not a rerun of the full qualification study.

```sh
python scripts/study_rigid_tube.py --executable /path/to/eonsim --work /tmp/tube --study
# Append individual states without repeating previously completed solves:
python scripts/study_rigid_tube.py --executable /path/to/eonsim --work /tmp/tube --case 12 4
# Recompute from an extracted archive; no executable or original absolute path needed:
python scripts/study_rigid_tube.py --work /tmp/tube --study --analyze-only
```

Results, source identity, commands, failures and remaining limitations are recorded
in [the dated evidence](../research/data/rigid-tube-2026-11-06/README.md). Global
mass balance and a small last flow change do not establish pointwise
incompressibility, pressure accuracy or an asymptotic convergence order.
