# Strict-stop derived diagnostic: 100-step relative convergence restored

Isolated build62612 completed0. Session26910 ran coarse N800100 steps from zero
with unchanged case, time step, relative tolerances and iteration caps, for
meshCG/FSILS, GMRES/FSILS and GMRES/ILUT. Only PIC.f's saved-initial-norm absolute
acceptance branch was disabled in this explicitly derived binary.

All three runs pass200 final equation rows with zero failures; maxMS relative
ratios3.8e-11,7.3e-11,2.6e-11 respectively. The corresponding unmodified runs
failed all100 MS steps. This supports the diagnosed stop-branch cause. Execution
is not a result comparison to a converged baseline and does not prove long-run
agreement, reference qualification or repair of the separate fineN800 residual
floor. No production adoption. Original fixed source/binaries/failed runs remain.

The derivative is explicitly labeled in input metadata and its patch/base/binary
hashes are frozen. Do not pass this as the unmodified pinned reference. Full
raw logs, every saved state and checkpoint remain local for further review.
