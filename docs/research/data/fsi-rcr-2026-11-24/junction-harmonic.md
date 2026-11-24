# A closed-inlet T-junction driven by its two downstream reservoirs

Closing the parent inlet leaves a path between the two daughter reservoirs. Drive their pressures with equal and opposite sinusoids of amplitude 0.02 Pa and initialize both capacitors at zero pressure. The outward flux changes sign at each daughter during the cycle. For a clamped impermeable wall the two discharges sum to zero even during startup. A deformable wall can also store fluid. The square-duct generator gives a daughter area of 0.25 m² and a total fluid volume of 0.8125 m³. Fluid density and viscosity are both one in SI units. These dimensions define a synthetic differential-pressure test. [Geometry generator](../../../../cases/fsi/generate_branched.py)

## Independent two-port solution

For the rigid lumen solve the 3D, linear, time-harmonic incompressible Stokes problem twice under unit terminal tractions. Integrating both outward fluxes forms the two-by-two admittance matrix $Y$. A common terminal pressure produces a constant interior pressure and zero flow. If $Q_2$ responds to a positive unit pressure difference from terminal 2 to 3, define the differential lumen impedance as $Z_\ell=-1/Q_2$. For each circuit let $H_i=(1+\lambda R_{di}C_i)^{-1}$ and $Z_i=R_{pi}+R_{di}H_i$. The terminal pressure satisfies $p_i=H_i p_{di}+Z_i Q_i$. Conservation then gives

$$
Q_2=-\frac{H_2p_{d2}-H_3p_{d3}}{Z_\ell+Z_2+Z_3},\qquad Q_3=-Q_2.
$$

Terminal 2 has $(R_p,R_d,C)=(3,8,0.025)$ and terminal 3 has $(12,32,0.0125)$ in SI units. At continuous time $\lambda=i\omega$. To check the time-stepping implementation, substitute the discrete generalized-α derivative and the ratio of prescribed stage forcing to an interpolated endpoint harmonic. The comparison reconstructs the network both from its separate impedance and directly from $Y$. It checks mass, common pressure, both terminal equations, complex weak residual and power. For PSPG the energy audit includes the pressure-gradient and tested inertial stabilization terms. The Taylor–Hood calculation independently satisfies the physical work balance. All velocity, divergence and pressure operators are integrated using 64 positive Duffy-mapped Gauss points per tetrahedron. [Independent mixed finite-element operator and frequency symbols](junction_harmonic.py)

| 1 Hz grid refinement | P2/P1, differential lumen impedance | P1/P1, fixed PSPG 0.01 | P1/P1, PSPG 0.01 divided by refinement squared |
|---:|---:|---:|---:|
| 1 | 905.15 + 69.22i | 814.07 + 31.40i | 814.07 + 31.40i |
| 2 | 859.57 + 67.76i | 521.19 + 31.10i | 805.03 + 51.80i |
| 3 | 854.78 + 67.63i | 478.38 + 31.54i | 831.59 + 60.05i |
| 4 | — | 462.62 + 31.73i | 841.29 + 63.29i |

Impedance is in Pa s/m³ with the above sign convention. In the fixed-0.01 column the pressure-gradient contribution to the power balance reaches 40.05% of the terminal complex power magnitude on grid 4. Reducing the prescribed PSPG coefficient as $h^2$ on these uniform meshes brings that fraction down to 6.96%. Holding an artificial pressure coefficient fixed changes the spatial refinement experiment. The normal production volume coefficient is recomputed from step size and local geometry. The startup check below exercises that path separately. [Complex responses, errors and solver dimensions](junction-admittance.csv)

## Three-dimensional startup and periodic response

At 1 Hz on grid 1 with fixed PSPG 0.01, 32 steps per cycle and ten cycles, EONSim gives a terminal-2 flow amplitude of 2.35135793e−5 m³/s at +121.0144° relative to its positive reservoir sine. Terminal 3 has the same amplitude at −58.9856°. The worst of either terminal's four last-cycle waveforms changed by less than 7.3e−8% of its harmonic amplitude from the previous cycle. The flow phasor differs from the independent continuous-time same-space prediction by 0.2432%. At identical spatial and temporal discretization the relative complex difference is 7.13e−10% or less. Using continuous-time P2/P1 on the same linear-sided geometry changes the prediction by 11.85% relative to that P2/P1 phasor. Distinguishing these three references exposes the error due to the discrete pressure/velocity space. [Waveforms, circuit residuals and two-port comparisons](junction-periodic.csv)

Nine further 3D startup runs compare every accepted stage and endpoint with an independent linear DAE initialized at rest. They cover three grids, four to 32 accepted steps, fixed PSPG and the default volume-based coefficient. The startup uses backward Euler for its first step. At generalized-α spectral radius 0.5 the later effective derivative interval is $8\Delta t/15$. Across both terminals the largest normalized flow error is 1.07e−11, and the largest terminal-pressure error is 4.67e−13. All terminal fluxes are independently integrated again on the final VTU. Deformable-wall records in the periodic table report measured storage and net flux separately from rigid-lumen errors. [Every startup trajectory](junction-startup.csv) · [Independent transient assembly](junction_startup.py) · [Driven 3D case](junction_periodic.py)

## Reproduction

Compile EONSim through the repository Release script. Use the fluid/wall mesh returned by the same T-junction generator for both discretizations. All phases use a sine reference and outward flow at each daughter. The archive contains operator records, final two measured cycles, raw-file hashes and every paired transient startup sample. [Archived measurements](junction-harmonic.json.xz) · [Verification and CSV replay](compare_junction_harmonic.py)

```bash
OPENBLAS_NUM_THREADS=1 python junction_harmonic.py --mesh "$work/g2" --refinement 2 \
  --order 2 --linear-solver steady-lu --hz 0 .25 1 2 --output "$work/g2-p2.json"
python junction_periodic.py --executable "$eonsim" --work "$work/g2-f1" \
  --grid 2 --tau .0025 --hz 1 --samples 32 --cycles 10
python junction_startup.py --executable "$eonsim" --work "$work/g2-start" \
  --grid 2 --default-pspg --samples 32 --steps 12
python compare_junction_harmonic.py --archive junction-harmonic.json.xz \
  --reference-csv "$work/admittance.csv" --solver-csv "$work/periodic.csv" --startup-csv "$work/startup.csv"
```
