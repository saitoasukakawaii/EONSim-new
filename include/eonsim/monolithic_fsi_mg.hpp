#pragma once
/** @file All-field, constrained Galerkin multigrid for monolithic FSI. */
#include "eonsim/pc_plan.hpp"
#include "eonsim/fsi_level_smoother.hpp"

namespace eonsim {
struct MonolithicFsiMgLevelStats {
    PetscInt rows=0,coarse_rows=0,spectral_modes=0;
    double reproduction_error=0,energy_before=0,energy_after=0;
};
/** Inspection is local. Row counts and transfer audits are globally agreed;
 * fp32_value_bytes counts only local float CSR coefficients (operators and
 * transfers), not retained FP64 setup matrices, factors, indices or vectors.
 */
struct MonolithicFsiMgStats {
    PetscInt levels=0,applications=0,refreshes=0,hierarchy_rebuilds=0,coarse_processes=0;
    /// Actual level residual matvecs and omitted A*0 actions, excluding smoothers/transfers/coarse solves.
    PetscInt level_matvecs=0,zero_start_skips=0;
    bool single_precision=false;
    std::size_t fp32_value_bytes=0;
    std::vector<MonolithicFsiMgLevelStats> transfers;
    std::vector<FsiLevelSmootherStats> smoothers;
};
/// Collective validation before an assembled operator exists.
void validate_monolithic_fsi_mg_options(MPI_Comm comm,const std::string& prefix);
/** Build a full-system hierarchy from the assembled preconditioning matrix.
 * Every Galerkin operator includes fluid velocity, pressure, structural and ALE
 * couplings. Physical candidate modes are retained by local rank-revealing QR;
 * aggregate-local low normal-energy eigenvectors enrich their span. Optional
 * constrained energy descent minimizes ||D_row^-1 J P||_F while preserving
 * P N_coarse=N_fine and fixed rank-revealing interpolation anchor rows. These
 * anchors retain independent spectral columns throughout energy descent.
 * This positive energy does not assert that J is SPD or
 * establish a mesh-independent coarse inf-sup bound.
 *
 * Every noncoarse level applies mixed patches/normal-equation Chebyshev through
 * the FSI level smoother. Vanka uses prefixed monolithic_mg_patch_overlap
 * (default 1) on the fine level and monolithic_mg_coarse_patch_overlap (default
 * 0) on intermediate levels. A coarse entity retains the complete preceding
 * aggregate's physical/spectral basis; zero overlap is a mixed aggregate block,
 * not a scalar or field-separated smoother. Full Galerkin couplings remain in
 * level residuals and coarse transfers. Explicit larger overlap must still fit
 * the unchanged patch size cap; no coupling rows are truncated to satisfy it.
 * Each cycle starts from an exact zero correction; its first residual is the
 * RHS directly, including when presmoothing is disabled. No norm reduction or
 * rank-local convergence branch is introduced to omit that zero matvec.
 * The coarsest full coupled matrix is solved with a
 * bounded KSP, optionally on a reduced communicator through PCTELESCOPE.
 * Identity rows have zero interpolation and receive exact fine corrections.
 * Graph, constraints, ownership and semantic metadata must stay fixed. Numeric
 * refresh updates all Galerkin operators and all level factors; fixed transfer
 * operators retain their setup candidate span by default. A positive prefixed
 * monolithic_mg_spectral_refresh_period automatically rebuilds spectral modes,
 * energy-minimized transfers and level patches after that many refreshes.
 * An unchanged source Mat numeric state retains the existing Galerkin values
 * and coarse factorization, allowing exact local patch-factor cache reuse.
 *
 * Explicit single precision uses row-scaled float CSR coefficients and float
 * sparse arithmetic for level matvecs and restriction/prolongation, plus the
 * smoother's float factors with FP64 refinement. FP64 setup matrices and the
 * coarse solve remain: this is a bandwidth optimization, not a claim that the
 * complete hierarchy uses half the memory. The outer flexible Krylov method
 * and original physical residual remain full precision. Collective on comm.
 */
void configure_monolithic_fsi_mg(MPI_Comm comm,KSP solver,Mat assembled,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,
    const std::vector<unsigned char>& owned_interface,PcSchurUpdates* updates);
bool query_monolithic_fsi_mg_stats(PC pc,MonolithicFsiMgStats& stats);
KSP monolithic_fsi_mg_coarse_solver(PC pc);
} // namespace eonsim
