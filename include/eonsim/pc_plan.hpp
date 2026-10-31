#pragma once
#include "eonsim/linear_system.hpp"
namespace eonsim {
/** Immutable owned-only indices. parent_rows address the immediate parent Mat;
 * root_rows preserve provenance. begin/global describe this node's submatrix.
 * No borrowed PETSc handles: a plan can outlive a solve's SNES/PC.
 */
struct PcBlock {
    std::string name;
    bool schur=false;
    PetscInt begin=0,global=0;
    std::vector<PetscInt> parent_rows,root_rows;
    std::vector<PcBlock> children;
};
/// Collective preparation; rejects unsupported recipe/layout consistently before IS creation.
PcBlock make_pc_plan(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe);
/// Collective configuration-only validation, including an exactly converged initial state.
void validate_pc_plan_options(MPI_Comm comm,KSP solver,const PcBlock& plan);
/// Collective, assembled AIJ; creates fresh IS/PC objects, never changes physical fields or root numbering.
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan);
} // namespace eonsim
