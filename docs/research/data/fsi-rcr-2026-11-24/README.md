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
