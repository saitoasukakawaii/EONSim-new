# Exact affine Tet4 moments in the ALE residual

On a linear tetrahedron, the current velocity gradient and pressure gradient are constant. With frozen cellwise stabilization, the relative transport velocity and strong momentum are affine. Every remaining spatial integrand in the Galerkin, SUPG and PSPG terms has degree at most two. Define $m_a=\rho(u_a-u_{a,\mathrm{old}})/\Delta t+\rho (u_a-w_a)\cdot\nabla u$. Then $\int_K N_b m\,dx=|K|(\sum_a m_a+m_b)/20$. The constant pressure gradient adds $|K|\nabla p/4$ to each weighted strong residual. Multiplication by the nodal transport values gives the integrated SUPG tensor. The time increment is subtracted at each node before multiplication by its reciprocal time step. Volume and shape gradients are differentiated with the ALE geometry.

The independent fixed-grid tangent retains symmetric four-point quadrature. A 64-point Duffy integration checks every residual row on a skew tetrahedron with 16 combinations of transient inertia, convection, stabilization and grad-div. Central differences check the fluid tangent and both blocks of the complete ALE tangent. All four Release variants passed the fluid-element, FSI-element and elastic-FSI tests through the repository build script.

| Implementation | Interior CPU time per tangent (µs) | Pressure-face CPU time (µs) | Paired CPU change, interior / face |
|---|---:|---:|---:|
| Four quadrature points, original dual type | 13.503 | 13.587 | reference |
| Exact moments, original dual type | 10.639 | 10.054 | −24.5% / −26.6% |
| Four quadrature points, scalar overload prototype | 33.852 | 35.310 | +150.8% / +158.5% |
| Exact moments, scalar overload prototype | 17.526 | 18.477 | +31.9% / +33.8% |

The timed routine computes the full 28-by-28 element tangent and consumes changing Jacobian entries. Each executable used 2,000 warmup tangents per geometry, then eight balanced rounds of 40,000 evaluations per geometry. Percentages are medians of the paired process-CPU changes. For the adopted moments the eight interior changes ranged from −34.9% to −8.6%, and the pressure-face changes from −35.6% to +7.9%. The rejected overloads passed the numerical tests but copied and scaled the full derivative vector by value. The production code keeps its original dual type. Only the shared-host microbenchmark supports the percentages in this table. [Timing rounds, checksums and binaries](element-cpu.json) · [Rejected prototype](rejected-scalar-overloads.patch)

Build each of the four variants with `bash scripts/cloud/run.sh 3.23.7 release explicit "$state" "$selection"`, selecting `fluid_element_jacobian`, `fsi_element_jacobian` and `elastic_fsi_verification`. Keep the same verification driver in the quadrature variants and restore the previous `include/eonsim/fluid_residual.hpp`. Apply the archived overload patch only to the two scalar variants. Name the four verification executables as expected by the command below.

```bash
python compare_kernel.py --builds "$variants" --libs "$prefix/lib" \
  --rounds 8 --samples 40000 --output element-cpu.json
```
