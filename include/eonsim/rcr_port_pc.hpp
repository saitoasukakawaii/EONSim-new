#pragma once
/** @file RCR port Schur correction around an existing bulk preconditioner. */
#include "eonsim/pc_plan.hpp"

namespace eonsim {
/** Cumulative work for one shell's lifetime. Port reductions exclude the
 * communications performed internally by the selected bulk preconditioner.
 */
struct RcrPortPcStats {
    PetscInt ports=0,rebuilds=0,applications=0,response_solves=0;
    PetscInt setup_reductions=0,apply_reductions=0;
};
/** Collective; full is the assembled, constrained Jacobian with blocks
 * [A U; V D]. Only owned full-matrix port rows are supplied. The remaining
 * owned rows keep their order in A. configure_bulk is called once with an
 * owned PREONLY KSP, A and its persistent numeric-update registry; its prefix
 * is the containing KSP prefix followed by rcr_bulk_.
 *
 * The shell caches Y=H U and S=D-V Y and applies z=H r_bulk,
 * q=S^-1(r_port-V z), x_bulk=z-Y q. In the ideal velocity-only fixed-port
 * block before row-only constraints, V=-U^T: eliminating ports gives the
 * usual Sherman--Morrison (one port) or Woodbury correction for
 * A+U D^-1 U^T. The implementation always extracts general assembled V,
 * retaining ALE derivatives and row constraints. Exact block-inverse identities require a fixed linear
 * H; tolerance-dependent inner/coarse actions are approximate responses and
 * require an outer FGMRES solve.
 *
 * updates must outlive use of the configured KSP. Its registered refresher
 * updates A/U/V/D, bulk factors and Y/S together. PCApply/PCSetUp never infer
 * numerical freshness from the changing full Jacobian: adaptive PC reuse may
 * deliberately retain the previous complete generation. The full matrix
 * identity, graph, ownership and port membership must remain fixed.
 */
void configure_rcr_port_pc(MPI_Comm comm,KSP solver,Mat full,
    const std::vector<PetscInt>& local_port_rows,
    const std::function<void(KSP,Mat,PcSchurUpdates*)>& configure_bulk,
    PcSchurUpdates* updates);
/// Local inspection only; false means this is not an EONSim RCR port shell.
bool query_rcr_port_pc_stats(PC pc,RcrPortPcStats& stats);
/// Borrowed child, or nullptr for a different PC; does not set up the child.
KSP rcr_port_bulk_solver(PC pc);
} // namespace eonsim
