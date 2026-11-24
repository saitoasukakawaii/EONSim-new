# Independent small-pressure transient of an elastic tube

This reference solves the infinitesimal-pressure limit of the conforming P1/P1 fluid and P1 elastic wall on the archived 48-sector mesh. It checks the nonlinear EONSim solver with a second implementation of the **same spatial operator**. It provides a transient reference at fixed mesh, PSPG time coefficient and grad-div viscosity. The continuum thick-cylinder Lamé solution supplies only the equilibrium normalization.

The independent circular meridian resolves the loaded-end corner on progressively finer meshes. A separate dimensional experiment isolates similarity from the effect of geometry, material and loading time. [Corner refinement](axisymmetric.md#corner-refinement-and-exact-displacement-elimination) · [Dimensional checks](scaled-tubes.md)

## Equations and checks

The conforming velocity is shared across the fluid–solid interface. The unknowns are free velocities, all fluid pressures and free solid displacements. The Python assembler integrates the consistent P1 mass, symmetric Newtonian stress, linear isotropic wall elasticity, divergence-pressure pair, and the acceleration and pressure-gradient parts of PSPG. The optional momentum term is $\gamma(\nabla\!\cdot w,\nabla\!\cdot u)$. Solid displacement obeys $\dot d=v_s$. Moving-domain and convective products are of higher order about the initial state at rest. Interfacial mesh displacement therefore adds no independent term to the first-order momentum balance.

The resulting system $M\dot y+Ky=f(t)$ has 3,485 unknowns and a singular mass matrix. Two-stage Radau IIA solves the coupled collocation equations directly with SciPy SuperLU. Fluid end pressures follow the same quintic ramp to the prescribed peak at 1 s. The implementation independently numbers and constrains components, orients boundary loads by face ownership, and differentiates the polygon area of each inner-wall ring.

- Unit hydrostatic pressure with an independently loaded wall gives a full-system infinity residual of 8.54e−15. A manufactured quadratic trajectory checks the differential and algebraic rows together. The maximum component errors for the two coefficients were 4.49e−10 and 6.65e−10.
- With 8, 16, 32, 64 and 128 steps, the final two observed orders for maximum inter-resolution wall strain at 1 s are 3.00 and 3.01 for both coefficients. The 64→128 change across both sampling times is at most 5.70e−7 of the analytical equilibrium strain. The largest collocation solve residual at 128 steps was below 7e−18.
- The comparison requires a matching baseline input hash, complete accepted history, 0.5 and 1 s fields, and all seven axial rings. All 30 nonlinear runs passed. We fixed PSPG $\tau=0.007716762652107021$ m³ s/kg in both programs and scaled the absolute nonlinear tolerance with pressure. Native svFSI uses different stabilization and is assessed in the [separate intercode study](../fsi-smooth-load-2026-11-24/README.md).

## Results at 1 s

Entries are $100\max_x|\epsilon_{A,h}^{\rm EON}-\epsilon_{A,h}^{\rm Radau}|/\epsilon_A^{\rm Lamé}$, with the linear reference rescaled to the same pressure. EONSim uses 256 time steps, and the reference uses 128 Radau steps. All seven sections are included.

| Peak pressure (Pa) | $\gamma=0$ Pa·s | $\gamma=4$ Pa·s |
|---:|---:|---:|
| 0.02 | 0.020169% | 0.017962% |
| 0.002 | 0.001663% | 0.001492% |
| 0.0002 | 0.000187% | 0.000155% |

The pressure sweep separates finite-amplitude ALE effects from the time-integration and reference errors. For example, at 0.0002 Pa with zero grad-div, reducing the EONSim step from 1/64 through 1/128 to 1/256 s changes the discrepancy from 0.006237% through 0.001394% to 0.000187%. At the largest pressure, finite-amplitude and temporal errors can cancel at intermediate step sizes. Agreement in this limit tests the implementation of the chosen spatial equations. Accuracy of the native transient at finite mesh size requires spatial refinement or an independent continuum solution.

[Radau histories, γ = 0](radau-zero.json) · [Radau histories, γ = 4](radau-four.json) · [Nonlinear runs, γ = 0](eonsim-zero.json) · [Nonlinear runs, γ = 4](eonsim-four.json)

## Reproduction

Set `case_dir` to the archived `coupled/sv05-s48` folder and `reference_scripts` to the pinned PR 42 scripts identified in the [pressure-face reproduction notes](../fsi-pressure-faces-2026-11-24/README.md). The reference integrator uses Python, NumPy and SciPy. The nonlinear comparison additionally uses the original VTU reader. Set `work` to a new output directory. Build EONSim through the repository script with PETSc 3.23.7 Release, as in the linked study. The run binary comes from the [grad-div implementation](https://github.com/saitoasukakawaii/EONSim-new/commit/85546ef04a707764e27a5b06adfc5b20b858e4cb).

```bash
data="$PWD/docs/research/data/fsi-linear-transient-2026-11-24"
mkdir -p "$work"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
for gamma in 0 4; do
  python3 "$data/reference.py" --case "$case_dir" --tau 0.007716762652107021 \
    --grad-div "$gamma" --steps 8 16 32 64 128 --output "$work/radau-$gamma.json"
  LD_LIBRARY_PATH="$prefix/lib" python3 "$data/compare.py" --case "$case_dir" \
    --reference-scripts "$reference_scripts" --reference "$work/radau-$gamma.json" \
    --executable "$eonsim" --work "$work/eonsim-$gamma" \
    --steps 16 32 64 128 256 --pressures 0.02 0.002 0.0002
done
```

The [axisymmetric continuum reference](axisymmetric.md) provides an independent space refinement, stage power and mass checks, and a comparison of both tetrahedral solvers at common axial stations.

[Dependence of the native Tet4 momentum stabilization on the time step](discrete-metric.md)

[Frequency-dependent area compliance, phase and total inward flux](harmonic.md)
