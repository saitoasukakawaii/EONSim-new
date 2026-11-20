# Pressure-driven oscillations in a rigid tube

The fixed-grid transient fluid solver accepts an independent sinusoidal
pressure on each tagged natural boundary. For example, the following two
entries load the normal component of a flat inlet perpendicular to x and set
the transverse velocities to zero. Use a zero-pressure outlet with the same
transverse constraints and a no-slip lateral wall for this benchmark.

```json
[
  {"tag": 1, "type": "pressure", "components": [0], "value": 0.0,
   "pressure_time": {"amplitude": 0.02, "period": 1.5707963267948966}},
  {"tag": 1, "type": "velocity", "components": [1, 2], "value": [0, 0, 0]}
]
```

With mean `value`, signed amplitude A and period T, the prescribed pressure is
`r(t) [value + A sin(2πt/T)]`. If `pressure_time.ramp_time` is positive, let
`s = clamp(t/ramp_time, 0, 1)` and `r = s³(10 − 15s + 6s²)`. Otherwise r=1.
The normal traction is −pn using the outward normal. The pressure profile and
an outer linear boundary ramp are mutually exclusive. The mean may be zero.
Each pressure condition uses absolute solver time across restarts and its
parameters enter the checkpoint signature. Constant and linearly ramped legacy boundaries retain their
checkpoint representation.

BE and BDF2 evaluate the traction at the endpoint. Generalized-alpha uses
the stage time after the BE startup step. Endpoint pressure follows the
integrator's stage-to-endpoint update. Add `-fluid_boundary_history` to a
transient tagged case to request one globally reduced row per boundary tag
after each accepted step, including on restart. Rows contain area, outward
volume flow and area-averaged computed pressure. The final tag summary is
also available without the per-step option.

## Reproduce the circular comparison

The synthetic reference uses R=1 m, L=2 m, ρ=1 kg/m³, μ=1 Pa s and a
0.02 Pa sine pressure drop at ω=4 rad/s. The wall is fixed. The zero initial
velocity approaches the periodic solution over several cycles. The
Womersley parameter is 2. Peak Reynolds number based on analytical mean
cross-sectional speed and diameter is 0.002062. A fully developed circular
solution satisfies the prescribed normal traction and transverse end
constraints. FE fields live on an inscribed polygon with planar Tet4 faces.

```sh
python scripts/study_womersley.py --executable /path/to/eonsim --work /tmp/wom64 \
  --mesh 48 8 12 --samples 64 --cycles 3 --scheme bdf2 --check
python scripts/study_womersley.py --work /tmp/wom64 --analyze-only --check
python scripts/audit_womersley_fields.py --work /tmp/wom64
```

The three mesh counts give circumferential sectors, radial rings and axial
slabs. Each solve takes a fresh directory. The postprocessor fits the complex
fundamental to a complete final cycle. It uses `Q=(Qout−Qin)/2` because both
end integrals use outward normals. A second full cycle supplies the samplewise
periodicity check. The analytic convention is `Q(t)=Im(Q̂ exp(iωt))`.
For `z²=−iα²` with `α=R sqrt(ωρ/μ)`, the complex response is

\[
\widehat Q=\frac{\pi R^2\Delta p}{i\omega\rho L}
  \left[1-\frac{2J_1(z)}{zJ_0(z)}\right].
\]

The benchmark evaluates the power series at α=2. A separately integrated
radial profile provides a numerical oracle. The continuum reference has
amplitude 0.00323951534417 m³/s and phase −33.2615734° relative to the
pressure drop. The per-tag pressure is a computed trace under a prescribed
normal stress. Its error and the local divergence are reported separately.
[Womersley (1955), pp. 553–563](https://doi.org/10.1113/jphysiol.1955.sp005276)
· [Bessel power series, DLMF 10.2.2](https://dlmf.nist.gov/10.2.E2)

## Compare space, time and processors

Use `--ranks 2` or `--ranks 4` to generate and use a matching partition.
`compare_womersley_runs.py mpi SERIAL PARALLEL --ranks N` checks owned
nodal fields, ghost copies and every accepted boundary sample. For temporal
refinement, keep the mesh and physical parameters fixed and double the
samples per cycle. `compare_womersley_runs.py time CASE1 CASE2 CASE3`
computes adjacent complex differences and their log₂ ratios. The normal
coefficient depends on each cell size, accepted velocity and effective
integration step. A separate family with `--tau 0.003` fixes the coefficient
throughout all cells and all steps.

The svFSI comparison uses upstream release 2022.09.26, generalized-alpha
with spectral radius zero, the same nodes and tetrahedra, the same pressure
and transverse end conditions, and the native stabilization in each code.
Run the two executables in their respective runtime environments.

```sh
python scripts/study_womersley.py --executable /path/to/eonsim --work /tmp/wom-alpha \
  --mesh 48 8 12 --samples 64 --cycles 3 --scheme generalized_alpha --rho-infinity 0
python scripts/compare_svfsi_womersley.py --case /tmp/wom-alpha --work /tmp/wom-sv \
  --executable /path/to/svFSI --check
python scripts/compare_svfsi_womersley_fields.py --case /tmp/wom-alpha --work /tmp/wom-sv
```

The cross-code field audit requires Python VTK. The harmonic, convergence and
EONSim field calculations use the Python standard library. The evidence
includes the coarse misses and individual field measurements.
[Measurements, environment and replay](../research/data/womersley-2026-11-20/README.md)
