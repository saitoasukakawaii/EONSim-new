# Newmark mesh-increment diagnostic — 2026-11-09

Source baseline e21e800; unchanged EON solver. Upstream fixed svFSI7bdb74c with explicit independent diagnostic patch; Release GNUFortran16.2/Trilinos13.2, serial/one thread. Configure command, patch, controller sources, logs, executable digest and all consumed raw are bound here. No production adoption.

PICP/PICC give Dn-Do=dt*Yo+dt²*((1/2-beta)*Ao+beta*An) in exact arithmetic. INITIALIZE uses different beta for FSI and mesh. PICC copies FSI kinematics onto structural nodes; diagnostic therefore uses eq(1)%beta on phys_lElas nodes and mesh beta elsewhere, with common af. The scope is this linear FSI, homogeneous fixed-end benchmark only; other materials/boundaries are not qualified. Mesh geometry remains x+Do, tangent and convergence bounds unchanged.

Build20006 and subsequent corrected rebuild exit0. Coarse fresh800-step diagnostic60002 exit0:1600 final equation rows pass, no cap, maximum FS2.5e-11/MS9.7e-11, at most3 iterations. This crosses the combined patch failure at474 but does not establish32-cycle convergence.

Normal-path check33173 completed all five numerical stages with convergence then exited1 on exact saved-norm comparison. Preserve this failed assertion. Separate analysis51236 exit0:20startup+20loaded+10replay field/history pairs pass original node2e-9, relative P1mass1e-8 and nativehistory2e-9. Startup saved norm differs3.944304526105059e-31, so exact norm equivalence is FALSE. Loaded maxnode2.498001805406602e-16, mass4.18510739537612e-14, history8.043999494278253e-14; replay is exact. No tolerance was changed, no original failure report overwritten.

Fine401..540 diagnostic session12782 is active from the separately proven original step400; its final convergence/field evidence is pending. Full fresh trajectories and error budgets are still required. Do not label this diagnostic as adopted or the old failed production as recovered.

Independent struct-decoded normal-path review now executed successfully; it verifies all50 native pairs and consumed raw hashes, preserving original_exact_norm_check_passed=false. New32-cycle coarse diagnostic session39080 started from zero with the same binary3eeacfeeb504ed1fe7f0223a23c004f7605078b7afabd21c2d6fa9f80f63c703; frozen strict audits every~800 completed steps auto-stop on failure. This is a diagnostic, not reference adoption. Current prefix evidence is in long-start; full convergence pending.

Fine-window12782 completed exit0:401..540,280 final equation rows all pass, FS maximum9.3e-12/MS1.3e-11, at most3 iterations and no caps. Full-field/native analysis28747 completed exit0:140pairs, node2.718975760686304e-19, relative P1mass4.964789849856611e-17, history1.570665899587858e-16, exact time/saved norms; original bounds pass. Comparison is against original failed CG and does not by itself qualify the patch; convergence is separately proven. All raw retained and hashed in fine-window.

Fresh zero-state fine600-step diagnostic42045 now running with the same binary, independently checking startup; its final convergence/fields remain pending.
