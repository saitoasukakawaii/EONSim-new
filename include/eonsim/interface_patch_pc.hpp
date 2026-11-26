#pragma once
/** @file Interface-centred mixed patches and optional FP32 local factors. */
#include "eonsim/pc_plan.hpp"

namespace eonsim {
struct InterfacePatchOptions {
    bool single_precision=false;
    PetscInt overlap=1,maximum_size=256,refinement_steps=3;
    double refinement_tolerance=1e-10,damping=1.;
};
/** Counters are rank-local; no hidden collective is performed by the query.
 * factor_bytes counts dense LU values only, excluding sparse patch matrices,
 * index maps, vectors, and the existing full-precision bulk preconditioner.
 */
struct InterfacePatchPcStats {
    PetscInt patches=0,largest_patch=0,rebuilds=0,applications=0;
    PetscInt fp32_patches=0,fp64_patches=0,setup_fallbacks=0,apply_fallbacks=0,refinements=0;
    std::size_t factor_bytes=0;
};
/// Collective validation, also usable before an exactly converged solve.
void validate_interface_patch_options(MPI_Comm comm,const std::string& prefix,
                                     const InterfacePatchOptions& options);
/** Wrap an existing semantic PREONLY action H with the residual correction
 * x=H*r; x+=damping*sum_i R_i^T W_i A_i^-1 R_i*(r-J*x).
 * Patches start at distinct owned trace vertices and grow through the assembled
 * graph by options.overlap layers. They contain the actual constrained mixed
 * fluid/structure/pressure/ALE entries, including off-rank rows. Identity rows
 * and boundary-port scalars are excluded; no pressure pin or diagonal shift is
 * introduced. W_i is reciprocal global patch multiplicity. Every patch must
 * fit maximum_size and have a nonsingular local matrix.
 *
 * owned_interface and owned_semantics follow full's owned row ordering. The
 * trace marker comes from the physical layout, never algebraic adjacency.
 * configure_bulk receives a PREONLY KSP with prefix interface_bulk_ appended
 * to the parent prefix and a persistent update registry. Numeric factors and
 * nested USER matrices refresh only through updates. The residual uses the
 * current full-precision J even when adaptive reuse retains older factors.
 * Thus the full J graph/identity/ownership and trace/constraint sets stay fixed.
 *
 * single_precision stores scaled pivoted LU in float, applies FP64 residual
 * refinement, and explicitly falls back to FP64 LU if a float factor or its
 * componentwise backward-error check fails. All root vectors and J stay FP64.
 * This changes only local patch factors, not PETSc's global scalar precision.
 * The flexible outer solve must still check the original physical residual.
 */
void configure_interface_patch_pc(MPI_Comm comm,KSP solver,Mat full,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<unsigned char>& owned_interface,
    const InterfacePatchOptions& options,
    const std::function<void(KSP,Mat,PcSchurUpdates*)>& configure_bulk,
    PcSchurUpdates* updates);
/// Local inspection only; false/nullptr means this is a different PC type.
bool query_interface_patch_pc_stats(PC pc,InterfacePatchPcStats& stats);
KSP interface_patch_bulk_solver(PC pc);
} // namespace eonsim
