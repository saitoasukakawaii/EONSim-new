#pragma once
#include "eonsim/linear_system.hpp"
#include <array>

namespace eonsim {
/** Validate the fixed two-level topology without requiring an assembled matrix.
 * prefix is the KSP options prefix, without a leading '-'. Solver tolerances,
 * overlap, local factors and coarse-solver options remain configurable.
 */
void validate_coupled_velocity_twolevel_options(MPI_Comm comm,const std::string& prefix);

/** Configure a coupled velocity PREONLY action with a distributed two-level PCMG.
 * Each MPI owner's active (domain, entity kind, component, mode, space) group
 * supplies one normalized piecewise-constant coarse vector. Exact identity
 * rows have zero interpolation, so prescribed increments are not prolonged.
 * PCMG forms P^T A P from the complete fluid/solid velocity block and refreshes
 * its values when A changes; the graph, ownership and constraints must be fixed.
 * The fine smoother is overlapping ASM/ILU and the coarse solve is GMRES/Jacobi.
 * Its tolerance-dependent coarse action requires a flexible outer FSI solve.
 * Explicit FGMRES options restore the retained rtol=1e-4, max_it=20 defaults;
 * PREONLY applies the PC once and does not use those stopping parameters.
 * An entirely identity operator uses one exact Jacobi level. With rigid_modes,
 * solid P1 vertex groups also contain their three reference-coordinate rotation
 * candidates, orthogonalized locally against the translations and each other;
 * dependent candidates are dropped. Fluid constants and body scalars are kept.
 * Coordinates are owned row metadata, never an assumption of packed xyz order.
 * The fixed reference basis does not assert mesh-independent convergence.
 * owned_semantics follows this KSP's owned row order. Collective on comm.
 */
void configure_coupled_velocity_twolevel(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates={},bool rigid_modes=false,
    PetscInt aggregate_nodes=0);
/** aggregate_nodes=0 retains owner/domain coarse modes. A positive value forms
 * graph-connected owner-local aggregates of at most that many semantic nodes.
 * Each aggregate retains its independent component translations and requested
 * solid rotations, dropping dependent columns before Galerkin projection. The
 * distributed aggregate operator uses a GAMG V-cycle, so its coarse dimension
 * need not be limited to a handful of modes per MPI rank. Neither the fine
 * unknown numbering nor cross-domain matrix couplings are changed. */

/// Validate field-aware PCMG options before an assembled operator is available.
void validate_coupled_velocity_field_amg_options(MPI_Comm comm,const std::string& prefix);

/** Build every velocity AMG transfer from propagated physical near modes.
 * Owner-local graph aggregates retain whole semantic nodes on the fine grid,
 * and whole preceding aggregates on later grids. Local rank-revealing QR
 * removes dependent candidate columns; P^T N supplies the candidate data on
 * the next grid. Thus every level retains independent fluid/solid translations,
 * optional reference rotations, body scalars, and their coupled combinations.
 * All Galerkin operators use the complete, generally nonsymmetric velocity
 * matrix. No packed xyz ordering or exact nullspace is assumed. Identity rows
 * have zero interpolation and are solved by the fine smoother.
 * Prefixed field_amg_coarse_limit (default 64) and field_amg_max_levels
 * (default 10) bound setup. Coarsening stops also when no dimension is reduced.
 * Interpolation is fixed for the solver session; PCMG refreshes every numerical
 * Galerkin operator as the current Jacobian changes. Geometry, constraints and
 * ownership must therefore remain fixed. Coarse solves are bounded GMRES/ASM,
 * requiring an outer flexible Krylov method. This mechanism alone does not
 * establish mesh-independent convergence. Collective on comm; P1 vertex and
 * scalar body velocity semantics only.
 */
void configure_coupled_velocity_field_amg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates={},bool rigid_modes=false,
    PetscInt aggregate_nodes=16);

/// Validate an optional scalar-AIJ GAMG hierarchy and flexible response options.
void validate_coupled_velocity_gamg_options(MPI_Comm comm,const std::string& prefix);

/** Full fluid/solid velocity GAMG, with one scalar near-nullspace vector.
 * The vector is constant on every active vertex component and body scalar, zero
 * on exact identity rows, and normalized globally. Only vertex P1 and body
 * semantics are supported; no uniform three-component block layout is assumed.
 * rigid_modes must be false: scalar aggregation cannot safely represent several
 * separate Cartesian/rotation modes when an aggregate contains too few scalar
 * rows. The rotation-enriched twolevel method is the supported vector option.
 * Default PREONLY applies one multiplicative V-cycle, using ASM/ILU smoothers
 * and GMRES/Jacobi on the coarse grid. Explicit FGMRES is allowed. PETSc owns
 * and reuses interpolation, while refreshing all Galerkin numerical operators;
 * -pc_gamg_reuse_interpolation false rebuilds it after large coefficient changes.
 * The near mode does not assert that the dynamic coupled matrix is singular,
 * and this scalar hierarchy does not promise elasticity-optimal convergence.
 * An all-identity matrix uses PREONLY/Jacobi without constructing an empty AMG.
 * The caller must require a flexible outer solve. Collective on comm.
 */
void configure_coupled_velocity_gamg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates={},bool rigid_modes=false);

/// Scalar-AIJ BoomerAMG on the complete velocity block, using one fixed cycle.
/// Requires PETSc built with hypre. No uniform xyz packing or elasticity modes
/// are assumed. Prefix options retain hypre coarsening/smoothing controls.
void validate_coupled_velocity_boomeramg_options(MPI_Comm comm,const std::string& prefix);
void configure_coupled_velocity_boomeramg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics);
} // namespace eonsim
