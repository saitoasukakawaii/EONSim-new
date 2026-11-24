# Four labels for one physical tetrahedron

On the pressure-loaded test tube the local numbering of a Tet4 changes the standard right-simplex metric used by svFSI. This experiment preserves every physical point, oriented port triangle, parent tetrahedron, signed volume, applied pressure and solver input. Only the even permutation used to designate the dependent local fluid vertex changes. There are four choices for that vertex. The comparison uses all four at 128 time steps. The wall mesh is byte-identical. Both solvers' nodal outputs and seven polygon-area derivatives were reread on the reference geometry at 0.5 and 1 s. The observer also verifies the native VTK facet IDs, connectivity and outward orientation up to a cyclic rotation. [Geometry and field audit](../fsi-smooth-load-2026-11-24/audit_vertex_order.py)

For affine Tet4 shape functions $N_a$ in the current configuration, define

$$
G_* = 4^{-1/3}\sum_{a=1}^{4} \nabla N_a\,\nabla N_a^T.
$$

The four gradients sum to zero. On the right unit tetrahedron their outer products sum to $I+\mathbf{1}\mathbf{1}^T$, with determinant 4. The prefactor preserves the determinant of the standard metric under an affine map. Relabelling the four vertices permutes the terms in the sum and leaves the tensor unchanged. Stretching or shearing the cell still changes its coefficients. The EONSim option evaluates the exact cell-average quadratic in the ALE relative velocity and differentiates all metric and velocity terms in the assembled Newton tangent. The native research variant substitutes the same tensor at its existing quadrature points. [EONSim input and kernel](../../../../include/eonsim/fluid_residual.hpp) · [Patch against the pinned native equation](../fsi-smooth-load-2026-11-24/svfsi-regular-tet-metric.patch)

| Dependent vertex | Largest change in native 1 s section strain, % of static Lamé strain | Largest native nodal pressure change, Pa | Native volume RMS pressure change, Pa | Largest section change with regular metric, % of static strain |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0.03980 | 0.002569 | 0.0001581 | 2.49 × 10⁻¹⁰ |
| 1 | 0.03905 | 0.001937 | 0.0001437 | 4.89 × 10⁻¹¹ |
| 2 | 0.08849 | 0.001431 | 0.0001965 | 2.14 × 10⁻¹⁰ |
| 3 (original) | 0 | 0 | 0 | 0 |

The largest pointwise pressure change for vertex 0 is 12.84% of the 0.02 Pa driving pressure. Its volume RMS is 0.79% of the same pressure. Local numbering alone changes the native area response by at most 0.08849% of static strain on these seven sections at 1 s. The original intercode area difference there was 4.0975% of static strain.

## Same coefficient in two nonlinear codes and one independent DAE

| 48/4/4/6 grid, 128 steps, 0.02 Pa | Left-end area increase at 1 s, % of initial area |
| --- | ---: |
| EONSim default volume coefficient | 0.073399263 |
| svFSI standard reference metric | 0.064489137 |
| EONSim optional `regular_tet` | 0.064617700 |
| svFSI regular-metric research variant | 0.064614873 |
| Independently assembled regular-metric 3D linear DAE | 0.064613651 |
| Independently refined circular meridian | ≈0.07883 |

With the same regular metric the nonlinear left-end values differ by 0.000002827 percentage points of initial area. Their maximum across all seven stations at 1 s is 0.001300% of the static strain. Each of the four local vertex choices gives these values to the digits shown. The DAE has no moving geometry or nonlinear convection. At 0.02 Pa its maximum seven-station error against nonlinear EONSim is 0.016585% of static strain at 1 s. At 0.0002 Pa the corresponding error is 0.001090%. With that amplitude and the stabilization time held fixed at 1/128 s, using 64 and 512 time-integration steps gives errors of 0.004904% and 0.000100% of static strain. The native metric control isolates a discrete operator effect on this mesh. The distance to the circular meridian remains visible in the last row. [Per-station and curve receipts](tet-order.json.xz) · [Nonlinear EONSim and DAE](tet-order-eonsim.csv) · [Native and DAE](tet-order-svfsi.csv) · [Radius, Lamé normalization and equations](discrete-metric.md)

At 1,024 steps, native right-simplex results became more sensitive to the vertex choice. Choosing vertex 0 gave 0.0552703% left-end expansion, vertex 2 gave 0.0525620%, and the original vertex 3 gave 0.0548186%. The independently assembled DAE gave 0.0552778%, 0.0525714% and 0.0548269% in the same order. With the label-invariant metric the two nonlinear codes gave 0.0531849% and 0.0531814%, and the DAE gave 0.0531904%. The two EONSim regular-metric runs with vertices 0 and 3 agreed in the last displayed digit. Stabilization parameters must accompany a reported time-step refinement. [Native measurements](tet-order-svfsi.csv) · [Regular metric cross-checks](tet-order-eonsim.csv)

## Reproduction

Use the referenced [EONSim compile script](../../../../scripts/cloud/run.sh) and [native build script](../fsi-pressure-faces-2026-11-24/build-svfsi.sh). For each external run apply the residual-side pressure observer and the current-equation convergence patch. The regular-metric native build also uses the metric patch above. Generate each physical input with `space_study.py --mesh 48 4 4 6 --fluid-last-vertex V --steps 128 --pressure .02` and the two program and library paths. Run `svfsi_linear.py --metric-basis regular-simplex --modes native` on the matching Gmsh and native VTK tetrahedra. The nonlinear EONSim runner requires the same reference input hashes, checks every stage/end pressure, and reconstructs end flux from the saved velocity. [Nonlinear runner](metric_eon.py)

```bash
python compare_tet_order.py --archive tet-order.json.xz \
  --sv-csv /tmp/tet-svfsi.csv --eon-csv /tmp/tet-eonsim.csv
```
