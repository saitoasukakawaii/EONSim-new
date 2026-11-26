#pragma once
#include "eonsim/fsi_element.hpp"
#include "eonsim/reduced_layout.hpp"

namespace eonsim {
/** P1 pressure auxiliary operators on the current ALE geometry. Full-root
 * numbering is retained only for composition/provenance; nonpressure rows are
 * empty. The physical Jacobian and boundary conditions are never changed.
 * For spatially uniform positive viscosity mu, homogeneous auxiliary data on
 * the existing pressure-traction boundary fixes only the Laplace correction's
 * gauge. With Q the free-row projector, E=I-Q, physical lumped mass Mp,
 * Laplacian Kp and reaction/advection N, the composed operators are Mp,
 * Kbc=Q Kp+E and Ftilde=mu Kbc+Q N. This retains mu Mp^-1 on all pressure
 * rows in the Stokes limit. Boundary columns are retained; the original
 * pressure unknown is not pinned. Other boundaries use natural data; inlet
 * convection Robin corrections and variable-viscosity PCD are not implemented.
 */
class FsiPressureOperators {
public:
    FsiPressureOperators(MPI_Comm,const MeshPartition&,const ReducedLayout&,
        const std::vector<bool>& fluid_cells,const std::vector<int>& traction_tags);
    /// Collective after successful physical assembly; data contains this step's
    /// effective time coefficients, full contains the current physical trial.
    /// Viscosity must be identical across all fluid cells and MPI ranks.
    void update(const std::vector<double>& full,const std::vector<FsiElementData>& data,Mat jacobian);
private:
    MPI_Comm comm_;
    const MeshPartition& mesh_;
    const ReducedLayout& reduced_;
    const std::vector<bool>& fluid_cells_;
    std::vector<PetscInt> boundary_rows_;
    PetscOwner<Mat,MatDestroy> mass_,laplace_,transport_;
    bool assembled_=false;
};
} // namespace eonsim
