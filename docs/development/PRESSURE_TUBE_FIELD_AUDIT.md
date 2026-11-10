# Equal-pressure elastic tube: field interpretation and audit

This is part of PROD-02, still in progress. The prepared problem has R=1,
outer radius1.2, length12, E=1000, nu=.3, both densities1, viscosity1 and
pressure `.02+.01*sin(t)` on both caps. Solid and ALE end caps are clamped.
Both codes use their own generalized-alpha implementation with rho_infinity=.5.
No nonlinear vascular or large-scale qualification follows from this study.
Implementation source: `2189a8c9589add9376c060ef4e4c2e871fdb0c60`.

The reference exporter now exposes the already studied independent ALE variant
as `--mesh-poisson 0`. The default remains0.3 and produces the original input
and manifest layout. The opt-in changes only the mesh equation and records
`mesh_motion_poisson_ratio` in `export.json`; the physical solid Poisson ratio,
mesh geometry, load, time integration and convergence tolerances are unchanged.
Only the two studied values0/0.3 are accepted; the zero variant is rejected for
fluid-only hydrostatic checks. It is not a correction of the original0.3
trajectory and does not inherit that trajectory's qualification. New independent
space/time/tail/sampling checks are still required for the selected variant.

The opt-in native restart chain v2 requires a binary digest per segment and an
explicit reviewed FSI-ILUT transition descriptor. Its proof must match the exact
physical case/input files and native rank layout and retain independent raw
100-state backend/10-state replay evidence, clean resource receipts, strict
convergence and the predeclared10% cost benefit. It cannot change the production
output grid, mesh backend or tolerances. V1 remains unchanged and rejects
implicit execution transitions. Every full-run field/convergence/physical gate
still applies. [Contract validation](../research/data/reference-backend-transition-contract-validation-2026-11-08/README.md)
passed with actual serial/two-rank proof bindings and the original S12 v1 chain;
no long backend handoff or whole-project qualification is claimed here.

## Output mapping

At pinned svFSI `7bdb74c`, `READFILES.f:READOUTPUTS` names both the FSI equation's
integrated velocity and the mesh equation's state `Displacement`. It supports
`Output: Alias`. The exporter now explicitly uses `Solid_displacement` for
the FSI equation and `Mesh_displacement` for the mesh equation. Without aliases,
a generic VTK reader may replace one array of that name; a successful solve
alone would not establish that both displacement fields were available.
This was found before the first coupled reference solve. The fluid-only
uniform-pressure result is unaffected; it has no displacement output.

`VTKXML.f:WRITEVTUS` writes reference coordinates and concatenates each mesh's
point/cell tables. `Mesh_ID` identifies the physical mesh; projected interface
points can occur in both tables. The auditor selects that mesh's cells, maps
their used nodes by reference coordinates and verifies every tetrahedron
against the original Gmsh input. Solid displacement is read only on the solid,
and ALE displacement only on the fluid. It does not interpret a solid-domain
pressure or the FSI velocity integral inside the fluid as a physical field.

EONSim writes deformed coordinates and a shared point table for the two domains.
The auditor subtracts the domain's own displacement, selects nodes used by that
domain's cells, then applies the same reference-coordinate/topology check.
Unused points have no physical meaning. Canonical mapping rejects missing,
duplicate, nonfinite or incorrectly shaped physical data.

## Observations and normalization

`scripts/audit_pressure_tube.py` evaluates exact P1 reference mass norms,
current tetrahedron Jacobians, cap/wall fluxes, the independent element
divergence integral, interface compatibility and clamped boundaries.
Mid-wall displacement is the reference-arclength mean radial projection on
the material ring at reference x=L/2, using four-point segment quadrature.
Its area is the ring's projected yz polygon area; axial displacement is
reported. Mid-pressure uses reference triangle-area weights on that material
section. These observations are not an Eulerian cut at the current x=L/2.
Both programs use the same definition; geometric sensitivity remains separate.

