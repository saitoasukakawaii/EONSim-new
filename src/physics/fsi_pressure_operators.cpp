#include "eonsim/fsi_pressure_operators.hpp"
#include "eonsim/pressure_schur_pc.hpp"
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
    const std::vector<int>& traction_tags,const std::vector<int>& inlet_tags):
    comm_(comm),mesh_(mesh),reduced_(reduced),fluid_cells_(fluid_cells) {
    const auto& layout=reduced.algebra;
    common_check(comm,fluid_cells.size()==mesh.cells.size(),"PCD fluid-cell layout mismatch");
    PetscBool robin=PETSC_FALSE,velocity_mass=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_pcd_robin",&robin,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_pcd_velocity_mass",&velocity_mass,nullptr));
    int choices[2]{robin?1:0,velocity_mass?1:0},minimum[2]{},maximum[2]{};
    EONSIM_PETSC(MPI_Allreduce(choices,minimum,2,MPI_INT,MPI_MIN,comm));
    EONSIM_PETSC(MPI_Allreduce(choices,maximum,2,MPI_INT,MPI_MAX,comm));
    common_check(comm,minimum[0]==maximum[0]&&minimum[1]==maximum[1],"PCD enhancement options differ between ranks");
    robin_=robin; velocity_mass_enabled_=velocity_mass;
    if(robin_) {
        common_check(comm,!inlet_tags.empty(),"PCD Robin correction requires an explicit velocity/flow inlet tag");
        bool valid=true;
        try {
            const auto facets=build_boundary_facets(mesh);
            for(std::size_t i=0;i<mesh.boundary.size();++i)
                if(std::find(inlet_tags.begin(),inlet_tags.end(),mesh.boundary[i].physical_tag)!=inlet_tags.end()) {
                    valid=valid&&fluid_cells[facets[i].cell];
                    if(fluid_cells[facets[i].cell]) robin_faces_.push_back(facets[i]);
                }
        } catch(const std::exception&) { valid=false; }
        common_check(comm,valid,"PCD Robin inlet must have a unique fluid-cell boundary adjacency");
        PetscInt local=robin_faces_.size(),total=0;
        EONSIM_PETSC(MPI_Allreduce(&local,&total,1,MPIU_INT,MPI_SUM,comm));
        common_check(comm,total>0,"PCD Robin inlet has no boundary faces");
    }
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
    std::vector<PetscOwner<Mat,MatDestroy>*> matrices{&mass_,&laplace_,&transport_};
    if(velocity_mass_enabled_) matrices.insert(matrices.end(),{&velocity_mass_,&viscosity_,&boundary_});
    for(auto* matrix:matrices) {
        EONSIM_PETSC(MatCreateAIJ(comm,layout.owned,layout.owned,layout.global,layout.global,
            16,nullptr,16,nullptr,matrix->put()));
        EONSIM_PETSC(MatSetOption(matrix->get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
        // Preserve geometrically possible entries, including current zeros.
        EONSIM_PETSC(MatSetOption(matrix->get(),MAT_IGNORE_ZERO_ENTRIES,PETSC_FALSE));
        EONSIM_PETSC(MatSetOption(matrix->get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
    }
}
void FsiPressureOperators::update(const std::vector<double>& full,
    const std::vector<FsiElementData>& data,Mat jacobian) {
    const int nc=reduced_.components;
    common_check(comm_,data.size()==mesh_.cells.size()&&full.size()==mesh_.nodes.size()*nc,
                 "PCD trial/data layout mismatch");
    // The BRM2 identity contribution is mu Mp^-1. The current FSI producer
    // supplies one spatially constant viscosity; do not silently extend that
    // factorization to regional materials. Empty fluid owners still take part.
    double local_min=std::numeric_limits<double>::infinity(),local_max=0.;
    bool valid_viscosity=true;
    for(std::size_t e=0;e<data.size();++e) if(fluid_cells_[e]) {
        const double mu=data[e].fluid.viscosity;
        valid_viscosity=valid_viscosity&&std::isfinite(mu)&&mu>0.;
        if(std::isfinite(mu)&&mu>0.) {
            local_min=std::min(local_min,mu); local_max=std::max(local_max,mu);
        }
    }
    double mu_min=0.,mu_max=0.;
    EONSIM_PETSC(MPI_Allreduce(&local_min,&mu_min,1,MPI_DOUBLE,MPI_MIN,comm_));
    EONSIM_PETSC(MPI_Allreduce(&local_max,&mu_max,1,MPI_DOUBLE,MPI_MAX,comm_));
    common_check(comm_,valid_viscosity&&std::isfinite(mu_min)&&mu_min>0.&&mu_min==mu_max,
                 "PCD auxiliary boundary factorization requires spatially uniform positive viscosity");
    std::vector<PetscOwner<Mat,MatDestroy>*> matrices{&mass_,&laplace_,&transport_};
    if(velocity_mass_enabled_) matrices.insert(matrices.end(),{&velocity_mass_,&viscosity_,&boundary_});
    if(assembled_) for(auto* matrix:matrices)
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
                if(velocity_mass_enabled_) for(int component=0;component<3;++component) {
                    // Fluid traces at the interface share their independent
                    // structural velocity row. Inactive/fixed components have
                    // no reduced row and cannot contribute to its L2 mass.
                    const auto velocity_row=reduced_.global[nc*cell.nodes[a]+component];
                    if(velocity_row>=0)
                        EONSIM_PETSC(MatSetValue(velocity_mass_.get(),velocity_row,velocity_row,lump,ADD_VALUES));
                }
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
        for(const auto& face:robin_faces_) {
            const auto& cell=mesh_.cells[face.cell]; const auto& coefficients=data[face.cell];
            if(!coefficients.fluid.convection) continue;
            const double rho=coefficients.fluid.density;
            const double mesh_dt=coefficients.mesh_dt>0?coefficients.mesh_dt:coefficients.fluid.dt;
            Tet4Topology::Nodal<Point> xyz{},relative{};
            for(int a=0;a<4;++a) for(int component=0;component<3;++component) {
                const auto node=cell.nodes[a];
                const double displacement=full[nc*node+Tet4Ale::mesh_offset+component];
                xyz[a][component]=coefficients.reference[a][component]+displacement;
                relative[a][component]=full[nc*node+component]-
                    (displacement-coefficients.previous_mesh[a][component])/mesh_dt;
            }
            Tri3Topology::Nodal<Point> points{};
            std::array<PetscInt,3> rows{};
            for(int a=0;a<3;++a) {
                points[a]=xyz[face.local_nodes[a]];
                rows[a]=reduced_.global[nc*cell.nodes[face.local_nodes[a]]+Tet4Flow::pressure];
            }
            const auto surface=triangle_geometry(points,xyz[face.opposite]);
            std::array<double,3> normal_velocity{};
            for(int a=0;a<3;++a) for(int component=0;component<3;++component)
                normal_velocity[a]+=relative[face.local_nodes[a]][component]*surface.normal[component];
            std::array<double,9> robin{};
            for(int a=0;a<3;++a) for(int b=0;b<3;++b) for(int q=0;q<3;++q) {
                // Integral of three barycentric factors: A/10 (all equal),
                // A/30 (two equal), A/60 (all distinct). A degree-two face
                // quadrature is insufficient for the linearly varying wind.
                const int multiplicity=a==b&&b==q?6:(a==b||a==q||b==q?2:1);
                robin[3*a+b]-=rho*normal_velocity[q]*surface.area*multiplicity/60.;
            }
            if(!std::all_of(robin.begin(),robin.end(),[](double value){return std::isfinite(value);}))
                throw std::runtime_error("Nonfinite PCD inlet Robin operator");
            EONSIM_PETSC(MatSetValues(transport_.get(),3,rows.data(),3,rows.data(),robin.data(),ADD_VALUES));
        }
        if(velocity_mass_enabled_) {
            for(std::size_t node=0;node<mesh_.owned_nodes;++node) {
                const auto row=reduced_.global[nc*node+Tet4Flow::pressure];
                if(row>=reduced_.algebra.begin&&row<reduced_.algebra.begin+reduced_.algebra.owned)
                    EONSIM_PETSC(MatSetValue(viscosity_.get(),row,row,mu_min,ADD_VALUES));
            }
            for(const auto row:boundary_rows_)
                EONSIM_PETSC(MatSetValue(boundary_.get(),row,row,1.,ADD_VALUES));
        }
    } catch(const std::exception& exception) { failed=1; error=exception.what(); }
    int any=0;
    EONSIM_PETSC(MPI_Allreduce(&failed,&any,1,MPI_INT,MPI_MAX,comm_));
    // Drain every insertion stash even after a rejected local geometry.
    for(auto* matrix:matrices) {
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
    // Preserve the leading Stokes inverse on every pressure row, including
    // artificial Dirichlet nodes. With Q the free-row projector, E=I-Q and
    // Fp=mu Kp+N (reaction/advection), these row-only operations give
    // Kbc=Q Kp+E and Ftilde=Q Fp+mu E=mu Kbc+Q N. Thus
    // Kbc^-1 Ftilde Mp^-1=mu Mp^-1+Kbc^-1 Q N Mp^-1: only the Laplace
    // correction has homogeneous auxiliary data. Mass and boundary columns
    // must remain physical; setting all three operators to identity there
    // destroys both the viscosity and mesh-volume scaling of the Stokes term.
    EONSIM_PETSC(MatZeroRows(laplace_.get(),boundary_rows_.size(),boundary_rows_.data(),1.,nullptr,nullptr));
    EONSIM_PETSC(MatZeroRows(transport_.get(),boundary_rows_.size(),boundary_rows_.data(),mu_min,nullptr,nullptr));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_mass_key,reinterpret_cast<PetscObject>(mass_.get())));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_laplace_key,reinterpret_cast<PetscObject>(laplace_.get())));
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_transport_key,reinterpret_cast<PetscObject>(transport_.get())));
    if(velocity_mass_enabled_) {
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_velocity_mass_key,reinterpret_cast<PetscObject>(velocity_mass_.get())));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_viscosity_key,reinterpret_cast<PetscObject>(viscosity_.get())));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(jacobian),pressure_pcd_boundary_key,reinterpret_cast<PetscObject>(boundary_.get())));
    }
}
} // namespace eonsim
