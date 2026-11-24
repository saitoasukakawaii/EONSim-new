# Three-element Windkessel coupled to a stationary FSI outlet

A fixed fluid boundary tag uses outward volume flux Q in m³/s, reservoir pressure p_d in Pa, positive proximal and distal resistances R_p and R_d in Pa s/m³, and compliance C in m³/Pa. The terminal traction on the fluid is −p_b n. For the capacitor pressure p_c, the circuit obeys

$$
p_b=p_c+R_p Q,\qquad C\dot p_c=Q-(p_c-p_d)/R_d.
$$

An example for an existing case with fluid outlet tag 2 is below. The optional initial capacitor pressure defaults to the distal pressure. Compatible prescribed-pressure tags can be included alongside the circuit tag. A moving outlet with free mesh displacement is rejected. The model permits reverse flow.

```yaml
fsi:
  domains:
    pressure_tags: [2]
    rcr_outlet:
      tag: 2
      proximal_resistance: 3.0
      distal_resistance: 8.0
      compliance: 0.025
      distal_pressure: 0.03
```

## Discrete pressure and flux

Let δ be the effective derivative step and p_ref the reference pressure for the integrator. At its residual evaluation stage let w = δ/(R_d C + δ), B = (1 − w)p_ref + w p_d, and Z = R_p + w R_d. The coupled equations use a single global pressure unknown, fluid force b p_b and an extra row (p_b − B)/Z − bᵀu. The entries of b are the integrals of the velocity trace against the outward normal on locally owned triangles. The extra row and column need storage proportional to the number of outlet velocity DoFs. Eliminating the pressure produces the positive impedance contribution Z b bᵀ. The natural circuit row has the same flux units as the fluid continuity rows. Flow signs and pressure power are verified against independently integrated faces.

The implementation uses BE, variable-step BDF2 and first-order generalized-α at the fluid residual stage. It computes the capacitor rate directly from the circuit to preserve accuracy on short steps at large absolute pressure. Accepted capacitor pressure, previous pressure and rate accompany the existing field checkpoint. In calculations with a sole circuit pressure tag, the main history and console report its actual applied stage pressure. Per-tag stage and endpoint traction pressure, flux and power are available under `fsi.pressure_face_history`.

## Actual acceptance

A fully clamped single-slab tube gives Q_out = Q_in from discrete continuity, allowing an exact terminal pressure while retaining the coupled 3D pressure/velocity assembly. The constant-flow step follows the discrete BE capacitor recurrence at every accepted step. Starting a sinusoidal flow at its periodic pressure permits a one-cycle impedance comparison with Z(ω) = R_p + R_d/(1 + iωR_dC). The case has R_p = 3, R_d = 8, C = 0.025, p_d = 0.03 and period 1 s. At 128 steps the signed modulus and phase errors are as follows.

| Time integrator | Impedance modulus error | Phase error |
|---|---:|---:|
| BE | −0.543% | +0.542° |
| BDF2 | −0.0334% | +0.00374° |
| Generalized-α | −0.00817% | +0.00560° |

A second tube has a genuinely deforming wall, backflow, positive stored pressure and variable step sizes. Its three schemes agree between one and two MPI ranks to at most 1.10 × 10⁻¹⁴ over the nodal fields. Same-partition resumed fields and pressure histories reproduce the continuous trajectories. The four-rank complete Jacobian check has relative discrepancy 8.78 × 10⁻⁹; the hybrid preconditioner agrees with the direct field solution within 4.16 × 10⁻¹². A strong inlet and restricted Newton iteration budget produce 13 BDF2 and 14 generalized-α rejections. Replaying the actual accepted step sizes reproduces both the final fields and circuit pressures. A separate run has one prescribed end and one circuit end. [Recorded results, including all three refinements](single-port.json)

Compilation and verification used the repo script with PETSc 3.23.7 Release. The targeted selection for the new numerical checks is `{"tests":["fsi_tube","time_integration"]}`. Run `bash scripts/cloud/run.sh 3.23.7 release explicit "$cache" "$selection"`. [Analytic, coupled, MPI and retry checks](../../../../tests/verify_fsi_tube.py) · [short-step large-pressure test](../../../../tests/verify_time_integration.cpp) · [upstream development contract](../../HPC_UPSTREAM_REVIEW_2026-11-24.md)

## Several stationary outlet circuits

The list form `fsi.domains.rcr_outlets` accepts an independent circuit per stationary pressure tag. Each entry uses the keys shown above. The parser sorts tags before numbering global port pressures or serializing capacitor states. It rejects duplicate tags and simultaneous use of the singular and plural input forms. A single-entry list can resume a checkpoint written by the earlier single-port implementation. The direct cross-version replay reproduced the prior two-rank fields and all circuit observables exactly.

For multiple circuits the main history appends the tag to each circuit column, e.g. `stage_rcr_flow_2`, `endpoint_capacitor_pressure_3`. The independent pressure-face table still has a row per tag. Both accepted stage and endpoint fluxes for all ports are reduced together in one diagnostic collective. Newton assembly uses distributed PETSc insertions of the sparse port border.

The [T-junction generator](../../../../cases/fsi/generate_branched.py) provides a square duct with a flexible 3D wall, a prescribed flow inlet and two distal circuits. At refinement one it has 312 fluid and 840 solid tetrahedra. The mesh is exactly symmetric about the daughter midplane. Identical circuits give equal branch fluxes even during filling. Exchanging unequal terminal impedances exchanges all measured pressure and flow trajectories and reflects the full solution, including the sign of the transverse velocity and displacement. The check matches all nodal fields by reference coordinates. Circuit power is positive into a passive terminal load for positive outward flow and pressure, and each pressure-face record stores the opposite applied fluid power.