The fixed displacement scale is the infinite plane-strain Lamé compliance
times the oscillatory pressure amplitude. Compliance is recomputed from the
actual configured E, nu, radii; metadata radii and length are checked against
the mesh. Solid velocity uses omega times this displacement, fluid velocity
uses L/R times that velocity, and pressure uses the load amplitude. These
definitions are fixed before the first coupled results are examined. Full
field periodic acceptance requires both of the last two complete cycle
differences below 1e-5 at every stored phase. Harmonic sine/cosine coefficients
retain the reported mean and higher-harmonic RMS; no fitted time shift is used.

The nonlinear equations enforce continuity at the assembly stage. The audit
reconstructs that state from adjacent endpoints and alpha_f; EONSim's first
step is BE, while the reference uses alpha from its zero initial state.
The existing absolute stage-mass and divergence-theorem limits are 1e-9 and
1e-12; the kinematic vector-norm limit is 1e-12. Positive geometry is required.
Endpoint net flux and the trapezoidal volume-change budget are reported
separately and are not mislabeled as stage residuals. Time refinement must
bound the latter diagnostic's integration error.

## Checks and execution status

Five standard-library checks passed: affine deformed geometry/divergence,
exact consistent mass for a linear axial field, invalid data/topology rejection,
known mean/first/second harmonic, and deformed-coordinate reading with permuted
large node IDs plus an unused point. The regular-polygon mean radius has an
independent analytic segment integral. Updated exporter checks passed 3/3;
CI-selection checks passed 26/26. Actual coupled output reading and physical
comparisons remain **pending** at this implementation checkpoint.

The separate VTK9.6.1 environment subsequently read independent synthetic
two-domain fields: physical values were preserved exactly, reference coordinate
error was at most 1.11e-16, and a deliberately imposed .004 interface mismatch
was correctly detected. VTK actually ignored the second legacy Displacement
array; the new auditor rejected that ambiguous fixture. A second 48-snapshot
manufactured history exercised both complete analysis paths and recovered the
known pressure harmonics and distinct startup stage clocks. These are parser/
analysis checks, **not solver results**. All 185 fixture/evidence files were
verified; [commands and data](../research/data/pressure-tube-audit-2026-11-07/README.md).

The old waiting controller was withdrawn before doing any work, with a
cancellation receipt. The active frozen Womersley calculation was not stopped.
The replacement controller is queued at source 2189a8c, with output directory
acceptance-2189a8c. It retains the same minimal time-scale checks and stage-load
check, then runs both coupled cases and these audits sequentially.

```sh
python scripts/audit_pressure_tube.py --case /path/case.json --work /path/eonsim \
  --output /new/eonsim-audit.json
# Requires the separate VTK analysis environment:
python scripts/audit_pressure_tube.py --case /path/case.json --work /path/reference \
  --svfsi --output /new/reference-audit.json
```

The script reports incomplete qualification even if file/geometry and periodic
checks pass. Cross-solver amplitude/phase, spatial/time/tail/sampling budgets,
finite-end effects, angular geometry, MPI and restart remain separate gates.

Subsequent comparison helpers have five known-signal/input checks and three
nested-field/dual-reader checks, all passed on manufactured data. They retain
the prescribed observable gates, refuse undefined zero-amplitude phase passes,
and verify actual red-refinement topology before taking exact P1 field norms.
[Commands and28 verified raw files](../research/data/pressure-tube-comparison-2026-11-08/README.md).
These do not establish actual elastic response agreement.

## First actual coupled outputs: binary32 coordinates

The first six-cycle runs completed at source2189a8c (the EONSim calculation
used frozen b072cc8). The initial reference audit failed before producing
physical metrics: `vtkXMLParser.f90:putVTK_pointCoords` at the pinned reference
version explicitly writes Float32 positions, while the physical arrays are
Float64. The earlier manufactured reader fixtures used Float64 positions and
therefore did not cover this real serialization contract.

The corrected auditor maps each actual Float32 position to the exact binary32
rounding of an input reference node. It rejects collisions, unmatched values
(including a one-ULP edit), missing nodes and changed tetrahedra. All physical
integrals use the original high-precision input geometry after this mapping;
physical field arrays are untouched. No distance or physical acceptance limit
was widened. Float64 inputs retain their previous mapping checks.

