# A continuum reference for filling an elastic tube from both ends

At rest the tube has lumen radius 1 m, outer radius 1.2 m and length 2 m. Fluid and wall densities are 1 kg/m³, dynamic viscosity is 1 Pa s, and wall Young's modulus and Poisson ratio are 100 Pa and 0.3. A quintic ramp raises the normal traction pressure on both lumen ends from zero to 0.02 Pa in one second. The wall ends have axial rollers, the outside is traction-free, and fluid and wall velocity are continuous at the bore. This artificially soft, viscous benchmark isolates the early filling transient produced by wall expansion.

## Independent equations and checks

The reference linearizes at rest on the undeformed circular cylinder. Its meridian mesh is independent of both 3D tetrahedral meshes. The mixed weak form uses quadratic axial and radial velocity in both subdomains, bilinear fluid pressure, and quadratic wall displacement. Fluid inertia, symmetric viscous stress, pressure/divergence, wall inertia, isotropic small-strain elasticity, and displacement-rate compatibility are retained. The cylindrical integral has weight $r$ per radian, circumferential strain $u_r/r$, and dilatation $∂ₓuₓ + ∂ᵣuᵣ + uᵣ/r$. The reference imposes zero radial velocity on the rotation axis and integrates pressure traction over the cap. Shared velocity gives no slip, and assembled momentum balances interface tractions. There is no pressure penalty. The singular mass-matrix system is integrated using the two-stage, third-order Radau IIA method in [reference.py](reference.py).

The primary run uses symmetry at the midplane; separate full-length runs with both loaded ends reproduce that symmetry without prescribing it. The 64-by-64-by-16 meridian base mesh has four local bisections towards the loaded end and the fluid-wall junction and 64,056 independent unknowns. Its static inner strain agrees with the analytic plane-strain Lamé solution to 5.22 × 10⁻¹⁰ relative. At 256 steps the largest relative power and fluid-volume balance residuals evaluated at all internal stages are 2.05 × 10⁻¹¹ and 4.70 × 10⁻¹¹. Across seven stations at 0.5 and 1 s, the change from the previous spatial grid is 0.00369% of the static area expansion. The change from 128 to 256 Radau steps is 0.00000416% on that scale. These are measured refinements, not rigorous error bounds. [Grid, quadrature and symmetry runs](axisym-refinement.json) · [finest grid](reference-axisym.json) · [previous grid](previous-axisym.json)

## What the cross-code gap measures

At 1 s the reference left-end area increase is 0.0788759% of the initial area; the midplane increase is 0.1071810%. At the same pressure and time the 48-sector 3D grid gives 0.0733993% (EONSim) and 0.0644891% (standard svFSI) at the left end. The right end of each 3D mesh samples a different tetrahedral orientation. Reflecting the entire mesh interchanges the ends in both solvers. The continuum reference is symmetric.

The following errors are maxima over the same seven axial sections at 1 s, expressed as percentages of the static Lamé area strain for the given pressure. The 3D models retain finite amplitude. Reducing the peak pressure from 0.02 to 0.0002 Pa tests proximity to the small-amplitude limit. The table uses the unmodified stabilization of both codes.

| 3D mesh (sectors / fluid radial / wall radial / axial) | Peak pressure (Pa) | Steps | EONSim error | svFSI error |
|---|---:|---:|---:|---:|
| 48 / 4 / 4 / 6 | 0.02 | 128 | 6.427% | 9.737% |
| 48 / 4 / 4 / 6 | 0.0002 | 128 | 6.439% | 9.746% |
| 96 / 8 / 8 / 12 | 0.02 | 128 | 2.842% | 4.625% |
| 96 / 8 / 8 / 12 | 0.0002 | 64 | 2.738% | 4.635% |

Switching off only svFSI's momentum grad-div term on the first mesh reduces its maximum error against the reference to 6.680%, while the maximum *intercode* gap falls from 4.097% to 0.497% of the static strain. A close match between the two tetrahedral solutions can therefore coexist with a larger shared spatial error. The actual normalized errors by station include their signs. [Comparison](axisym-comparison.json) · [paired 3D reports and solver hashes](axisym-3d-reports.tar.xz) · [mesh reflection](../fsi-smooth-load-2026-11-24/reflection.json)

## Reproduction

Run in this directory with Python, NumPy, and SciPy. The lengths in the command refer to element counts on the ungraded half tube. To repeat the symmetry check add `--full-length` to the 24/24/8, three-level case. For the uniform-grid controls set `--corner-levels 0`. The corresponding 3D decks, solver versions and build procedure are in the [matched-load study](../fsi-smooth-load-2026-11-24/README.md).

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python axisymmetric.py --mesh 48 48 16 --corner-levels 4 --steps 64 128 256 --output previous.json
python axisymmetric.py --mesh 64 64 16 --corner-levels 4 --steps 64 128 256 --output finest.json
mkdir -p reports
tar -xf axisym-3d-reports.tar.xz -C reports
python compare_axisymmetric.py --reference finest.json --previous-mesh previous.json \
  --native reports/native/*.json --ablated reports/no-grad-div/*.json --output comparison.json
```
