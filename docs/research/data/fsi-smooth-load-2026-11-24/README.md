# Two-ended elastic tube under a smooth pressure ramp

On the fixed 48-sector mesh, matching the two assembled port pressures at every step and both ends to within 6.94e−18 Pa leaves a 4.0975% difference in sectional expansion at 1 s for Δt = 1/128 s. The denominator is the Lamé **equilibrium** area strain (0.00217454545). It sets the scale for the comparison. No exact transient displacement is assumed.

The large transient gap occurs in an artificial thick-walled cylinder, lumen diameter 2 m and Young modulus 100 Pa. At 128 steps the two left-end area increases are 0.0733993% and 0.0644891% of their initial area. Their difference is 0.0089101 percentage points. A separate 20 mm diameter, 0.4 MPa straight tube gives 0.18680312% and 0.18680355% after an 80 Pa ramp on its coarse mesh. A third experiment imposes actual through-flow and an RCR outlet, where the native terminal time stage and axial resolution contribute measurable differences to flow transfer. [Discrete stabilization](../fsi-linear-transient-2026-11-24/discrete-metric.md) · [Dimensional tube](../fsi-linear-transient-2026-11-24/scaled-tubes.md) · [Pulsatile perfusion](../fsi-linear-transient-2026-11-24/perfusion.md)

The [Release validation record](release-validation.md) lists the 62 distinct incremental CTests, the 54 Python tests, their passing source revisions and the earlier failure and timeout controls.

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

## One-term control of discrete incompressibility

At 1/128 s and at the x = 0 end, the actual area-strain values at 1 s are 0.000733992632 in EONSim and 0.000644891365 in svFSI. The difference is 0.00891013 percentage points of reference cross-sectional area, or 13.82% of the svFSI instantaneous expansion there. The 4.0975% above uses the analytical equilibrium strain as its denominator.

EONSim at the base commit has residual-based streamline and pressure stabilization. Its momentum residual does not include the svFSI 3D grad-div term. For a paired diagnostic build we set only τC in `FLUID3D_M` to zero before the residual and tangent use it. For the P1/P1 FSI fluid this removes the momentum term ∫ τC (∇·v)(∇·u) dV. The pressure-test stabilization with τM and other small-scale contributions remain active. Both binaries used identical load tables, mesh and linear/nonlinear tolerances. The full native run still defines the reference result.

| Δt (s) | Original svFSI vs EONSim at 1 s | svFSI with τC = 0 vs EONSim at 1 s |
|---:|---:|---:|
| 1/8 | 5.032% | 2.345% |
| 1/16 | 4.952% | 2.203% |
| 1/32 | 4.654% | 1.746% |
| 1/64 | 4.394% | 1.084% |
| 1/128 | 4.097% | 0.497% |

For Δt = 1/128 s, zeroing only τC reduces the maximum intercode gap from 4.0975% at an end to 0.4967% at the midplane. In that modified calculation, the volume-weighted spatial RMS of the discrete fluid divergence rises from 5.696e−4 to 6.673e−4 s⁻¹. This identifies a major source of the difference for this mesh, time and loading. It provides no exact transient reference that would select either formulation by its wall displacement. [Control patch](svfsi-zero-grad-div.patch) · [All section strains, volume gains and divergence](grad-div.json) · [Maximum and signed gaps](grad-div.csv)

To reproduce, create a second checkout at the same pinned svFSI commit. Apply the observer patch and the one-term patch to it, then compile through the same `build-svfsi.sh`. Run `run_study.py --mode matched --steps 8 16 32 64 128 --linear-atol 1e-19` once with each binary in separate empty directories. Pass those roots to `audit_grad_div.py --native ... --ablated ...`, along with `--archive`, `--reference-scripts`, `--eon` (the run root containing eon-N), `--steps 8 16 32 64 128` and `--output`. The audit requires byte-identical paired decks, tables and meshes, valid FS and MS convergence at every accepted step and matching residual-side loads at both ports.

## Controlled EONSim grad-div viscosity

The optional `fsi.grad_div_viscosity` uses a uniform coefficient in Pa·s. In EONSim on the same mesh at Δt = 1/128 s, increasing it from 0 through 1, 4 and 16 Pa·s changed the worst 1 s sectional difference from 4.097%, through 3.181%, 1.058% and 5.215% against the native svFSI solution. The endpoint fluid divergence RMS fell monotonically from 6.948e−4 to 4.929e−4 s⁻¹. Smaller divergence alone did not predict closer wall response. These coefficients were a fixed sensitivity sweep across three time resolutions. The default remains zero. The upstream τC also varies with metric, time step and velocity.

[Full sweep with dissipated power and seven sections](fixed-grad-div.json) · [Driver](grad_div_sweep.py). Use the same `--archive`, `--reference-scripts`, `--executable` and `--work` arguments as above, plus `--native` pointing to the matched svFSI output root and `--steps 32 64 128`.

## Axial reflection control

The equal end pressures, identical rollers, uniform materials and geometry imply mirror symmetry in the continuum. The baseline mesh splits prisms into oriented tetrahedra. At 1 s on the 48-sector, 32-step case the two EONSim end strains were 0.0007502692 and 0.0008472629. For svFSI they were 0.0006490577 and 0.0008547844. The control mirrors every reference coordinate across the midplane, exchanges the physical end tags, and preserves positive tetrahedral orientation. With identical solver decks and residual-side loading the expanded end switched sides in both programs.

Reflecting back all seven sections at 0.5 and 1 s gave maximum absolute strain differences of 2.17e−19 for EONSim and 1.27e−15 for svFSI. The audit also compares the reflected fluid pressure, all three velocity and displacement components, and both mesh connectivities. This isolates the left–right asymmetry of this mesh from any bias specific to the inlet or outlet label. Averaging both ends can hide the local error. [Node and section comparisons](reflection.json)

To reproduce, run `space_study.py` twice with identical `--mesh 48 4 4 6 --steps 32 --nonlinear-limit 30`, adding `--reflect` to one run. Supply the same observer binary to both. Then run `audit_reflection.py --original <base> --mirrored <mirror> --reference-scripts <PR42-scripts> --output reflection.json`. The metadata distinguishes solver binaries recorded at process launch from executable hashes supplied when retrospectively auditing early runs.

### Independent mirror audit of the bore area

The audit reconstructs each quarter-section directly from tag 13 on the reference solid mesh. It differentiates the polygon area with respect to each vertex and contracts that gradient with the transverse solid displacements read from the matching VTU. Both time stamps and every station position, count and cached value must agree. The cache tolerance is 2e−14 plus 2e−12 times strain. The independent comparison of mirrored VTU strains uses 5e−12 plus 1e−8 times strain. Each of four corruptions in an isolated copy was rejected, including adding 0.001 strain to a single midpoint. The replay writes one JSON object. Its original entry matches the positive field archive and its four other entries match the four recorded rejection reasons. All original field checks continue to pass. [Recorded measured fields and areas](reflection.json) · [Negative controls](reflection-negative-controls.json)

```bash
python check_reflection_controls.py --original "$original" --mirrored "$mirrored" \
  --reference-scripts "$pr42_scripts" --output "$work/reflection-controls.json"
```

[Discrete metric, frozen grad-div time and current-equation convergence](../fsi-linear-transient-2026-11-24/discrete-metric.md)
