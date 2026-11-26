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
 * fp32_value_bytes counts local float operator/transfer coefficients and native
 * patch/lifting coefficients, not factors, indices or PETSc FP64 vectors.
 */
struct MonolithicFsiMgStats {
    PetscInt levels=0,applications=0,refreshes=0,hierarchy_rebuilds=0,coarse_processes=0;
    /// Rejected near-identity coarsening (zero when the ratio guard was not needed).
    PetscInt weak_coarsening_stop_rows=0,weak_coarsening_proposed_rows=0;
    /// Actual level residual matvecs and omitted A*0 actions, excluding smoothers/transfers/coarse solves.
    PetscInt level_matvecs=0,zero_start_skips=0,coarse_revisits=0;
    bool single_precision=false,native_fp32=false,field_scaling=false,fsi_candidates=false,w_cycle=false;
    std::size_t fp32_value_bytes=0;
    /// Additional level/transfer coefficient storage, excluding original outer P, indices and PETSc vectors.
    std::size_t retained_fp64_operator_bytes=0,released_fp64_operator_bytes=0;
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
 * Explicit field_scaling builds A_s=L A R from globally agreed semantic-field
 * row/column maxima. The PC action is R M_s^-1 L; the outer Jacobian/residual
 * are unchanged. Physical candidates are transformed by R^-1. Changes to the
 * source rebuild these scales and their hierarchy. The first restriction is
 * P^T W, W=R L^-1, so its coarse matrix is (R P)^T A (R P): independent row and
 * column equilibration preserves the original physical Galerkin test space.
 * W is applied before either FP64 or native FP32 restriction; only its diagonal
 * vector remains after setup, not an additional FP64 fine operator.
 * fsi_candidates additionally preserves pressure coordinate modes and
 * interface-local coherent translation, rotation and pressure modes. Fluid
 * dilation x/3 and directional quadratic velocities e_i*x_i^2/2 pair the
 * pressure modes 1,x_i with nonzero velocity divergence in normalized reference
 * coordinates. Constraints still remove candidate values on identity rows;
 * these are near modes, not a new exact nullspace or a coarse inf-sup proof.
 * With fsi_candidates the default max_coarse_ratio is 0.8 (otherwise 1): reject
 * a proposed level that reduces too few rows and solve its parent as coarsest.
 * This is a hierarchy work bound, independent of physical/Krylov tolerances.
 * cycle=w revisits each noncoarsest coarse level with its current residual.
 * adaptive_patches keeps every entity core covered and grows overlap only on
 * the true interface or rows whose inter-entity absolute coupling fraction
 * reaches patch_strength. Numeric changes rebuild this selection.
 *
 * Explicit single precision uses row-scaled float CSR coefficients and float
 * sparse arithmetic for level matvecs and restriction/prolongation, plus the
 * smoother's float factors with FP64 refinement. FP64 setup matrices and the
 * coarse solve remain: this is a bandwidth optimization, not a claim that the
 * complete hierarchy uses half the memory. native_fp32 (Vanka only) additionally
 * releases noncoarse FP64 setup operators/transfers, patch submatrices and
 * Galerkin product references. Native patch residual refinement uses retained
 * equilibrated FP32 coefficients; unrepresentable FP32 factors fail explicitly,
 * with no hidden FP64 fallback. The original outer P and coarsest solve remain
 * FP64, as do PETSc vectors/communication. Actual numeric changes rebuild the
 * transient setup; unchanged generations reuse compact coefficients. Native
 * storage reduces retained coefficient memory, not peak setup memory. The
 * outer flexible Krylov method and original physical residual remain full
 * precision. Collective on comm.
 */
void configure_monolithic_fsi_mg(MPI_Comm comm,KSP solver,Mat assembled,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,
    const std::vector<unsigned char>& owned_interface,PcSchurUpdates* updates);
bool query_monolithic_fsi_mg_stats(PC pc,MonolithicFsiMgStats& stats);
KSP monolithic_fsi_mg_coarse_solver(PC pc);
} // namespace eonsim
