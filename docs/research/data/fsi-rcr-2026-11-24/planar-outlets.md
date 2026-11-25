# RCR terminal on an expanding planar section

A straight elastic tube can have an axial roller at its outlet and still expand circumferentially. Set `moving_plane_axis` on that RCR to the fixed Cartesian normal component (0, 1 or 2). Supply matching mesh and wall end constraints. Every triangle of this tag must lie on the same plane, have a consistent outward orientation and have constrained normal mesh displacement. The two tangential directions may move. The input may list positive- and negative-facing ports and mix this option with stationary RCR outlets.

```yaml
fsi:
  domains:
    rcr_outlet:
      tag: 2
      proximal_resistance: 3
      distal_resistance: 8
      compliance: 0.025
      distal_pressure: 0
      moving_plane_axis: 0
    mesh_constraints:
      - {tag: 1, components: [0, 1, 2]}
      - {tag: 2, components: [0]}
    solid_constraints:
      - {tag: 11, components: [0, 1, 2]}
      - {tag: 12, components: [0]}
```

The excerpt uses the axial tube tags. Other domain, time, inflow and material settings come from the case. The default RCR accepts fixed exterior faces of arbitrary orientation. The moving-plane option requires a coordinate-aligned plane with zero normal mesh speed. The outlet relative-flow definition then reduces to the integral of the physical normal fluid velocity on the current area.

## Coupled residual and endpoint recovery

Let $\boldsymbol a=\tfrac12(\boldsymbol x_1-\boldsymbol x_0)\times(\boldsymbol x_2-\boldsymbol x_0)$ be the outward area vector and $w=a_k/3$ for normal axis $k$. The triangle contributes $Q=w\sum_i u_{ik}$ to the circuit and $w p_b$ to each free normal momentum row. Displacement changes $w$ through the two current tangential edges. The Newton matrix includes both $p_b\,\partial w/\partial d$ in momentum and $-(\sum_i u_{ik})\,\partial w/\partial d$ in the port row. Interface geometry columns use the same stage displacement-to-wall-velocity derivative as the volume elements. Each rank assembles its owned triangles into the shared pressure border.

The generalized-alpha residual uses the current stage flux and capacitor stage pressure. At the accepted endpoint the boundary pressure is $p_c^{n+1}+R_p Q(\boldsymbol u^{n+1},\boldsymbol d^{n+1})$. Since this flux is nonlinear in the unknown geometry and velocity, extrapolating stage boundary pressure alone would change the endpoint circuit relation. The solver reconstructs and checkpoints the physical endpoint even when all history output is disabled.

## Solver checks

The short nonlinear test uses a conforming 8-sector, 2-radial, 3-axial full circular tube, signed inflow, a pressurized capacitor, a supported neo-Hookean wall and variable step sizes. Each row recomputes the signed outlet flux from the final VTU velocities and displaced Tri3 coordinates. The reference-area column uses the same velocities on the original triangles. MPI differences compare every reported fluid and wall node field on one and two ranks.

| Integrator | Final absolute area change (%) | Flux error with original area (m³/s) | Current-area flux discrepancy (m³/s) | Largest MPI field difference |
|---|---:|---:|---:|---:|
| Backward Euler | 0.12713 | 9.28e−7 | 1.09e−19 | 8.22e−15 |
| Variable-step BDF2 | 0.17683 | 1.24e−6 | 2.17e−19 | 5.77e−15 |
| Generalized-alpha | 0.18449 | 1.45e−6 | 1.09e−19 | 1.65e−12 |

All three no-output checkpoints reproduced endpoint fields and subsequent pressure histories to the precision written. Changing the Cartesian port normal to negative y or positive z and rigidly transforming the model changed the recovered fields by at most 3.06e−12. The assembled Newton tangent's maximum relative Frobenius difference against PETSc finite differences was 1.99e−8. A centered perturbation of each signed face-area derivative, on all three axes and both orientations, differed by at most 2.91e−11. Three rejected attempts at a 0.1 s candidate step reduced it to 0.0125 s. Replaying that accepted step from the same initial state reproduced all node fields and circuit pressure exactly.

In a separate T-junction the positive-y daughter was allowed to expand while the negative-y daughter was fully clamped. Their final areas changed by 0.02455% and zero. Releasing the negative-y daughter gave changes of 0.02454% and 0.01260%. The largest measured flux or circuit defect was 5.43e−17 in the corresponding SI quantity. A second control clamped the moving-plane tube completely and recovered the stationary-port solution within 1.37e−12. [Measured values](planar-outlets.json) · [Reproduction runner](../../../../tests/verify_fsi_moving_port.py)

The repository Release driver builds the implementation. From the repository root, use a PETSc 3.23.7 prefix from the cloud lock and an explicit test list containing `fsi_moving_plane_rcr` and `fsi_element_jacobian`. [Build and validation](../../../development/BUILD_AND_VALIDATION.md)

[Through-flow, phase and cross-code comparison for the dimensional elastic tube](../fsi-linear-transient-2026-11-24/perfusion.md)
