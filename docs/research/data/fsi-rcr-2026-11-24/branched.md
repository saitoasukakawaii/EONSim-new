# Flow split, wall storage and RCR pressure in a symmetric T-junction

The manufactured T has a square inlet, two equal daughter branches and one stationary RCR on each outlet. The inlet is normal to the x axis and the outlet caps face opposite y directions. Each cap has area 0.25 m². The mesh, inlet shape and axial ends are fixed across each EONSim–svFSI pair. This geometry permits a separate stationary Stokes experiment, a clamped-wall pulse, and direct measurement of wall storage in the deformable junction. [Mesh generator](../../../../cases/fsi/generate_branched.py) · [Circuit and interface equations](README.md)

## Why a fourfold terminal resistance gives nearly equal steady flows

Let positive flow leave the lumen at either daughter. Set the inlet velocity and wall velocity to zero, impose a small daughter pressure difference, and recover both fluxes from the nodal Stokes solution. For a left-right symmetric linear lumen the antisymmetric mode satisfies

$$
p_2-p_3=-\mathcal R_\Delta(Q_2-Q_3).
$$

The symmetric inlet component adds the same flow at both daughters. At steady state each downstream circuit imposes $p_i=(R_{p,i}+R_{d,i})Q_i$ relative to its prescribed distal pressure, which is zero here. With $Q_2+Q_3=Q_{in}$, the independent prediction is

$$
\frac{Q_2}{Q_{in}}=\frac{\mathcal R_\Delta+R_3}{2\mathcal R_\Delta+R_2+R_3}.
$$

| Fluid tetrahedra | Measured $\mathcal R_\Delta$ (Pa·s/m³) | Predicted $Q_2/Q_{in}$ | Computed at 0.002 m³/s | Computed at 0.0002 m³/s |
| ---: | ---: | ---: | ---: | ---: |
| 312 | 406.888 | 48.100775% | 48.101014% | 48.100799% |
| 2,496 | 260.425 | 47.134673% | 47.134956% | 47.134701% |
| 8,424 | 239.005 | 46.904376% | 46.904676% | 46.904406% |

Here $R_2=44$ and $R_3=11$ Pa·s/m³. Using the terminal elements alone gives 20%. The lumen carries most of the differential resistance on every tested grid. Reversing the Stokes jump from +0.02 Pa to −0.01 Pa gives the same resistance. Swapping the two terminal circuits gives the complementary flow split. Equal circuits give 50% on every mesh. Reducing the inlet flow tenfold reduces the absolute difference from the linear prediction by about a factor of ten. The coupled calculations use their own time-marched fields, no-slip clamped wall, and two evolving capacitor pressures. The audit reconstructs the cap fluxes directly from both independently solved VTUs, checks each stage circuit and requires small terminal drift over the final quarter of the run. Grid refinement still changes the predicted split. [Raw flux, pressure, drift, mesh and field receipts](branch-conductance.json.xz) · [Independent experiment](branch_conductance.py) · [Field audit](audit_conductance.py)

## Early flux mostly fills the compliant junction

With a constant positive mean inlet of 0.002 m³/s, the Neo-Hookean wall initially stores most of the entered fluid. The numbers below are one-second averages ending at the listed times. On the two meshes the accumulated volume gains at 128 s are 0.01244 and 0.01143 m³ respectively. The final shares of total outflow going to the higher-resistance terminal are 48.087% and 47.114%. Each circuit satisfies the stage power identity and the reported volume is integrated on the deformed lumen. [Milestone flows and volumes](branched-storage.csv) · [Long-transient runner](branch_study.py)

| End of averaging window | 312 cells, total outflow/inflow | 2,496 cells, total outflow/inflow |
| ---: | ---: | ---: |
| 2 s | 8.76% | 8.63% |
| 8 s | 71.45% | 75.38% |
| 16 s | 94.37% | 96.17% |
| 32 s | 99.78% | 99.91% |
| 128 s | 100.00% | 100.00% |

## Two-cycle zero-mean pressure and flux comparison

On the same tagged mesh both programs imposed the signed sinusoidal inlet with a peak of $2\times10^{-4}$ m³/s. The deformable comparison uses a linear wall with $E=100$ Pa and $\nu=0.3$, and observes the first two cycles from rest. Both solvers' accepted steps, native capacitor and boundary pressures, and raw VTU cap flows were checked. The maximum in each column is taken over both outlets, so the two relative-error columns can attain their maxima at different ports. [Time histories, convergence and excluded runs](branched-comparison.json.xz) · [Each outlet and denominator](branched-ports.csv)

| 312-cell case | Steps/cycle | Largest outlet discrepancy / inlet peak | Largest discrepancy / that native outlet's peak |
| --- | ---: | ---: | ---: |
| Elastic, 0.2 s period | 32 | 0.2084% | 28.57% |
| Elastic, 2 s period | 32 | 3.5187% | 211.36% |
| Elastic, 2 s period | 64 | 2.3560% | 142.35% |
| Elastic, 2 s period, native grad-div disabled | 64 | 2.3939% | 105.23% |
| Clamped, 2 s period | 64 | 0.4572% | 0.93% |
| Clamped, 2 s period | 128 | 0.1977% | 0.40% |

At the 2 s period and 64 steps/cycle, the native compliant outlet peaks were only $3.106\times10^{-6}$ and $3.310\times10^{-6}$ m³/s. The maximum discrepancy was $4.712\times10^{-6}$ m³/s. The small reference signal explains the large *relative* percentage. The deformation and transient flux into storage are part of the numerical problem. Turning off native grad-div alone left the absolute discrepancy almost unchanged in this junction. The rigid-fluid control uses svFSI's native NS equation on the clamped lumen. The attempted fully clamped native mesh equation finished its first step at residual 1 after 40 corrections. Several elastic external trajectories also failed their linear solve or geometry update. Their diagnostics are archived separately from completed waveforms. Two earlier EONSim attempts encountered the interface boundary-tag error subsequently fixed and covered by the [sliding and clamped regression](interface-constraints.json).

## Replay

Build EONSim with the repository Release compile script and use the fixed svFSI version and external build script documented in the [matched single-port study](README.md). The zero-grad-div build changes only the native coefficient. The small external helper module comes from the pinned PR 42 source. The recorded binary and mesh hashes identify each run. A single-rank steady experiment can launch the solver directly on its prepared partition. The multi-rank partition tests use MPI. Run the archived-table comparison in this directory with

```bash
python compare_branches.py --archive branched-comparison.json.xz \
  --ports-csv /tmp/ports.csv --storage-csv /tmp/storage.csv
for grid in 1 2 3; do
  python branch_conductance.py --refinement "$grid" --steps 80 --duration 8 \
    --executable "$eonsim" --mpiexec "$mpiexec" --work "$runs/g$grid"
done
python audit_conductance.py --runs "$runs" --reference-scripts "$pr42_scripts" \
  --executable "$eonsim" --output /tmp/branch-conductance.json.xz
```

For a fresh paired transient, use `branch_external.py --refinement 1 --period 2 --samples 64 --cycles 2 --unequal` with the executable, library, reference-script and new work paths shown by `--help`. For the rigid control add `--clamped --rigid-reference`. [External case and phase auditor](branch_external.py) · [Cross-case replay](compare_branches.py)
