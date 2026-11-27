#pragma once
/** @file Fixed-work smoothers for coupled, indefinite FSI multigrid levels. */
#include "eonsim/interface_patch_pc.hpp"
#include <memory>

namespace eonsim {
struct FsiLevelSmootherOptions {
    std::string kind="vanka"; ///< vanka[_multiplicative|_colored], braess_sarazin, or [block_]chebyshev.
    InterfacePatchOptions patches;
    PetscInt polynomial_degree=3;
    double eigenvalue_ratio=.1;
    /// H=alpha*blockdiag(F); the default damps the primal block inverse.
    double braess_alpha=2.;
    PetscInt schur_iterations=3;
};
struct FsiLevelSmootherStats {
    PetscInt applications=0,refreshes=0,polynomial_degree=0;
    double eigenvalue_upper=0.;
    PetscInt primal_rows=0,pressure_rows=0,schur_budget=0,schur_iterations=0,schur_applications=0,zero_lift_skips=0;
    InterfacePatchPcStats patches;
};
struct FsiLevelSmoother;
using FsiLevelSmootherHandle=std::shared_ptr<FsiLevelSmoother>;

/** Collective setup on an assembled scalar AIJ with matching row/column
 * ownership. Semantics and trace follow owned row order. Coarse semantics may
 * identify algebraic aggregates. Braess-Sarazin requires preserved pressure
 * quantity tags on every level; all other active fields are primal.
 * Vanka includes all fields and the true interface on each level.
 *
 * Chebyshev acts on B^T B, B=D A C, not directly on the indefinite Jacobian.
 * D equilibrates rows; C whitens single columns or same-entity column blocks.
 * A fixed polynomial damps the upper spectral interval [ratio*upper,upper],
 * where upper=1.05*||B||_1*||B||_infinity is a checked bound. Lower-frequency
 * modes are left to coarse correction. Its normal operator is implicit, and
 * polynomial applications use no dot products or eigenvalue estimation.
 * Identity constraints are solved exactly before either action.
 *
 * Braess-Sarazin uses H=alpha*blockdiag(F), with every owned entity's full
 * nonpressure block (fluid, structure and ALE) inverted using scaled pivoting.
 * It forms S=C-D H^-1 G on the distributed pressure partition, solves it with
 * a fixed-budget GMRES/Jacobi action, and recovers du=H^-1(ru-G dp). No sign
 * convention, pressure pin, shift, global field gather or serial direct
 * coarse solve is introduced. Structural compliance enters D H^-1 G through
 * the retained primal blocks; coupling between different blocks remains an
 * approximation. The outer solver must be flexible and check true residuals.
 */
FsiLevelSmootherHandle make_fsi_level_smoother(MPI_Comm comm,Mat matrix,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<unsigned char>& owned_trace,
    const FsiLevelSmootherOptions& options);
/// Collective explicit numeric refresh; matrix identity/graph/constraints stay fixed.
void refresh_fsi_level_smoother(const FsiLevelSmootherHandle& smoother,Mat matrix);
/// Native FP32 Vanka only: release all borrowed/owned FP64 setup matrices.
void release_native_fsi_smoother_setup(const FsiLevelSmootherHandle& smoother);
/** Applies a zero-initial-guess correction. Expected local numeric failure
 * returns PETSC_ERR_NOT_CONVERGED only after all scheduled communication has
 * completed and borrowed arrays are restored. The caller must complete its
 * remaining collective schedule and propagate the failure to the outer PC.
 */
PetscErrorCode apply_fsi_level_smoother(const FsiLevelSmootherHandle& smoother,Vec rhs,Vec correction);
/// Rank-local diagnostics; no hidden collective.
FsiLevelSmootherStats query_fsi_level_smoother_stats(const FsiLevelSmootherHandle& smoother);
} // namespace eonsim
