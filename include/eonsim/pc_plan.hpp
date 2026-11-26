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
    bool gamg_velocity=false, boomeramg_velocity=false, rigid_velocity_modes=false;
    bool field_amg_velocity=false;
    bool monolithic_mg=false;
    std::vector<DofKey> monolithic_semantics;
    std::vector<std::array<double,3>> monolithic_coordinates;
    std::vector<unsigned char> monolithic_interface;
    int pressure_schur=0; ///< 0=native/nodal; 3=LSC, 4=BFBt, 5=physical PCD, 6=structural compliance.
    std::vector<std::vector<PetscInt>> pressure_fluid_groups,pressure_structure_groups; ///< Root rows.
    bool interface_patch=false,patch_single_precision=false;
    PetscInt patch_overlap=1,patch_maximum_size=256,patch_refinement_steps=3;
    double patch_refinement_tolerance=1e-10,patch_damping=1.;
    std::vector<DofKey> patch_semantics;
    std::vector<unsigned char> patch_interface;
    // Optional outer port Schur action. The sole child describes the reindexed
    // bulk matrix; boundary-pressure rows retain their full-matrix provenance.
    bool rcr_ports=false;
    std::vector<PetscInt> rcr_port_rows;
    PetscInt velocity_aggregate_nodes=0; ///< Positive selects graph aggregates plus a GAMG coarse solve.
    // Added-mass retains full fluid saddle-point blocks with an approximate inverse action.
    // fluid_response defaults to PREONLY; explicit FGMRES keeps its bounded budget.
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
    std::vector<std::array<double,3>> velocity_reference_coordinates; ///< Same owned row order; reference geometry only.
};
/// Collective preparation; rejects unsupported recipe/layout consistently before IS creation.
PcBlock make_pc_plan(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe);
/// Collective configuration-only validation, including an exactly converged initial state.
void validate_pc_plan_options(MPI_Comm comm,KSP solver,const PcBlock& plan);
/** Numeric state for the user Schur matrices. The plan itself still owns no PETSc
 * handles. Keep this object alive for the configured KSP and refresh after every
 * successful, constrained Jacobian assembly by default. Adaptive PC reuse may
 * retain these USER matrices with the rest of P until its next chosen numerical
 * refresh; the root Jacobian still changes on every Newton correction. The
 * matrix graph must stay fixed.
 */
struct PcSchurUpdates {
    std::vector<std::function<void(Mat)>> refreshers;
    void refresh(Mat matrix) const { for(const auto& update:refreshers) update(matrix); }
};
/// Collective, assembled AIJ; creates fresh IS/PC objects, never changes physical fields or root numbering.
/// Nodal pressure/structure recipes require a fresh updates object and numeric refresh.
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan,PcSchurUpdates* updates=nullptr);
} // namespace eonsim
