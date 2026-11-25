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
    bool schur=false, nodal_schur=false, coupled_velocity=false, twolevel_velocity=false;
    // Added-mass topology retains the complete fluid saddle-point Schur operator.
    // structure_response selects the historical iterative solve preconditioned by A11.
    bool added_mass_schur=false, fluid_response=false, structure_response=false;
    // USER structural P uses local mixed fluid inverses; its default action is PREONLY.
    bool nodal_structure_schur=false;
    PetscInt begin=0,global=0;
    std::vector<PetscInt> parent_rows,root_rows;
    std::vector<PcBlock> children;
    // Owned velocity-submatrix numbering, grouped by canonical entity/mode/space.
    std::vector<std::vector<PetscInt>> velocity_groups;
    // Owned full-fluid numbering: active velocity and pressure of one entity/mode/space.
    // RCR boundary pressures have separate identities and form scalar groups.
    std::vector<std::vector<PetscInt>> fluid_groups;
    std::vector<DofKey> velocity_semantics; ///< Leaf row order, for the coupled coarse space.
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
/// Nodal pressure/structure recipes require a fresh updates object and numeric refresh.
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan,PcSchurUpdates* updates=nullptr);
} // namespace eonsim