Across a separate four-step test on 1, 2, 4 and **8 MPI ranks on one host**, the maximum nodal discrepancy was 1.78 × 10⁻¹⁵. On two ranks, BDF2 needed two rejected candidates and generalized-α one candidate before accepting their third step with a restricted Newton budget. Both reproduced the explicitly replayed trajectories, including each capacitor pressure. The complete two-port Jacobian gave a relative finite-difference discrepancy of 4.30 × 10⁻⁸. These experiments verify coupling, signs, rollback and MPI ownership for this synthetic geometry. [Measured fields and circuit checks](multi-port.json) · [manual MPI and retry driver](extended.py)

```bash
python cases/fsi/generate_branched.py --output "$work/case" --refinement 1
"$eonsim" -case "$work/case/case.json" -prepare "$work/part" -parts 4
"$prefix/bin/mpiexec" -n 4 "$eonsim" -case "$work/case/case.json" -partition "$work/part"
python docs/research/data/fsi-rcr-2026-11-24/extended.py --work "$work/extended" \
  --executable "$eonsim" --mpiexec "$prefix/bin/mpiexec" --ranks 2 4 8
```

## Independent RCR calculation in native svFSI

A fixed tube isolates the three-element outlet from wall storage. Both programs solve 3D flow on the same Tet4 connectivity. Prescribe zero-mean sinusoidal inflow of amplitude 0.01 m³/s and period 1 s, initialize the capacitor at its periodic pressure and run one cycle with generalized-α spectral radius 0.5. The fluid face is stationary. Values below are in Pa and use each accepted endpoint. The pinned Fortran svFSI revision is `94a2ff5`, with its original RCR update. EONSim is the multiple-port implementation from [the tagged multiple-port commit](https://github.com/saitoasukakawaii/EONSim-new/commit/5ac87ebab12553c1faadd3dc89093470df1703b2) in single-port mode.

| Steps per period | Max EONSim–svFSI pressure difference | Max EONSim–analytic error | Max svFSI–analytic error |
|---:|---:|---:|---:|
| 16 | 1.787e−3 | 1.733e−3 | 7.134e−4 |
| 32 | 5.798e−4 | 5.762e−4 | 1.782e−4 |
| 64 | 1.650e−4 | 1.647e−4 | 4.452e−5 |
| 128 | 4.492e−5 | 4.486e−5 | 1.114e−5 |
| 256 | 1.186e−5 | 1.186e−5 | 2.819e−6 |
| 512 | 3.047e−6 | 3.046e−6 | 7.388e−7 |

The two circuit schemes differ in time. EONSim evaluates the circuit with the generalized-α fluid stage. In `SETBC.f` svFSI advances the circuit with 100 explicit fourth-order substeps and linearly interpolates the step-end flows. Integrating that linear interpolant exactly matches the printed native capacitor pressure within 5.70e−9 Pa over all six runs. The 512-step harmonic pressure lags calculated by the two schemes differ from the exact impedance phase by +0.000368° and +0.0000704°, respectively.

Native boundary tables truncate at a sign-dependent precision. Checking them against one absolute threshold initially rejected valid output. Independently integrating the double-precision velocity from all 1,008 native VTUs against both cap surfaces agrees with EONSim flux to 4.83e−15 m³/s; the native text values are also checked at their actual printed resolution. Each deck, executable and mesh hash accompanies the measurements. [Results](svfsi-single-port.json) · [All paired samples](svfsi-single-port.csv.xz) · [Source and checks](compare_svfsi.py)

```bash
python docs/research/data/fsi-rcr-2026-11-24/compare_svfsi.py \
  --work "$work/independent-rcr" --eon "$eonsim" --mpiexec "$prefix/bin/mpiexec" \
  --svfsi "$svbuild/bin/svFSI" --svfsi-libs "$svprefix/lib" --steps 16 32 64 128 256 512
```

## Constraints on the shared material interface

A homogeneous component constraint on the solid's interface tag fixes that component of the structure, the shared no-slip velocity and the shared mesh motion. Selecting only one component leaves the other components free. A fluid or mesh constraint conflicts with a free solid master on the same component and is rejected at setup. Constraints on the two original interface tags are resolved through the joined mesh's fluid/solid region incidence. Pressure and circuit face integrals still require exterior faces.

The two-outlet T-junction exercised a transverse slide, its two-rank checkpoint, a changed-component restart, a conflicting master, and a fully clamped lumen on one and two ranks. The free displacement reached 7.712e−5 m in the sliding case. The resumed final fields matched exactly. For the clamped control, the volume change was zero, the largest inlet–outlet flux imbalance was 2.17e−19 m³/s, and the largest replicated node-field difference was 1.89e−15 in native units. The executable check runs in `fsi_branched_rcr`. [Measured bound for each control](interface-constraints.json)

The symmetric T-junction now has independent checks on daughter pressure and flow. A separate Stokes experiment predicts the steady high-resistance share on three meshes, while two-cycle EONSim–svFSI runs and long deformable-wall simulations distinguish small outlet signals from actual volume storage. [Flow split, wall storage and matched waveforms](branched.md)

A separate RCR option permits tangential mesh and wall motion on a fixed coordinate plane. The circuit uses the current outlet area, and the monolithic tangent includes its displacement derivative. It supports stationary and expanding outlets in the same computation. [Inputs, equations and moving-port checks](planar-outlets.md)

[Independent downstream pressure waveforms, two-frequency transfer and restart](reservoir-pressure.md)
