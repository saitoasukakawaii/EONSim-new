#pragma once
#include "eonsim/linear_system.hpp"
#include <memory>

namespace eonsim {
enum class PressureSchurKind { lsc, bfbt, pcd };

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

/** Propagate optional composed PCD operators to a compact root submatrix.
 * Extracts child_rows in its exact distributed IS order, reusing the child
 * compositions and their sparsity when present. Call after each root update,
 * before building or refreshing the child's pressure preconditioner.
 * No auxiliaries is a no-op; incomplete triples fail collectively.
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
 * Root row sets are immutable, locally owned, disjoint, and globally nonempty.
 */
PressureSchurHandle make_pressure_schur_state(MPI_Comm comm,Mat root,
    const std::vector<PetscInt>& velocity_root_rows,
    const std::vector<PetscInt>& pressure_root_rows,PressureSchurKind kind);

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
