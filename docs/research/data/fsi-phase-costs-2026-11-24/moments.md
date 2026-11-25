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

### Cost of differentiating the current regular-tetrahedron metric

The optional `regular_tet` model differentiates the deformed shape gradients, the cell-average ALE velocity quadratic, and both stabilization coefficients in the fluid tangent. The following timings also include the tangent terms shared by both models. Each of the twelve rounds used 40,000 calls per geometry. All six binary/run-mode orders appeared twice, with one thread and an unmeasured warmup. The pressure case includes its follower-load derivative. The checksum of the default full tangent agreed across the two Release binaries.

| CPU time per tangent | Interior Tet4 | Pressure facet |
| --- | ---: | ---: |
| Previous executable, volume model | 10.555 µs | 11.049 µs |
| New executable, volume model | 10.035 µs | 10.683 µs |
| New executable, regular metric | 12.775 µs | 13.343 µs |
| Regular / volume, median of paired CPU ratios in new executable | 1.250 | 1.253 |
| Regular / volume, range of paired ratios | 1.056–1.514 | 1.140–1.410 |

The optional metric cost about 25% more per full tangent on this fixture. The paired ratios for the new and old *default* spanned 0.775–1.156 and 0.864–1.116, respectively. Differences in iteration count, MPI communication, and preconditioner setup require separate end-to-end measurements. [Raw round measurements](metric-cpu.json) · [Benchmark runner](profile_metric.py)

Build both element regression executables with the repository compile script using the `fsi_element_jacobian` selection. Run `python profile_metric.py --before OLD_ELEMENT_EXE --after NEW_ELEMENT_EXE --libs PETSC_LIB --output metric-cpu.json` to compare their defaults and the new optional metric.

## Whole solver with bound MPI ranks

The 3,024-unknown elastic tube used the same partition, matrices, boundary load, PETSc settings and two accepted time steps in each before/after pair. For each rank count and preconditioner, five uninstrumented pairs measured end-to-end process wall time. Five additional pairs recorded the maximum-rank time inside each PETSc event. Baseline/candidate order alternated. Each actual solver launch reported its Open MPI binding. Ranks used distinct cores on package 0, starting at core 3. The host was shared with numerical validation jobs.

| MPI ranks | Preconditioner | Fluid/ALE tangent, paired median change | Whole run, paired median change | Range of five whole-run changes |
|---:|---|---:|---:|---:|
| 1 | Direct | −36.4% | +5.9% | −29.7% to +26.2% |
| 1 | Schur | −39.0% | −26.3% | −33.3% to +4.1% |
| 2 | Direct | −23.7% | +2.4% | +0.3% to +13.9% |
| 2 | Schur | −37.9% | −10.9% | −30.9% to +24.2% |
| 4 | Direct | −28.2% | −0.1% | −18.9% to +42.8% |
| 4 | Schur | −29.7% | −1.7% | −11.5% to +35.1% |

Across all 60 pairs (120 timed launches), the maximum field differences were 3.47e−18 for the saved fluid-domain fields and 2.17e−18 for the solid-domain fields. Both versions used the same Krylov and Newton iteration counts in every pair. Direct solves took four linear iterations in total. The Schur solves took 488, 483 and 449 on one, two and four ranks. The largest final reported nonlinear residual was 9.79e−14 or smaller. The machine and problem size support a local kernel comparison. Whole-run effects depend on partition, preconditioner and competing work. An earlier launcher overwrote its inherited rank mapping; its unverified timings are excluded. [Paired times, fields, bindings, reported convergence and binary hashes](moment-pair-results.json.xz) · [Full phase medians and ranges](moment-phase-medians.csv)

Build the pre-moment and exact-moment revisions with the repository Release build script. Use the same 48-sector fixture as the [sparse-insertion experiment](README.md). For each pair use `profile_case.py --ranks 1 2 4 --pcs direct schur --repeats 1 --verify-core-placement` with each executable in a separate directory. Run `compare.py --work "$work" --pairs 5 --element-moments --output "$work/audit"` on the resulting directories. The comparison reopens both domains' VTUs and each measured launch log.