Six unit checks and the independent VTK Float32/Float64 fixtures passed. Both
preserved600-step histories were then read successfully with the corrected
analyzer. Interface/clamp, stage-mass, divergence-theorem and positive-geometry
checks passed in both programs. They are **not periodic**: last-cycle solid
velocity differences are about.0466 and.0465 on the prescribed scale. The
cross-solver mid-pressure amplitude/phase differences are4.9021%/2.6578degrees,
above their2%/1degree gates. Mean wall displacement differs from the circular
infinite-cylinder reference by8.3153%; finite-end and geometry effects still
need separate budgets. Six completed cycles are not elastic qualification.

Commands and immutable raw results will be captured under
`docs/research/data/pressure-tube-first-2026-11-08/`; current reanalysis is
`work/elastic-reaudit-float32-865b101`. The original failed audit and original
outputs remain intact. The minimum time-scale Debug/Release checks and explicit
reference stage-pressure check completed before these coupled calculations.

## Native restart convergence chains

For a continued pinned reference, use an explicit `svfsi-native-restart-chain-v1`
JSON manifest with `final_step`, `target_work` and ordered `segments`. Each
segment names its actual `work`, original `log`, `first_step` and `last_step`.
Paths resolve relative to the chain file; absolute recorded paths are also
accepted. A chain starts at1 without gaps or overlap. Do not concatenate logs
or rewrite a resumed input as `Continue previous simulation: 0`.

`python3 scripts/svfsi_restart_evidence.py --chain restart-chain.json --output convergence.json`
audits selected original and resumed intervals. Each resumed segment requires
an explicit local native seed, hashed export provenance and actual log evidence
of initialization. The seed must match the preceding segment's real checkpoint
byte for byte. Physics, mesh, source case, pressure tables, tolerances and output
grid remain identical; only stop/restart execution controls may differ. A changed
linear backend is still rejected by this identity check. Original failed tails
remain in the report as explicitly excluded rows, never as passed steps.

For final field qualification, supply `--reference-chain restart-chain.json`
instead of `--reference-log` to `audit_pressure_tube.py --svfsi`. It requires the
complete source study, not a successful late segment or shorter prefix. The
actual preceding endpoint must still initialize the stored field window, and
its hash is bound to the chain. All physical gates below remain unchanged.

The narrow native decoder supports the pinned linear-FSI little-endian i32/f64
layout at one or two ranks, with two equations, two meshes, no coupled0D state,
seven DoFs and displacement history. It checks finite complete Yn/An/Dn and
saved equation norms. Two-rank records use the maximum rank payload as fixed
RECL; local node counts can differ and smaller payloads have non-state padding.
Each rank's layout is bound to provenance, and step/time/norms agree exactly.
Elapsed times and padding are excluded only from numerical-state comparisons;
the full-file SHA continues to cover them. Saved native time is not replaced by
step*dt and is not described as EONSim's v4 compensated clock.

The [19 reference and8 pressure checks plus five actual record decodes](../research/data/native-two-rank-record-audit-2026-11-08/README.md)
verify this format and provenance behavior. Actual two-rank restored trajectories
require separate runtime evidence; arbitrary rank counts, re-partitioning and
other upstream layouts are unsupported. No unchanged C++ checks were rerun.

## Explicit late-cycle window

--first-step defaults to1. A later value must start a cycle and leave at least
three complete cycles. The actual preceding field is required: its geometry
and velocity initialize the alpha stage and endpoint volume budget. A restart
is not another zero-state startup or BE step. The report names the stored
window and makes no unstored warmup field claim. Duplicate/missing steps,
unaligned/short windows and field comparisons outside the window are rejected.

The reference output-start-step changes only saving; pinned MAIN.f uses
cTS>=saveATS, so include the preceding endpoint. EONSim keeps immutable
warmup/sample attempts and combines their actual indices. A64-step manufactured
static dilation gave identical window/full-history rows and harmonics, zero
window volume defect and a correctly failed clamp gate. Eleven window checks
and four exporter checks passed. [551 verified files](../research/data/pressure-tube-window-2026-11-08/README.md).
Actual long-tail results are pending; physical gates are unchanged.

