#pragma once
/** @file Fixed-work smoothers for coupled, indefinite FSI multigrid levels. */
#include "eonsim/interface_patch_pc.hpp"
#include <memory>

namespace eonsim {
struct FsiLevelSmootherOptions {
    std::string kind="vanka"; ///< vanka, chebyshev, or block_chebyshev.
    InterfacePatchOptions patches;
    PetscInt polynomial_degree=3;
    double eigenvalue_ratio=.1;
};
struct FsiLevelSmootherStats {
    PetscInt applications=0,refreshes=0,polynomial_degree=0;
    double eigenvalue_upper=0.;
    InterfacePatchPcStats patches;
};
struct FsiLevelSmoother;
using FsiLevelSmootherHandle=std::shared_ptr<FsiLevelSmoother>;

/** Collective setup on an assembled scalar AIJ with matching row/column
 * ownership. Semantics and trace follow owned row order. Coarse semantics may
 * identify algebraic aggregates; they are not interpreted as physical fields.
 * Vanka includes all fields and the true interface on each level.
 *
 * Chebyshev acts on B^T B, B=D A C, not directly on the indefinite Jacobian.
 * D equilibrates rows; C whitens single columns or same-entity column blocks.
 * A fixed polynomial damps the upper spectral interval [ratio*upper,upper],
 * where upper=1.05*||B||_1*||B||_infinity is a checked bound. Lower-frequency
 * modes are left to coarse correction. Its normal operator is implicit, and
 * polynomial applications use no dot products or eigenvalue estimation.
 * Identity constraints are solved exactly before either action.
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
