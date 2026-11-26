#include "eonsim/fsi_pressure_operators.hpp"
#include "eonsim/quadrature.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0;
    EONSIM_PETSC(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm));
    if(any) throw std::runtime_error(message);
}
}
FsiPressureOperators::FsiPressureOperators(MPI_Comm comm,const MeshPartition& mesh,
    const ReducedLayout& reduced,const std::vector<bool>& fluid_cells,
    const std::vector<int>& traction_tags):comm_(comm),mesh_(mesh),reduced_(reduced),fluid_cells_(fluid_cells) {
    const auto& layout=reduced.algebra;
    common_check(comm,fluid_cells.size()==mesh.cells.size(),"PCD fluid-cell layout mismatch");
    std::set<PetscInt> rows;
    // node_boundary_tags is owner/ghost-complete even when the owner has no
    // local traction face, so boundary rows are imposed exactly once.
    for(std::size_t n=0;n<mesh.owned_nodes;++n) {
        const auto row=reduced.global[reduced.components*n+Tet4Flow::pressure];
        if(row<layout.begin||row>=layout.begin+layout.owned) continue;
        const auto& tags=mesh.node_boundary_tags[n];
        if(std::any_of(traction_tags.begin(),traction_tags.end(),[&](int tag) {
            return std::find(tags.begin(),tags.end(),tag)!=tags.end();
        })) rows.insert(row);
    }
    boundary_rows_.assign(rows.begin(),rows.end());
    PetscInt count=boundary_rows_.size(),total=0;
    EONSIM_PETSC(MPI_Allreduce(&count,&total,1,MPIU_INT,MPI_SUM,comm));
    common_check(comm,total>0,"PCD requires an existing pressure-traction boundary for its auxiliary Laplace gauge");
    for(auto* matrix:{&mass_,&laplace_,&transport_}) {
        EONSIM_PETSC(MatCreateAIJ(comm,layout.owned,layout.owned,layout.global,layout.global,
            16,nullptr,16,nullptr,matrix->put()));
        EONSIM_PETSC(MatSetOption(matrix->get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
        // Preserve geometrically possible entries, including current zeros.
        EONSIM_PETSC(MatSetOption(matrix->get(),MAT_IGNORE_ZERO_ENTRIES,PETSC_FALSE));
    }
}
void FsiPressureOperators::update(const std::vector<double>& full,
    const std::vector<FsiElementData>& data,Mat jacobian) {
    const int nc=reduced_.components;
    common_check(comm_,data.size()==mesh_.cells.size()&&full.size()==mesh_.nodes.size()*nc,
                 "PCD trial/data layout mismatch");
    if(assembled_) for(auto* matrix:{&mass_,&laplace_,&transport_})
        EONSIM_PETSC(MatZeroEntries(matrix->get()));
    int failed=0;
    std::string error;
    try {
        for(std::size_t e=0;e<mesh_.cells.size();++e) {
            if(!fluid_cells_[e]) continue;
            const auto& cell=mesh_.cells[e]; const auto& coefficients=data[e];
            const double rho=coefficients.fluid.density,mu=coefficients.fluid.viscosity;
            const double dt=coefficients.fluid.dt;
            const double mesh_dt=coefficients.mesh_dt>0?coefficients.mesh_dt:dt;
            if(!(rho>0&&mu>0&&dt>0&&mesh_dt>0)) throw std::runtime_error("Invalid PCD material/time coefficients");
            Tet4Topology::Nodal<Point> xyz,relative;
            std::array<PetscInt,4> rows{};
            for(int a=0;a<4;++a) {
                const auto n=cell.nodes[a];
                rows[a]=reduced_.global[nc*n+Tet4Flow::pressure];
                if(rows[a]<0) throw std::runtime_error("PCD requires active nodal fluid pressure");
                for(int c=0;c<3;++c) {
                    const double displacement=full[nc*n+Tet4Ale::mesh_offset+c];
                    xyz[a][c]=coefficients.reference[a][c]+displacement;
                    relative[a][c]=full[nc*n+c]-(displacement-coefficients.previous_mesh[a][c])/mesh_dt;
                }
            }
            const auto geometry=tet4_geometry(xyz);
            std::array<double,16> k{},f{};
            for(int a=0;a<4;++a) {
                const double lump=geometry.volume/4.;
                EONSIM_PETSC(MatSetValue(mass_.get(),rows[a],rows[a],lump,ADD_VALUES));
                for(int b=0;b<4;++b) {
                    double dot=0.;
                    for(int c=0;c<3;++c) dot+=geometry.gradients[a][c]*geometry.gradients[b][c];
                    k[4*a+b]=geometry.volume*dot;
                    f[4*a+b]=rho/dt*geometry.volume*(a==b?2.:1.)/20.+mu*k[4*a+b];
                }
            }
            // q * (u-w) dot grad(p) is quadratic for P1 q,u,w: the symmetric
            // four-point Tet4 rule integrates it exactly on this affine cell.
            if(coefficients.fluid.convection) for(const auto& point:SimplexGauss<Tet4Topology,4>::points) {
                Point velocity{};
                for(int a=0;a<4;++a) for(int c=0;c<3;++c) velocity[c]+=point.shape[a]*relative[a][c];
                for(int a=0;a<4;++a) for(int b=0;b<4;++b) {
                    double advection=0.;
                    for(int c=0;c<3;++c) advection+=velocity[c]*geometry.gradients[b][c];
                    f[4*a+b]+=geometry.volume*point.weight*rho*point.shape[a]*advection;
                }
            }
            if(!std::all_of(f.begin(),f.end(),[](double value){return std::isfinite(value);}))
                throw std::runtime_error("Nonfinite PCD pressure transport operator");
            EONSIM_PETSC(MatSetValues(laplace_.get(),4,rows.data(),4,rows.data(),k.data(),ADD_VALUES));
            EONSIM_PETSC(MatSetValues(transport_.get(),4,rows.data(),4,rows.data(),f.data(),ADD_VALUES));
        }
    } catch(const std::exception& exception) { failed=1; error=exception.what(); }
    int any=0;
    EONSIM_PETSC(MPI_Allreduce(&failed,&any,1,MPI_INT,MPI_MAX,comm_));
    // Drain every insertion stash even after a rejected local geometry.
    for(auto* matrix:{&mass_,&laplace_,&transport_}) {
        EONSIM_PETSC(MatAssemblyBegin(matrix->get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix->get(),MAT_FINAL_ASSEMBLY));
    }
    assembled_=true;
    if(any) {
        int rank=0,source=0; MPI_Comm_rank(comm_,&rank);
        const int candidate=failed?rank:std::numeric_limits<int>::max();
        EONSIM_PETSC(MPI_Allreduce(&candidate,&source,1,MPI_INT,MPI_MIN,comm_));
        int length=error.size(); EONSIM_PETSC(MPI_Bcast(&length,1,MPI_INT,source,comm_));
        error.resize(length); EONSIM_PETSC(MPI_Bcast(error.data(),length,MPI_CHAR,source,comm_));
        throw std::runtime_error("PCD auxiliary assembly: "+error);
    }
    // Auxiliary homogeneous boundary rows and columns are consistent in all
    // three operators. This does not constrain the original pressure unknown.
    for(auto* matrix:{&mass_,&laplace_,&transport_})
        EONSIM_PETSC(MatZeroRowsColumns(matrix->get(),boundary_rows_.size(),boundary_rows_.data(),1.,nullptr,nullptr));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),"eonsim_pcd_mass",reinterpret_cast<PetscObject>(mass_.get())));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),"eonsim_pcd_laplace",reinterpret_cast<PetscObject>(laplace_.get())));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),"eonsim_pcd_transport",reinterpret_cast<PetscObject>(transport_.get())));
}
} // namespace eonsim
