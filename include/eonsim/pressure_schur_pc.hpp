#pragma once
#include "eonsim/linear_system.hpp"
#include <memory>

namespace eonsim {
enum class PressureSchurKind { lsc, bfbt, pcd, added_mass };

/** Immutable owned nodal momentum groups in root numbering. Together the two
 * lists partition the velocity rows passed to make_pressure_schur_state.
 * A group contains one to three active components of one physical node (or a
 * scalar rigid body). Interface aliases belong to the structural group once.
 */
struct PressureComplianceLayout {
    std::vector<std::vector<PetscInt>> fluid_groups,structure_groups;
};

/** Physical PCD operators composed on the root Jacobian. Each is an assembled
 * full-root-size AIJ matrix with the root's ownership and pressure-only entries.
 * mass is the positive lumped pressure mass, laplace the pressure Laplacian,
 * and transport the current pressure reaction/convection/diffusion operator.
 * Their producer owns pressure auxiliary boundary/gauge treatment and updates
 * ALE geometry, advection and time coefficients with the Jacobian. Composition
 * retains the matrices; no physics or geometry is inferred by this module.
 */
inline constexpr const char* pressure_pcd_mass_key="eonsim_pcd_mass";
inline constexpr const char* pressure_pcd_laplace_key="eonsim_pcd_laplace";
inline constexpr const char* pressure_pcd_transport_key="eonsim_pcd_transport";
/// Optional complete triple used by the velocity-mass PCD enhancement.
inline constexpr const char* pressure_pcd_velocity_mass_key="eonsim_pcd_velocity_mass";
inline constexpr const char* pressure_pcd_viscosity_key="eonsim_pcd_viscosity";
inline constexpr const char* pressure_pcd_boundary_key="eonsim_pcd_boundary";

/** Propagate optional composed PCD operators to a compact root submatrix.
 * Extracts child_rows in its exact distributed IS order, reusing the child
 * compositions and their sparsity when present. Call after each root update,
 * before building or refreshing the child's pressure preconditioner.
 * No auxiliaries is a no-op; incomplete base/enhancement triples fail collectively.
 */
void propagate_pressure_auxiliaries(Mat root,Mat child,IS child_rows);

struct PressureSchurState;
using PressureSchurHandle=std::shared_ptr<PressureSchurState>;

/// Configuration-only validation, including exactly converged initial states.
void validate_pressure_schur_options(MPI_Comm comm,const std::string& pressure_prefix);

/** Collective root-row extraction, preserving C and B independently.
 * For S=D-C A^-1 B, LSC uses W=I, BFBt uses W=|diag(A)|^-1, and both form
 * L=-C W B+s D, H=-C W A W B+s^2 D, s=||W A||_infinity.
 * The action L^-1 H L^-1 is a scaled stabilized commutator. It reduces to
 * signed LSC/BFBt for D=0, and is exact when W A=s I. It is not a PCD proxy.
 * Physical PCD forms T=Kp+Fp Mp^-1 D and applies T^-1 Fp Mp^-1; Mp must
 * be lumped. This retains the complete stabilization block D.
 * Its optional velocity-mass variant replaces Kp by a theta blend with
 * -C diag(Mu)^-1 B (same auxiliary boundary rows), and replaces Fp by
 * Fp+mu*(Knew-Kp). The default theta=0.5 retains geometric regularization;
 * this is a discrete-Laplace PCD blend, not the additive PCDR formula.
 * added_mass eliminates an explicit nodal structural compliance Hs from
 * A=[F E;G K], then forms Fhat=F-E Hs G and a nodal inverse Hf of Fhat.
 * Its pressure matrix is D-Cs Hs Bs-(Cf-Cs Hs G) Hf (Bf-E Hs Bs).
 * Both coupling directions remain independent; no density-ratio surrogate is
 * inserted. Accuracy of Hs/Hf is local and is not a mesh-independence claim.
 * Root row sets are immutable, locally owned, disjoint, and globally nonempty.
 */
PressureSchurHandle make_pressure_schur_state(MPI_Comm comm,Mat root,
    const std::vector<PetscInt>& velocity_root_rows,
    const std::vector<PetscInt>& pressure_root_rows,PressureSchurKind kind,
    const PressureComplianceLayout& compliance={});

/// Borrowed stable USER preconditioning matrix, L (LSC/BFBt) or T (PCD).
Mat pressure_schur_matrix(const PressureSchurHandle& state);
/// Collective numeric update after a valid constrained root Jacobian assembly.
void refresh_pressure_schur(const PressureSchurHandle& state,Mat root);
/** Configure a pressure KSP with a shell action and independent work vectors.
 * The containing Schur operator stays unchanged. One shared state may serve
 * multiple main/inner/upper solver instances; refresh it only once per J.
 * Auxiliary inverse options use the pressure KSP prefix plus pressure_aux_.
 * Default auxiliary action is one GAMG application; finite-work iterative
 * overrides are allowed, with breakdown and PC failures propagated.
 */
void configure_pressure_schur_pc(MPI_Comm comm,KSP pressure,
    const PressureSchurHandle& state);
/// Borrowed auxiliary solver for diagnostics; nullptr for unrelated PCs.
KSP pressure_schur_auxiliary_solver(PC pc);
} // namespace eonsim
