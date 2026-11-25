# Separating cellwise stabilization time from integration time

With the default transient PSPG formula, refining the time step changes the spatially varying stabilization operator even at rest. A uniform value of the entire coefficient also changes its variation across unequal tetrahedra. The optional FSI input `stabilization_time_scale` fixes the time entering the cell formula. The cell size, viscosity and accepted local velocity still enter normally. At rest, the independent three-dimensional P1/P1 DAE assembles the corresponding PSPG pressure block and pressure-test acceleration contribution separately on every tetrahedron.

On the 24/3/2/6 quarter tube the 1/128 s control gives cell coefficients from 0.00369123 to 0.00385323 m³ s/kg. The 1,141-unknown reference passes the manufactured trajectory with maximum error 8.89e−13. Its largest section change on refining Radau IIA from 256 to 512 steps over 1 s is 7.95e−9 of the Lamé equilibrium area strain. With peak pressure 0.0002 Pa, the maximum nonlinear-to-linear section difference at 1 s falls from 0.09391% of the corresponding equilibrium at 16 steps to 0.001272% at 128 steps and 0.0001010% at 512 steps. For the original peak 0.02 Pa, the fixed-mesh small-displacement reference and the nonlinear ALE model retain a finite-amplitude difference. [Independent matrices, tolerances, all seven sections and pressure controls](time-scale-coarse.json.xz)

Use the case produced by `space_study.py --mesh 24 3 2 6`, build using the repository Release script and run the following commands from this directory. The reference accepts either a uniform `--tau` or the cellwise temporal control. The nonlinear driver authenticates both meshes and the baseline case before running.

```bash
OPENBLAS_NUM_THREADS=1 python reference.py --case "$case_dir" --output /tmp/scale-ref.json \
  --stabilization-time-scale .0078125 --grad-div 0 --stage-solver complex-pair --steps 64 128 256 512
OPENBLAS_NUM_THREADS=1 LD_LIBRARY_PATH="$prefix/lib" python compare.py \
  --case "$case_dir" --reference /tmp/scale-ref.json --executable "$eonsim" \
  --reference-scripts "$pr42_scripts" --work /tmp/scale-eon \
  --steps 16 32 64 128 256 512 --pressures .02 .0002
```

## Changing the fixed cell time on two meshes

All 42 nonlinear trajectories passed the prescribed times and the displacement-field checks. Each spatial operator has its own independently assembled DAE with 512 Radau steps. The table uses the same nonlinear time step, 1/256 s, and compares the linearized polygon area at the left end of the pressure-driven tube at 1 s. Each of the last two columns is the largest absolute error across all seven sections divided by the equilibrium Lamé strain for that load.

| Tet4 grid | Fixed cell time (s) | Local PSPG range at rest (m³ s/kg) | End area increase under 0.02 Pa (%) | Error under 0.02 Pa (% static) | Error under 0.0002 Pa (% static) |
|---|---:|---:|---:|---:|---:|
| 24 / 3 / 2 / 6 | 1/128 | 0.003691–0.003853 | 0.0695993 | 0.01867 | 0.000175 |
| 24 / 3 / 2 / 6 | 1/32 | 0.009147–0.013006 | 0.0713452 | 0.01880 | 0.000172 |
| 48 / 4 / 4 / 6 | 1/128 | 0.003047–0.003722 | 0.0743082 | 0.02012 | 0.000193 |
| 48 / 4 / 4 / 6 | 1/32 | 0.004650–0.009652 | 0.0753575 | 0.02016 | 0.000191 |

Changing only the temporal factor in PSPG shifts the end expansion by 0.001746 percentage points on the coarser mesh and 0.001049 on the finer mesh. The independent spatial operators reproduce that direction and magnitude. Their maximum manufactured-trajectory component error is 2.36e−12, and their largest 256-to-512-step section change is 9.30e−9 of the equilibrium strain. [All 84 observations](time-scales.csv) · [Matched references and field hashes](time-scales.json.xz)

```bash
python compare_time_scales.py --archive time-scales.json.xz --csv "$work/time-scales.csv"
```
