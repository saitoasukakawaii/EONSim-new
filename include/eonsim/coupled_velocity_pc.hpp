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
    const std::vector<std::array<double,3>>& owned_coordinates={},bool rigid_modes=false);

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
} // namespace eonsim
