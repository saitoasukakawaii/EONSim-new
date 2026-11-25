#pragma once
#include "eonsim/linear_system.hpp"
#include <functional>
namespace eonsim {
/** Immutable owned-only indices. parent_rows address the immediate parent Mat;
 * root_rows preserve provenance. begin/global describe this node's submatrix.
 * No borrowed PETSc handles: a plan can outlive a solve's SNES/PC.
 */
struct PcBlock {
    std::string name;
    bool schur=false, nodal_schur=false, coupled_velocity=false;
    PetscInt begin=0,global=0;
    std::vector<PetscInt> parent_rows,root_rows;
    std::vector<PcBlock> children;
    // Owned velocity-submatrix numbering, grouped by canonical entity/mode/space.
    std::vector<std::vector<PetscInt>> velocity_groups;
};
/// Collective preparation; rejects unsupported recipe/layout consistently before IS creation.
PcBlock make_pc_plan(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe);
/// Collective configuration-only validation, including an exactly converged initial state.
void validate_pc_plan_options(MPI_Comm comm,KSP solver,const PcBlock& plan);
/** Numeric state for the user Schur matrices. The plan itself still owns no PETSc
 * handles. Keep this object alive for the configured KSP and refresh after every
 * successful, constrained Jacobian assembly; the matrix graph must stay fixed.
 */
struct PcSchurUpdates {
    std::vector<std::function<void(Mat)>> refreshers;
    void refresh(Mat matrix) const { for(const auto& update:refreshers) update(matrix); }
};
/// Collective, assembled AIJ; creates fresh IS/PC objects, never changes physical fields or root numbering.
/// Nodal recipes require a fresh updates object and subsequent numeric refresh.
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan,PcSchurUpdates* updates=nullptr);
} // namespace eonsim
