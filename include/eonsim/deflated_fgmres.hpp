#pragma once
/** @file Bounded spectral recycling and two-level right deflation for FGMRES. */
#include "eonsim/linear_system.hpp"

namespace eonsim {
struct DeflatedFgmresStats {
    PetscInt capacity=0,vectors=0,refreshes=0,projections=0,applications=0;
    PetscInt projected_applications=0,candidates=0,rank_drops=0,spectral_updates=0;
    PetscInt operator_actions=0,projection_reductions=0,failure_reductions=0;
    double smallest_retained_response=0,largest_retained_response=0;
};
/** Install after the original PC recipe has been configured. Retains that PC
 * in an owned PREONLY child without changing its options prefix. The outer
 * operator, RHS, stopping test and flexible GMRES implementation stay intact.
 * Repeated installation with the same capacity is harmless. Collective.
 *
 * Before every linear solve prepare_deflated_fgmres recomputes AU=C with the
 * CURRENT operator, using paired twice-reorthogonalized QR. The shell applies
 *   (I-U C^T A) M_j^-1 (I-C C^T) + U C^T,
 * where C^T C=I and the underlying PC M_j may vary between applications.
 * Thus a residual perpendicular to C is propagated by (I-C C^T) A M_j^-1,
 * with its correction lifted consistently to the original variable space.
 * No projected/regularized operator is substituted for the physical A.
 *
 * At successful completion, a bounded pool of actual preconditioned Krylov
 * directions and previous recycle vectors is compressed using an image QR
 * followed by a small SVD. Small nonzero singular-response directions are
 * retained. This is deflated FGMRES, not harmonic-Ritz GCRO-DR. At most
 * 2*capacity search samples are collected; no full Arnoldi basis is stored.
 */
void configure_deflated_fgmres(KSP solver,PetscInt capacity);
/// Zeroes x, refreshes images, seeds U*C^T*b and enables sample collection.
void prepare_deflated_fgmres(KSP solver,Vec rhs,Vec x);
/// Call only after the original-operator residual of a successful solve passed.
void complete_deflated_fgmres(KSP solver,Vec solution);
/// Reset counters at a nonlinear solve boundary, preserving the recycle space.
void reset_deflated_fgmres_stats(PC pc);
bool query_deflated_fgmres_stats(PC pc,DeflatedFgmresStats& stats);
/// Borrowed original PC's holder for inspection; does not set it up.
KSP deflated_fgmres_bulk_solver(PC pc);
} // namespace eonsim
