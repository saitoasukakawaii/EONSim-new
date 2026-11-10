# Coarse reference stopping-condition diagnosis

Fresh zero-state100-step runs with meshCG/FSILS, GMRES/FSILS and GMRES/ILUT
all completed solver0 but all100 MS rows failed original strict relative
convergence. Session4145 completed0 as a diagnostic, not a qualification.
Thus simply changing existing linear options does not bypass the initial-norm
absolute branch. Original fixed upstream source is unchanged.

A separate source copy contains exactly one numerical-source change: PIC.f
sets the initial-norm absolute acceptance flagfalse. Equations, relative
limits and iteration cap are unchanged; the external auditor still rejects cap
or nonconverged exit. Patch and base commit are frozen. This is an explicitly
derived diagnostic executable, NOT the unmodified pinned reference and NOT
adopted for production. It will test causality of the identified stop branch.

Initial configure used the repository superbuild root, which ignored direct
solver flags; that configuration/log is preserved and never built. Corrected
configure uses source/Code and existing Trilinos installation. Buildsession62612
is active at capture, two compiler workers. No binary or numerical result yet.
The three old production failures and all original source/binaries remain intact.
