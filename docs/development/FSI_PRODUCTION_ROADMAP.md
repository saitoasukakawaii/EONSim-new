# Production FSI milestones

2026-11-06. User goal: advance EONSim-new toward production FSI. Baseline
`dd27eef` includes PR #36. Production readiness is an evidence claim for a defined
problem class, hardware and operating envelope, not a single global feature flag.

| Stage | Deliverable | Acceptance / current status |
|---|---|---|
| FSI-PROD-01 | Circular volume-flow inlet and conforming 3D solid-wall tube | Merged via [PR #37](https://github.com/saitoasukakawaii/EONSim-new/pull/37), main `dc37852`; independent mesh topology/volume checks; actual wall response; flux, interface, positive geometry; BE/BDF2/alpha; 1/2/4 rank; restart and rejection. This is an enabling benchmark, not physiological validation. |
| FSI-PROD-02 | Quantitative tube qualification | [48-hour task ready](FSI_PROD_02_48H_TASK.md), numerical work not started. Rigid Poiseuille/Womersley limit and elastic-tube response; temporal/spatial separation including polygon geometry; reference comparison against pinned svFSI configuration/results; qualify default dt-dependent stabilization or explicitly supported alternatives. |
| FSI-PROD-03 | Vascular boundary coupling | Multiple RCR outlets with shared stage and accepted 0D history, consistent flow-pressure Jacobian, retry/restart; external Robin tissue support. Verify circuit limit, interface work and MPI invariance. |
| FSI-PROD-04 | Physiological geometry and robustness | Curved/branched conforming vascular cases, arbitrary planar inlet orientation/profile; backflow behavior, loading/initial stress and material envelope selected from actual case requirements. Validate before recommending use. |
| FSI-PROD-05 | Distributed production qualification | Growing meshes, 1/2/4/8/16/32 ranks and at least two nodes; strong/weak scaling, iterations, max-rank memory, I/O and failure recovery. No inference from single-node small tests. |

Each stage uses one branch and one reviewable PR after its local acceptance;
fix CI in that PR, do not merge main automatically. Use repository build scripts
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
