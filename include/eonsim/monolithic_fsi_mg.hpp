#pragma once
/** @file All-field, constrained Galerkin multigrid for monolithic FSI. */
#include "eonsim/pc_plan.hpp"
#include "eonsim/fsi_level_smoother.hpp"

namespace eonsim {
struct MonolithicFsiMgLevelStats {
    PetscInt rows=0,coarse_rows=0,spectral_modes=0;
    double reproduction_error=0,energy_before=0,energy_after=0;
    /// Fine-level local pairs, audited on FP64 setup before native quantization;
    /// these are not a global coarse inf-sup bound or an FP32 action guarantee.
    PetscInt pressure_supremizer_modes=0,pressure_paired_aggregates=0;
    double pressure_pair_min_singular=0,pressure_pair_relative_change=0;
};
/** Inspection is local. Row counts and transfer audits are globally agreed;
 * fp32_value_bytes counts local float operator/transfer coefficients and native
 * patch/lifting coefficients, not factors, indices or PETSc FP64 vectors.
 */
struct MonolithicFsiMgStats {
    PetscInt levels=0,applications=0,refreshes=0,hierarchy_rebuilds=0,coarse_processes=0;
    /// Rejected near-identity coarsening (zero when the ratio guard was not needed).
    PetscInt weak_coarsening_stop_rows=0,weak_coarsening_proposed_rows=0;
    /// Level operator matvecs (including K-cycle directions/audits), and omitted A*0 actions; excludes smoothers/transfers/coarse solves.
    PetscInt level_matvecs=0,zero_start_skips=0,coarse_revisits=0;
    /// Lifetime cumulative work, preserved by numeric hierarchy rebuilds.
    PetscInt coarse_solves=0,coarse_iterations=0,smoother_applications=0;
    PetscInt coarse_krylov_directions=0,coarse_krylov_rank_drops=0,coarse_krylov_rejections=0;
    /// VecDot/VecNorm reduction requests, not measured MPI packets or latency events (norms may be cached).
    PetscInt coarse_krylov_reductions=0;
    /// Worst explicitly recomputed row-equilibrated coarse residual ratio returned by a K-cycle projection.
    double coarse_krylov_max_residual_ratio=0.;
    bool single_precision=false,native_fp32=false,field_scaling=false,fsi_candidates=false,w_cycle=false,k_cycle=false;
    bool pressure_supremizers=false;
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
 * pressure_supremizers requires fsi_candidates and spectral_modes>0. On the semantic fine level,
 * at most min(2,spectral_modes) aggregate-local velocity responses replace
 * spectral enrichment slots. A positive diagonal velocity-energy proxy and
 * a bounded QR projection apply the actual discrete B^T to pressure modes;
 * the selected responses address pressure coupling missing from the existing
 * velocity span. B uses the actual Galerkin test weights W when scaled.
 * The paired pressure and response columns remain fixed during energy
 * descent, and their coupling is audited against the formed FP64 coarse
 * matrix. Native transfer quantization remains subject to the independent
 * original-operator residual gate; it has no exact-pairing guarantee.
 * Reported singular values belong only to these selected, row-normalized
 * local paired blocks. Other pressure directions, later mixed scalar levels,
 * and a global inf-sup bound are not certified. Numeric changes rebuild this
 * enrichment. Aggregate, spectral-slot, smoothing and coarse-solve budgets
 * are unchanged; no convergence tolerance is weakened.
 * With fsi_candidates the default max_coarse_ratio is 0.8 (otherwise 1): reject
 * a proposed level that reduces too few rows and solve its parent as coarsest.
 * This is a hierarchy work bound, independent of physical/Krylov tolerances.
 * cycle=w revisits each noncoarsest coarse level with its current residual.
 * cycle=k instead minimizes the row-equilibrated full coarse residual in at
 * most two recursively preconditioned Arnoldi directions. Twice modified
 * Gram-Schmidt forms a small QR without normal equations. Numerically dependent
 * directions are dropped relative to the precision of the level action; an
 * explicitly recomputed finite residual increase selects the zero correction
 * from this subspace. Nonfinite actions retain the PC failure protocol.
 * The coarse equations, 36-column physical candidate container, and external
 * residual tolerances are unchanged. Flexible outer Krylov is required.
 * With L levels the maximum coarsest solve count is 2^(L-2) per nontrivial
 * application (one for L<=2), not an unbounded inner convergence loop. This
 * costs additional coarse matvecs, vector storage and dot/norm reductions;
 * actual cumulative solves, iterations, smoothing and direction/reduction-request work
 * are exposed in the stats. It is not a mesh-independent complexity proof.
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
 * transient setup; unchanged generations reuse compact coefficients. Before a
 * native rebuild, invalidated compact storage is released while fine metadata
 * remains available for failure recovery. A failed replacement is unusable and
 * can be reconstructed by a later refresh; no old factor is silently reused.
 * Native
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
