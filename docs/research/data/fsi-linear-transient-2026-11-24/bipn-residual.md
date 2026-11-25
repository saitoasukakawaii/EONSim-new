# True linear residuals in the native BIPN tube comparison

The test uses the 20 mm diameter, 120 mm long straight elastic tube. A 1 s quintic traction ramp reaches 80 Pa at both ends in 32 accepted steps of the physical driver. The two meshes have 24 and 48 circumferential sectors. Their fluid and wall coordinates, pressure records, block method and solver controls are identical in each within-grid intervention. The external program is Fortran svFSI at 94a2ff5, using the discrete pressure observer and independent fluid/structure and mesh convergence checks documented in the [dimensional tube study](scaled-tubes.md).

The native FSILS BIPN projects on its accumulated pressure and momentum directions and evaluates a squared residual by subtracting two nearly equal numbers. At native termination the observer forms the returned correction, applies the full assembled, internally scaled momentum/continuity operator and its coupled-boundary contribution, then takes the distributed Euclidean norm of $b-Ax$. The target is $\max(10^{-23},10^{-10}\lVert b\rVert_2)$. Native success flags, component norms and independently evaluated full residuals are matched by physical step and Newton correction. Each observer-only run produced eight binary-identical VTU snapshots relative to its uninstrumented control. The experiment is single-rank. It tests the native linear stopping rule under these dimensional tolerances, separately from nonlinear FSI time-step acceptance.

| Sectors | Variant | Full residual within target / linear solves | Native positive flags above target | Largest full residual / target |
|---:|---|---:|---:|---:|
| 24 | Observe original stopping rule | 19 / 121 | 92 | 705.43 |
| 48 | Observe original stopping rule | 17 / 148 | 117 | 1,232.72 |
| 24 | Explicit residual for stopping | 105 / 120 | 0 | 1.3823 |
| 48 | Explicit residual for stopping | 110 / 129 | 0 | 1.3392 |
| 24 | Twice-reorthogonalized QR, explicit residual | 105 / 120 | 0 | 1.3847 |
| 48 | Twice-reorthogonalized QR, explicit residual | 112 / 129 | 0 | 1.2327 |
| 24 | Explicit residual, inner absolute floors ×0.1 | 120 / 120 | 0 | 0.9229 |
| 24 | QR, inner absolute floors ×0.1 | 120 / 120 | 0 | 0.9274 |
| 48 | Explicit residual, inner absolute floors ×0.1 | 129 / 129 | 0 | 0.9870 |
| 48 | QR, inner absolute floors ×0.1 | 129 / 129 | 0 | 0.9876 |

The unmodified projection produced 101 negative squared estimates on the coarse grid and 120 on the fine grid. Sixteen and nine reported norms, respectively, were nonfinite. For the coarse run, the very first correction had a true residual 84.84 times its requested bound while reporting success. Computing the true residual before stopping removes the false successes on both grids. Some correctly reported failures then remain close to the acceptance threshold. On the coarse QR run, 14 of the 15 failing corrections had both component norms below the inner solvers' shared absolute tolerance, including the rounding uncertainty of the printed percentages. Their combined 2-norm still exceeded the outer limit. Reducing only the two inner absolute floors from 1e−23 to 1e−24 recovered all 120 coarse corrections in both experimental methods. The same change recovered all 129 corrections on the 48-sector mesh for either method. All four tightened-inner-tolerance runs passed the separate fluid/structure and mesh histories through the final physical step. At 1 s the two corrected schemes gave 0.18680355% end-area increase on the 24-sector tube and 0.19495081% on the 48-sector tube. The ten measured trajectories contain 1,265 independently checked linear residuals. The outer tolerance, relative inner tolerances and iteration budgets stayed fixed.

The QR variant orthogonalizes the operator images of the original two block directions twice, projects the right hand side in that basis and recovers the correction. The same outer/inner budget handles each corrected case. This experiment tests whether loss of significance in the Gram projection and a shared inner stopping floor explain the observed behavior on this fixture. The outer monitor alone cannot assess continuum accuracy. The [area and volume comparisons](scaled-tubes.csv) use only accepted trajectories. [All corrections and executable/file hashes](bipn-residual.json.xz) · [Per-run counts and solver resources](bipn-residual.csv)

## Reproduction

Build the original source and each variant in separate directories with the [native compilation script](../fsi-pressure-faces-2026-11-24/build-svfsi.sh). Apply the same pressure observer and current-equation history patches to all builds. Apply exactly one of the three BIPN patches in a variant. For the two inner-floor experiments also apply the option-reader patch. Rebuild the solver with the same compile script, run `scaled_svfsi.py --problem arterial --linear-solver bipn --krylov 85 --outer-iterations 100 --steps 32` with each case and executable path. Capture stdout, historian, split-solver file and process receipt for each grid. [Observer](svfsi-bipn-residual-observer.patch) · [Explicit residual](svfsi-bipn-residual-explicit.patch) · [Reorthogonalized QR](svfsi-bipn-residual-qr.patch) · [Inner floors](svfsi-bipn-inner-floor.patch) · [Receipt reader](compare_bipn_residual.py)

```bash
python compare_bipn_residual.py --archive bipn-residual.json.xz --csv "$work/bipn-residual.csv"
```
