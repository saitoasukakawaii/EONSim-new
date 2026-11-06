# Production FSI milestones

2026-11-06. User goal: advance EONSim-new toward production FSI. Baseline
`dd27eef` includes PR #36. Production readiness is an evidence claim for a defined
problem class, hardware and operating envelope, not a single global feature flag.

| Stage | Deliverable | Acceptance / current status |
|---|---|---|
| FSI-PROD-01 | Circular volume-flow inlet and conforming 3D solid-wall tube | Locally accepted on `codex/fsi-production-tube` (PR/CI pending); independent mesh topology/volume checks; actual wall response; flux, interface, positive geometry; BE/BDF2/alpha; 1/2/4 rank; restart and rejection. This is an enabling benchmark, not physiological validation. |
| FSI-PROD-02 | Quantitative tube qualification | Rigid Poiseuille/Womersley limit and elastic-tube response; temporal/spatial separation including polygon geometry; reference comparison against pinned svFSI configuration/results; qualify default dt-dependent stabilization or explicitly supported alternatives. |
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
