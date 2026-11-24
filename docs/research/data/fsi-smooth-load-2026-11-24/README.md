# Two-ended elastic tube under a smooth pressure ramp

On the fixed 48-sector mesh, matching the two assembled port pressures at every step and both ends to within 6.94e−18 Pa leaves a 4.0975% difference in sectional expansion at 1 s for Δt = 1/128 s. The denominator is the Lamé **equilibrium** area strain (0.00217454545). It sets the scale for the comparison. No exact transient displacement is assumed.

## Physical and temporal comparison

We use the quarter tube, material, roller ends, Tet4 mesh and zero initial fields from [the pressure-face study](../fsi-pressure-faces-2026-11-24/README.md). The two pressure ends receive 0.02 x³(10 − 15x + 6x²) Pa, with x = min(t/1 s, 1). The outward unit normal points out of the fluid. EONSim `6a5ac96` uses backward Euler at startup and then a common generalized-α state and load stage at tₙ + 2Δt/3.

Fortran svFSI `94a2ff5` increments its clock before residual assembly in `MAIN.f`. `SETBCNEUL` reads the face table at that clock through `IGBC`, while `PICI` interpolates state fields to their α stages. The endpoint control supplies the analytical pressure at each endpoint. The matched control supplies the EONSim stage pressure at the corresponding svFSI endpoint lookup. Its input table therefore depends on Δt. Both controls use the upstream general Neumann interface. The table contains negative scalar traction, one uniform value per face node; its repeat time is strictly later than the last output. Only sampled values are matched. The continuous analytical profile between samples is not asserted for the piecewise-linear tables.

The observer reads the actual signed load array immediately before boundary assembly in svFSI. Every inner iteration must report both faces and the prescribed extrema. For the unmodified and observed binaries at Δt = 0.25 s all four accepted velocity, displacement and pressure fields match exactly on both domains. Only the fluid domain has a physical pressure comparison. EONSim records the pressure supplied to the accepted-step residual and the two individual face histories. Geometry, cell connectivity, timestamps, finite fields and both svFSI equation convergence histories are checked independently.

| Δt (s) | Native load sampling, gap at 0.5 s | Matched, gap at 0.5 s | Native, gap at 1 s | Matched, gap at 1 s |
|---:|---:|---:|---:|---:|
| 0.5 | 4.969% | 4.969% | 4.123% | 4.878% |
| 0.25 | 2.085% | 1.255% | 5.523% | 4.869% |
| 0.125 | 1.791% | 0.882% | 3.408% | 5.032% |
| 0.0625 | 1.037% | 0.823% | 3.443% | 4.952% |
| 0.03125 | 0.607% | 0.800% | 3.982% | 4.654% |
| 0.015625 | 0.614% | 0.758% | 4.058% | 4.394% |
| 0.0078125 | 0.632% | 0.703% | 3.930% | 4.097% |

The gap is the maximum absolute difference at seven common axial sections. The axial coordinate of the worst section may change. The first step receives identical pressure in all three runs at each Δt. Midplane wall displacement divided by Δt times the corresponding radial velocity equals 1 in EONSim and 49/96 in svFSI, verified from saved fields. For this svFSI FSI/lElas equation, `INITIALIZE.f` uses αₘ = 5/6, αf = 2/3, γ = 2/3 and β = 49/144. Starting from rest, `PICP/PICC` give the ratio β/γ. The result diagnoses a startup difference. It does not apportion the remaining 1 s discrepancy among spatial stabilization, grid motion and time discretization.

[First-step kinematics and net flow](startup.csv) · [Section gaps for every accepted step](section-gaps.csv) · [Displacements, velocities, volume and all seven strains](fields.csv.xz) · [Port extrema, source/lookup/state times and iteration counts](ports.csv.xz) · [Binaries, convergence, control and common-time results](results.json)

## Reproduce

Begin with the archived inputs and pinned reference Python scripts described in [the preceding study](../fsi-pressure-faces-2026-11-24/README.md#重现). For this example, set `inputs` to the extracted archive, `reference_scripts` to PR 42's scripts, `svsrc` to the pristine upstream checkout, `svprefix` to its compiler/MPI environment, and `work` to a new absolute directory. NumPy and the VTK Python bindings are required by the audit.

```bash
data="$PWD/docs/research/data/fsi-smooth-load-2026-11-24"
old="$PWD/docs/research/data/fsi-pressure-faces-2026-11-24"
mkdir -p "$work"
bash scripts/cloud/restore.sh 3.23.7
echo '{"tests":["fsi_alpha_verification","fsi_pressure_state"]}' > "$work/selection.json"
bash scripts/cloud/run.sh 3.23.7 release explicit "$PWD/.cloud" "$work/selection.json"
git -C "$svsrc" worktree add --detach "$work/sv-observer" 94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571
git -C "$work/sv-observer" apply "$data/svfsi-pressure-observer.patch"
bash "$old/build-svfsi.sh" "$svsrc" "$svprefix" "$work/sv-pristine-build"
bash "$old/build-svfsi.sh" "$work/sv-observer" "$svprefix" "$work/sv-observer-build"
suite=(--archive "$inputs" --work "$work/runs")
LD_LIBRARY_PATH="$PWD/.cloud/petsc-3.23.7/lib" python3 "$data/run_study.py" "${suite[@]}" --mode eon \
  --executable build/cloud-3.23.7-release/eonsim --steps 2 4 8 16 32 64 128
export LD_LIBRARY_PATH="$svprefix/lib"
python3 "$data/run_study.py" "${suite[@]}" --mode control --executable "$work/sv-pristine-build/bin/svFSI" --steps 4
for mode in endpoint matched; do
  python3 "$data/run_study.py" "${suite[@]}" --mode "$mode" --executable "$work/sv-observer-build/bin/svFSI" --steps 2 4 8 16 32
  python3 "$data/run_study.py" "${suite[@]}" --mode "$mode" --executable "$work/sv-observer-build/bin/svFSI" --steps 64 128 --linear-atol 1e-19
done
unset LD_LIBRARY_PATH
OPENBLAS_NUM_THREADS=1 python3 "$data/audit_study.py" "${suite[@]}" --reference-scripts "$reference_scripts" \
  --steps 2 4 8 16 32 64 128 --output "$work/audit"
```

At Δt = 1/64 s the original 1e−15 linear absolute tolerance allowed a zero mesh correction with a first-step normalized MS residual of 1.26e−8. Both original runs were excluded. Tightening both linear absolute tolerances to 1e−19 allowed both nonlinear equations to pass the original 1e−8 gate at every step for Δt = 1/64 and 1/128 s. A paired 1/32 s endpoint control with these two tolerances gave maximum nodal differences 4.98e−17 m in displacement, 5.78e−16 m/s in velocity and 1.01e−14 Pa in pressure over all 32 steps. This is a single-rank intercode study.
