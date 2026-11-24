# Dimensional similarity and a 20 mm elastic tube

Both ends of each initially quiescent cylinder receive the same quintic pressure ramp. Axial displacement is fixed on the two annular ends, the bore expands freely there, and the exterior carries zero traction. The resulting flow fills the expanding tube from both ends. The reported end area is the displaced inner polygon from the actual solid field.

| Parameter | Original transient | Exactly similar tube | Arterial-scale tube |
|---|---:|---:|---:|
| Inner / outer radius (m) | 1 / 1.2 | 0.010 / 0.012 | 0.010 / 0.012 |
| Length (m) | 2 | 0.020 | 0.120 |
| Fluid / wall density (kg/m³) | 1 / 1 | 1060 / 1060 | 1060 / 1100 |
| Viscosity (Pa s) | 1 | 20.5913 | 0.004 |
| Young modulus (Pa) / Poisson ratio | 100 / 0.30 | 400,000 / 0.30 | 400,000 / 0.45 |
| Peak pressure (Pa) / ramp duration (s) | 0.02 / 1 | 80 / 0.00514782 | 80 / 1 |
| $\rho_f R_i^2/(\mu T)$ | 1 | 1 | 26.5 |
| $(L/T)\sqrt{\rho_s/E}$ | 0.2 | 0.2 | 0.00629 |

All three have the same ratio of peak pressure to Young modulus, 0.0002. The third has a different slenderness, density ratio, wall compressibility and ramp time relative to elastic and viscous time scales. The second deliberately has a high viscosity to preserve the original dimensionless equations.

## Exact similarity in two independent executables

For length, pressure and time scale factors $\ell$, $s$ and $t$, displacement scales by $\ell$, velocity by $\ell/t$, pressure and Young modulus by $s$, density by $st^2/\ell^2$, viscosity by $st$ and cap flux by $\ell^3/t$. The comparison verifies these transformations, initial coordinates, connectivity and boundary tags. It recovers the fluid and wall VTU fields at eight ramp phases. The error for each field is its largest pointwise absolute difference divided by its own peak over all observed times and nodes.

| Solver / stabilization | Sectors | Steps | Largest scaled field error |
|---|---:|---:|---:|
| EONSim volume | 24 | 32 | 1.19e−11 |
| EONSim regular Tet4 | 24 | 32 | 9.43e−12 |
| EONSim regular Tet4 | 48 | 128 | 6.31e−12 |
| svFSI native metric | 24 | 32 | 2.24e−9 |

## Dimensional pressure response

At 1 s the plane-strain Lamé area increase is 0.2030000%. A four-grid Q2/Q1 meridian calculation with 99,875 unknowns and 256 Radau steps gives 0.20300062% at the end and 0.20300485% at midspan. The 3D comparison uses the applied stages read from both pressure residuals, directly coincident section locations and eight full-field snapshots per run. The last column normalizes the largest absolute section difference to the static Lamé strain.

| Solver / stabilization | 3D grid (sectors / fluid / wall / axial) | Steps | Left area increase (%) | Midspan (%) | Max section error (% static) |
|---|---|---:|---:|---:|---:|
| EONSim volume | 24 / 3 / 2 / 6 | 32 | 0.18680312 | 0.19720563 | 7.9791 |
| svFSI native metric | 24 / 3 / 2 / 6 | 32 | 0.18680355 | 0.19720671 | 7.9789 |
| EONSim regular Tet4 | 24 / 3 / 2 / 6 | 32 | 0.18680335 | 0.19720648 | 7.9790 |
| svFSI regular metric | 24 / 3 / 2 / 6 | 32 | 0.18680357 | 0.19720673 | 7.9788 |
| EONSim volume | 48 / 4 / 4 / 6 | 32 | 0.19495029 | 0.20150120 | 3.9657 |
| EONSim volume | 48 / 4 / 4 / 6 | 128 | 0.19494468 | 0.20149434 | 3.9684 |

At the left end on the coarse dimensional mesh the two default solutions differ by 0.000000423 percentage points, while both underestimate the circular-meridian expansion by about 0.01620 percentage points. Changing the dimensional absolute nonlinear tolerance from 1e−14 to 2e−15 on this mesh gave identical stored area strains and cap fluxes at all eight phases for both EONSim metrics. Two trial runs at 1e−19 exhausted Newton/time-step retries after 30 accepted steps and are recorded separately. The benchmark describes an idealized incremental pressure load on a straight elastic wall.

Raw-mode validation reopens every observed VTU, recomputes polygon area, current cap flux and volume, checks EONSim stage and endpoint loads and verifies every accepted external fluid/structure and mesh solve. The compressed archive preserves input, binary, history and field hashes, sampled sections, cap fluxes and the complete similarity comparison. [Accepted runs and failed controls](scaled-tubes.json.xz) · [Paired section and flow table](scaled-tubes.csv) · [EONSim case generator](scaled_tube.py) · [svFSI case generator](scaled_svfsi.py)

```bash
OPENBLAS_NUM_THREADS=1 python scaled_tube.py meridian --problem arterial --mesh 80 80 20 \
  --corner-levels 5 --steps 128 256 --output "$work/arterial-meridian.json"
python compare_scaled.py --archive scaled-tubes.json.xz --csv "$work/scaled-tubes.csv"
```