The later132-cycle EONSim run passed the stored-window periodic/quality gates;
the reference continuation is still being computed. No full qualification is
inferred. A startup ramp now requires three full post-ramp cycles before the
periodic audit can run. Explicit same-solver startup comparisons may differ
only in ramp_time and may select only post-ramp cycles; the default comparison
still rejects that change. Both laws remain in the report. Six manufactured
checks passed, alongside seven auditor unit checks; see the
[General input evidence](../research/data/pressure-general-input-2026-11-08/README.md).

Reference convergence now has separate evidence: --reference-log reads every
equation/step with audit_svfsi_convergence.py and binds the result to the export
manifest. A reference report without that evidence is ineligible, even if its
fields look periodic. The pinned program can call an iteration cap ok. Printed
relative ratios must be strictly below the unchanged1e-10 input limit; rounded
equality is unproven. The absolute residual cannot be reconstructed from these
rounded normalized logs. [Actual and synthetic checks](../research/data/svfsi-convergence-2026-11-08/README.md).

The long reference passes its nonlinear checks but not the mesh-displacement
period gate (about1.95e-5). The ramp16/c32 reference has the same issue. EON
startup equivalence passes the predeclared1e-5 five-field maximum-phase gate
(max1.891e-6); reference equivalence fails with mesh difference.00217017.
Do not drop the ALE field or promote physical-only periodicity to full passage.
The completed N200/default-tau study reduces mid-pressure amplitude difference
to2.48284% (still above2%) and phase difference to.51230degrees (below1degree).
All reference equation steps pass relative convergence. Its mesh period maximum
remains1.93514e-5; EONSim passes the five-field periodic gate. N400 and same-polygon
spatial refinement are running; no full elastic acceptance.

Pinned svFSI's internal mesh equation is incremental pseudoelasticity on the
previous mesh, while EONSim uses fixed-reference vector Laplace extension.
This difference is documented from MESH.f/LELAS.f and fsi_element.cpp.
An independent replay now quantifies it on the coarse mesh: reconstructing the
incremental pseudoelastic operator on each previous configuration reproduces
the actual N100/N200 mesh fields with maximum normalized nodal differences
2.70e-15/4.79e-15, below the predeclared1e-8 check. The reference operator uses
the quadrature weight without the element Jacobian determinant; the replay
retains that element-volume normalization.

After removing only the boundary endpoint mismatch by a linear correction in
phase, a strictly closed boundary cycle still gives mesh RMS drift
1.94584e-5/1.93212e-5 for N100/N200. The same pseudoelastic extension on fixed
initial geometry returns within1.63e-16/2.49e-16. This isolates a path-dependent
incremental-mesh contribution for the observed boundary histories; it does
not modify accepted fields, rerun the coupled PDE or qualify a different
reference algorithm. The fixed-geometry counterfactual is pseudoelastic,
not EONSim's vector Laplace equation. Its spatially refined effect remains
pending. [Time and replay evidence](../research/data/pressure-tube-time-2026-11-08/README.md).

Cross-solver pulled-back fields
are not Eulerian samples at identical current positions. Physical observable
gates and each program's independent error budgets remain unchanged.

The separate [static Lamé diagnostic](../research/data/lame-static-2026-11-08/README.md)
uses symmetry and axial-only end supports. Its improved mean-wall agreement
cannot replace the actual clamped-end mean-response and finite-end budgets;
the nonmonotone volume-field errors are retained explicitly.

## Explicit finite-length inputs

`cases/fsi/generate_pressure_tube.py --length 24 --axial 24` generates a
length24 tube with the same seed axial spacing as default length12/axial12.
Length is finite and positive; default12 remains byte-identical. Increasing
length without increasing axial count also changes axial resolution, so it
cannot by itself isolate end effects. Radius, thickness, material, pressure
waveform and time-grid controls are unchanged by this option. Each length case
still needs its own periodic and field-quality checks before comparing means;
input generation alone is not finite-end qualification.
