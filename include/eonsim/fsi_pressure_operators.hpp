#pragma once
#include "eonsim/fsi_element.hpp"
#include "eonsim/reduced_layout.hpp"

namespace eonsim {
/** P1 pressure auxiliary operators on the current ALE geometry. Full-root
 * numbering is retained only for composition/provenance; nonpressure rows are
 * empty. The physical Jacobian and boundary conditions are never changed.
 * Homogeneous auxiliary Dirichlet data on the existing pressure-traction
 * boundary fixes the Laplace gauge; other boundaries use natural Neumann data.
 * This choice is an explicit PCD approximation, not a physical pressure pin.
 */
class FsiPressureOperators {
public:
    FsiPressureOperators(MPI_Comm,const MeshPartition&,const ReducedLayout&,
        const std::vector<bool>& fluid_cells,const std::vector<int>& traction_tags);
    /// Collective after successful physical assembly; data contains this step's
    /// effective time coefficients, full contains the current physical trial.
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
