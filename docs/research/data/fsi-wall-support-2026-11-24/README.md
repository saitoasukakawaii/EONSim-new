# Reference-normal spring and dashpot on a thick elastic tube

The wall support acts on triangles of the tagged outer solid surface. Given a reference normal **N**, wall displacement **d**, and velocity **v**, the traction on the wall is −[k (**d** · **N**) + c (**v** · **N**)] **N** per unit reference area. Tangential motion is free. The three-node triangular mass matrix integrates the linear trial and test functions, including all off-diagonal entries. For the implicit stage, the displacement chain coefficient multiplies the spring tangent. The residual, traction power and elastic energy use the same physical reference surface. [Implementation](https://github.com/saitoasukakawaii/EONSim-new/commit/bd163b148acf0c2173115a45c51289f0ae8bcc02)

## Analytic static response

A quarter elastic tube, inner radius 1 m and outer radius 1.2 m, experiences identical pressure at both open ends. Both axial wall ends are on rollers. The interior pressure rises smoothly to 0.02 Pa over 1 s and is then held until 16 s. The wall Young's modulus is 100 Pa and Poisson ratio 0.3. Write the plane-strain Lamé displacement at the outer radius as the sum of the effects of inner pressure and outer pressure. Solving the scalar relation between outer pressure and spring compression gives the supported equilibrium. Damping affects the transient and vanishes in that equilibrium.

| k (Pa/m) | Analytic inner area strain | 24-sector, maximum section error | 48-sector | 72-sector | 96-sector |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.0021745455 | 3.2254% | 1.1702% | 0.5683% | 0.2851% |
| 10 | 0.0014158615 | 2.2038% | 0.8525% | 0.4289% | 0.2242% |
| 50 | 0.0006159456 | 1.1878% | 0.5473% | 0.3024% | 0.1910% |

Each percentage uses the supported equilibrium strain in its own row. The table uses c = 0. Repeating k = 50 with c = 5 and 30 Pa s/m gives the same terminal strain to the displayed digits. At 2 s on the 96-sector mesh, the midplane strains are 0.0005976, 0.0006098 and 0.0005735 for c = 0, 5 and 30, respectively. The spatial study uses 64 steps of 0.25 s and generalized-α with spectral radius 0.5. The time histories retain genuine startup and inertial effects. [All 24 runs, sampled fields, surface audits, and executable and mesh SHA-256](equilibria.json.xz)

## Independent energy and power checks

The integrated support work on each accepted step is old minus new endpoint spring energy, less the stage dissipation multiplied by the accepted step. Integrating the displacement over independent VTK output reproduces endpoint energy on all four grids. On the 24-sector mesh every stage can be reconstructed from consecutive saved endpoints, including the initial backward Euler step. Three-point Gauss integration gives a maximum power discrepancy of 5.09 × 10⁻²¹ W for all six k/c combinations. Across the four grids, the largest energy discrepancy is 1.87 × 10⁻²⁰ J. Larger meshes saved less frequent snapshots, so independent *stage* power is reported only on the 24-sector grid. The balance tests use separate scales for energy and power.

## Reproduction

Build with the repository script for PETSc 3.23.7 Release. The analytic comparison uses the pinned independent Lamé and mesh readers in the [reference scripts](../fsi-smooth-load-2026-11-24/README.md). Set `case_dir` to the corresponding quarter-tube mesh and case produced by `space_study.py`. For 24/48/72/96 sectors the fluid radial, solid radial and axial subdivisions are respectively (3,2,6), (4,4,6), (5,6,8), (8,8,12). Supply snapshot intervals 1, 4, 8 and 8, respectively. Use a fresh work directory for each grid. Adding `--audit-only` checks existing input and mesh hashes and repeats the integration from saved fields.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LD_LIBRARY_PATH="$prefix/lib" \
  python study.py --case "$case_dir" --work "$work" --executable "$eonsim" \
  --reference-scripts "$reference_scripts" --steps 64 --dt .25 --output-interval "$interval" \
  --support 0 0 --support 10 0 --support 50 0 --support 50 5 --support 50 30 --support 0 5
```

For a physical input, add e.g. `wall_supports: [{tag: 14, stiffness: 50, damping: 5}]` under `fsi.domains`. Inputs use passive nonnegative coefficients; either coefficient may be zero.
