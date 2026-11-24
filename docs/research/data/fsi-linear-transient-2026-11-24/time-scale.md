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
