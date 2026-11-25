# Production FSI milestones

2026-11-06. User goal: advance EONSim-new toward production FSI. Baseline
`dc378529538259567a78cea9820a202a6187809c` includes PR #36 and #37. Production readiness is an evidence claim for a defined
problem class, hardware and operating envelope, not a single global feature flag.

| Stage | Deliverable | Acceptance / current status |
|---|---|---|
| FSI-PROD-01 | Circular volume-flow inlet and conforming 3D solid-wall tube | Done: [PR #37](https://github.com/saitoasukakawaii/EONSim-new/pull/37) merged; independent mesh topology/volume checks; actual wall response; flux, interface, positive geometry; BE/BDF2/alpha; 1/2/4 rank; restart and rejection. This is an enabling benchmark, not physiological validation. |
| FSI-PROD-02 | Quantitative tube qualification | Rigid steady and oscillatory flow are in main. The elastic static/shared-mesh work in [PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) remains a separate review. This branch adds controlled pressure ramps, circular dynamic compliance, a 20 mm dimensional tube, an independently assembled transient and a pulsatile inlet/RCR response with through-flow. High-Reynolds-number, prestressed and patient-specific validation remain open. [Rigid flow](WOMERSLEY_FLOW.md) · [Elastic pressure response](../research/data/fsi-linear-transient-2026-11-24/scaled-tubes.md) · [Pulsatile perfusion](../research/data/fsi-linear-transient-2026-11-24/perfusion.md) |
| FSI-PROD-03 | Vascular boundary coupling | Stationary multi-RCR outlets, tangentially deforming outlets on coordinate-normal planes, independently driven downstream reservoirs, sampled pressure/flow profiles and passive reference-normal tissue support have same-host tests. One- and two-frequency analytic impedances, sector-area changes, mass and restart are measured. [Terminal equations](../research/data/fsi-rcr-2026-11-24/README.md) · [Moving plane](../research/data/fsi-rcr-2026-11-24/planar-outlets.md) · [Reservoir forcing](../research/data/fsi-rcr-2026-11-24/reservoir-pressure.md) · [Lamé support and work](../research/data/fsi-wall-support-2026-11-24/README.md) |
| FSI-PROD-04 | Physiological geometry and robustness | The synthetic curved tube accepts an oblique fixed planar circular inlet and was exercised through eight local MPI ranks. For the conforming T-junction, independent two-port Stokes operators and transient port and volume harmonics quantify the effects of PSPG, wall storage and time resolution. Patient-derived meshes, initial stress, calibrated wall laws and moving outlets with arbitrary oblique normals remain open. [Curved tube](../research/data/fsi-rcr-2026-11-24/curved.md) · [T-junction](../research/data/fsi-rcr-2026-11-24/branched.md) · [Pressure-driven exchange](../research/data/fsi-rcr-2026-11-24/junction-harmonic.md) |
| FSI-PROD-05 | Distributed production qualification | Growing meshes, 1/2/4/8/16/32 ranks and at least two nodes; strong/weak scaling, iterations, max-rank memory, I/O and failure recovery. No inference from single-node small tests. |

Each independently accepted stage increment uses one branch and one reviewable PR after its local acceptance;
fix CI in that PR and follow the repository's protected merge workflow. Use repository build scripts
and PETSc 3.23.7; validate affected paths incrementally. Preserve failed attempts
and original tolerances. Record both passed and unverified behavior.

No broad requirement to add GPU, AMR, nonmatching interfaces, contact or remeshing
before the first vascular production envelope. Add them only when the target
case requires them. Cross-partition restart remains separate from current
same-partition checkpoint support.

## PROD-02 first quantitative target

Do not reuse PROD-01's coarse transient configuration as an accuracy reference.
For its rho=mu=R=1, mean Q=.01, T=.04, the mean Reynolds number
`2 rho Q/(pi mu R)` is .006366, but Womersley number
`R sqrt(2 pi rho/(T mu))` is 12.533. The oscillatory viscous length
`sqrt(2 mu/(rho omega))` is .11284, compared with radial spacing .5 in the
coarse generator. Low Reynolds number alone does not establish adequate
spatial resolution. This scaling observation is not a proven explanation of
the local wall displacement signs.

Start the quantitative study with a rigid tube and a resolved low-frequency
regime, explicitly recording radius/length, Q or pressure, rho/mu, Re and alpha.
Verify Poiseuille's steady pressure-flow relationship and an appropriate
fully-developed oscillatory reference with consistent inlet/outlet tractions;
do not compare arbitrary entrance flow with a fully-developed formula.
Separate polygon geometry refinement, FE field refinement and time refinement.
Then introduce a compliant wall, quantify field/pressure/area response and
compare against a pinned svFSI case with the same material, mesh, loads and
initial state. Keep reference agreement and MPI equality as separate gates.

## 2026-11-20 · pressure–area equilibrium

The straight, small-strain thick-wall case now has an isolated structural
reference, a monolithic hydrostatic FSI case and a matched upstream svFSI
comparison. The refined isolated wall has 0.1894% area error. The 72-sector
coupled BE case has 0.5684%. The 48-sector cross-code pair agrees to
0.0000227% of the analytical expansion. The 24-sector pair misses the
3% circular target in both codes. Paired step histories differ by up to
9.947% of the static expansion during the initial transient. Dynamic compliant-wall pressure/area
phase, wave speed and a larger operating envelope remain open in PROD-02.
[Hydrostatic case and raw evidence](../research/data/lame-wall-2026-11-20/README.md)
· [Rigid oscillatory flow work](https://github.com/saitoasukakawaii/EONSim-new/pull/41)
