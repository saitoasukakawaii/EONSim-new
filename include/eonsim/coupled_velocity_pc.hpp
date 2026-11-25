#pragma once
#include "eonsim/linear_system.hpp"

namespace eonsim {
/** Validate the fixed two-level topology without requiring an assembled matrix.
 * prefix is the KSP options prefix, without a leading '-'. Solver tolerances,
 * overlap, local factors and coarse-solver options remain configurable.
 */
void validate_coupled_velocity_twolevel_options(MPI_Comm comm,const std::string& prefix);

/** Configure a coupled velocity FGMRES with a distributed two-level PCMG.
 * Each MPI owner's active (domain, entity kind, component, mode, space) group
 * supplies one normalized piecewise-constant coarse vector. Exact identity
 * rows have zero interpolation, so prescribed increments are not prolonged.
 * PCMG forms P^T A P from the complete fluid/solid velocity block and refreshes
 * its values when A changes; the graph, ownership and constraints must be fixed.
 * The fine smoother is overlapping ASM/ILU and the coarse solve is GMRES/Jacobi.
 * An entirely identity operator uses one exact Jacobi level. No coordinates,
 * packed xyz ordering, rigid rotations or mesh-independent convergence assumed.
 * owned_semantics follows this KSP's owned row order. Collective on comm.
 */
void configure_coupled_velocity_twolevel(MPI_Comm comm,KSP solver,
                                        const std::vector<DofKey>& owned_semantics);
} // namespace eonsim
