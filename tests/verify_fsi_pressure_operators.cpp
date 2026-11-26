#include "eonsim/fsi_pressure_operators.hpp"
#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <numeric>

using namespace eonsim;
namespace {
std::array<long double,4> dense_solve(std::array<long double,16> matrix,
                                     std::array<long double,4> rhs) {
    for(int k=0;k<4;++k) {
        int pivot=k;
        for(int i=k+1;i<4;++i) if(std::abs(matrix[4*i+k])>std::abs(matrix[4*pivot+k])) pivot=i;
        if(std::abs(matrix[4*pivot+k])<1e-20L) throw std::runtime_error("Singular Stokes mass oracle");
        for(int j=k;j<4;++j) std::swap(matrix[4*k+j],matrix[4*pivot+j]);
        std::swap(rhs[k],rhs[pivot]);
        for(int i=k+1;i<4;++i) {
            const auto factor=matrix[4*i+k]/matrix[4*k+k];
            for(int j=k;j<4;++j) matrix[4*i+j]-=factor*matrix[4*k+j];
            rhs[i]-=factor*rhs[k];
        }
    }
    for(int k=3;k>=0;--k) {
        for(int j=k+1;j<4;++j) rhs[k]-=matrix[4*k+j]*rhs[j];
        rhs[k]/=matrix[4*k+k];
    }
    return rhs;
}

double verify_stokes_mass_limit(FsiPressureOperators& operators,Mat root,
    const Tet4Topology::Nodal<Point>& reference,std::vector<FsiElementData>& data) {
    // The independent expected action is (Mp/mu+D)^-1, assembled directly
    // from analytic tetrahedron volume and D. It never uses production K/F/T.
    // Nonzero auxiliary-boundary data catches the former identity-row error.
    const std::vector<PetscInt> pressure{3,10,17,24},velocity{0,1,2};
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-stokes_pressure_aux_ksp_type","preonly"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-stokes_pressure_aux_pc_type","lu"));
    PressureSchurHandle state;
    PetscOwner<KSP,KSPDestroy> solver;
    PetscOwner<Vec,VecDestroy> rhs,solution;
    const std::array<double,3> scales{.25,1.,3.},viscosities{.17,.7,2.4};
    const std::array<long double,4> input{.4L,-1.1L,2.L,.3L};
    double worst=0.;
    for(std::size_t phase=0;phase<scales.size();++phase) {
        const double scale=scales[phase],mu=viscosities[phase],volume=scale*scale*scale/6.;
        // Finite positive coefficients approximate the steady limit far below
        // roundoff without adding a test-only production assembly mode.
        data[0].fluid={2.3,mu,1e30,0.,false,0.}; data[0].mesh_dt=.13;
        std::vector<double> full(28,0.);
        for(int a=0;a<4;++a) for(int c=0;c<3;++c)
            full[7*a+4+c]=(scale-1.)*reference[a][c];
        operators.update(full,data,root);
        for(bool stabilized:{false,true}) {
            std::array<double,16> d{};
            std::array<long double,16> schur{};
            for(int a=0;a<4;++a) for(int b=0;b<4;++b) {
                // A non-diagonal positive-semidefinite pressure block with
                // zero row sum, resembling pressure-gradient stabilization.
                d[4*a+b]=stabilized?.03*(a==b?3.:-1.):0.;
                schur[4*a+b]=d[4*a+b]+(a==b?volume/(4.L*mu):0.L);
            }
            EONSIM_PETSC(MatSetValues(root,4,pressure.data(),4,pressure.data(),d.data(),INSERT_VALUES));
            EONSIM_PETSC(MatAssemblyBegin(root,MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(root,MAT_FINAL_ASSEMBLY));
            if(!state) {
                state=make_pressure_schur_state(PETSC_COMM_SELF,root,velocity,pressure,PressureSchurKind::pcd);
                EONSIM_PETSC(KSPCreate(PETSC_COMM_SELF,solver.put()));
                EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),"stokes_"));
                const auto matrix=pressure_schur_matrix(state);
                EONSIM_PETSC(KSPSetOperators(solver.get(),matrix,matrix));
                configure_pressure_schur_pc(PETSC_COMM_SELF,solver.get(),state);
                EONSIM_PETSC(MatCreateVecs(matrix,solution.put(),rhs.put()));
            } else refresh_pressure_schur(state,root);
            const auto expected=dense_solve(schur,input);
            PetscScalar* values=nullptr;
            EONSIM_PETSC(VecGetArray(rhs.get(),&values));
            for(int a=0;a<4;++a) values[a]=static_cast<double>(input[a]);
            EONSIM_PETSC(VecRestoreArray(rhs.get(),&values));
            EONSIM_PETSC(KSPSolve(solver.get(),rhs.get(),solution.get()));
            KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
            EONSIM_PETSC(KSPGetConvergedReason(solver.get(),&reason));
            if(reason<=0) throw std::runtime_error("Stokes pressure action did not converge");
            const PetscScalar* actual=nullptr;
            EONSIM_PETSC(VecGetArrayRead(solution.get(),&actual));
            bool finite=true;
            for(int a=0;a<4;++a) {
                finite=finite&&std::isfinite(actual[a]);
                worst=std::max(worst,static_cast<double>(std::abs(actual[a]-expected[a])/
                    std::max(1.L,std::abs(expected[a]))));
            }
            EONSIM_PETSC(VecRestoreArrayRead(solution.get(),&actual));
            if(!finite||worst>2e-12) throw std::runtime_error("PCD failed independent Stokes mass-limit action oracle");
        }
    }
    return worst;
}

void verify_viscosity_collectives(MPI_Comm comm,bool empty_owners) {
    int rank=0,ranks=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    const bool owns=!empty_owners||rank==0;
    const int owners=empty_owners?1:ranks;
    constexpr int nc=7,block=35;
    const PetscInt owned=owns?block:0,begin=empty_owners?(rank?block:0):block*rank;
    MeshPartition mesh;
    mesh.rank=rank; mesh.ranks=ranks; mesh.global_nodes=5*owners; mesh.global_cells=2*owners;
    if(owns) {
        const GlobalId first=5*rank;
        mesh.nodes={{first,{0,0,0}},{first+1,{1,0,0}},{first+2,{0,1,0}},
                    {first+3,{0,0,1}},{first+4,{1,1,1}}};
        mesh.owned_nodes=5; mesh.owned_begin=first;
        mesh.cells={{2*rank,{0,1,2,3},1},{2*rank+1,{4,2,1,3},1}};
        mesh.node_boundary_tags={{9},{},{},{},{}};
    }
    ReducedLayout reduced;
    reduced.components=nc; reduced.algebra.begin=begin;
    reduced.algebra.owned=owned; reduced.algebra.global=block*owners;
    reduced.global.resize(owned); std::iota(reduced.global.begin(),reduced.global.end(),begin);
    std::vector<bool> fluid(mesh.cells.size(),true);
    std::vector<FsiElementData> data;
    for(const auto& cell:mesh.cells) {
        Tet4Topology::Nodal<Point> reference{};
        for(int a=0;a<4;++a) reference[a]=mesh.nodes[cell.nodes[a]].position;
        data.emplace_back(reference); data.back().fluid={1.,.7,.1,0.,false,0.};
    }
    FsiPressureOperators operators(comm,mesh,reduced,fluid,{9});
    PetscOwner<Mat,MatDestroy> root;
    EONSIM_PETSC(MatCreateAIJ(comm,owned,owned,block*owners,block*owners,owned?1:0,nullptr,0,nullptr,root.put()));
    EONSIM_PETSC(MatAssemblyBegin(root.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(root.get(),MAT_FINAL_ASSEMBLY));
    std::vector<double> full(owned,0.);
    operators.update(full,data,root.get()); // Must include ranks with no fluid cells/rows.
    if(rank==0) data[1].fluid.viscosity=1.1;
    bool rejected=false;
    try { operators.update(full,data,root.get()); }
    catch(const std::runtime_error& error) {
        rejected=std::string(error.what()).find("uniform positive viscosity")!=std::string::npos;
    }
    int good=rejected?1:0,all_good=0;
    EONSIM_PETSC(MPI_Allreduce(&good,&all_good,1,MPI_INT,MPI_MIN,comm));
    if(!all_good) throw std::runtime_error("PCD did not collectively reject regional viscosity");
    for(auto& cell:data) cell.fluid.viscosity=.7;
    operators.update(full,data,root.get()); // Rejection must leave the producer reusable.
    if(!empty_owners&&ranks>1) {
        if(rank==ranks-1) for(auto& cell:data) cell.fluid.viscosity=1.1;
        rejected=false;
        try { operators.update(full,data,root.get()); }
        catch(const std::runtime_error& error) {
            rejected=std::string(error.what()).find("uniform positive viscosity")!=std::string::npos;
        }
        good=rejected?1:0;
        EONSIM_PETSC(MPI_Allreduce(&good,&all_good,1,MPI_INT,MPI_MIN,comm));
        if(!all_good) throw std::runtime_error("PCD did not collectively reject rank-dependent viscosity");
    }
}
} // namespace

int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int status=0;
    try {
        // An affine unit tetrahedron supplies an independent closed-form
        // integral oracle. A single marked auxiliary boundary row leaves a
        // nontrivial 3x3 free pressure block to check off-diagonal convection.
        MeshPartition mesh;
        mesh.nodes={{0,{0,0,0}},{1,{1,0,0}},{2,{0,1,0}},{3,{0,0,1}}};
        mesh.owned_nodes=4; mesh.global_nodes=4;
        mesh.cells={{0,{0,1,2,3},1}};
        mesh.node_boundary_tags={{9},{},{},{}};
        ReducedLayout reduced;
        constexpr int nc=7,n=28;
        reduced.components=nc; reduced.algebra.owned=n; reduced.algebra.global=n;
        reduced.global.resize(n); std::iota(reduced.global.begin(),reduced.global.end(),0);
        std::vector<bool> fluid{true};
        FsiPressureOperators operators(PETSC_COMM_SELF,mesh,reduced,fluid,{9});
        PetscOwner<Mat,MatDestroy> root;
        EONSIM_PETSC(MatCreateSeqAIJ(PETSC_COMM_SELF,n,n,4,nullptr,root.put()));
        EONSIM_PETSC(MatSetOption(root.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
        EONSIM_PETSC(MatSetOption(root.get(),MAT_IGNORE_ZERO_ENTRIES,PETSC_FALSE));
        for(PetscInt row=0;row<n;++row) EONSIM_PETSC(MatSetValue(root.get(),row,row,1,INSERT_VALUES));
        const std::array<PetscInt,4> pressure_rows{3,10,17,24};
        const std::array<double,16> zero_pressure{};
        EONSIM_PETSC(MatSetValues(root.get(),4,pressure_rows.data(),4,pressure_rows.data(),zero_pressure.data(),INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(root.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(root.get(),MAT_FINAL_ASSEMBLY));
        Tet4Topology::Nodal<Point> reference{};
        for(int a=0;a<4;++a) reference[a]=mesh.nodes[a].position;
        std::vector<FsiElementData> data; data.emplace_back(reference);
        // Run the behavioral oracle first so linking this test against the
        // former producer fails specifically on its Stokes-limit action.
        const double stokes_error=verify_stokes_mass_limit(operators,root.get(),reference,data);
        std::array<Mat,3> first{};
        const std::array<const char*,3> keys{pressure_pcd_mass_key,pressure_pcd_laplace_key,pressure_pcd_transport_key};
        double worst=0.;
        for(int generation=0;generation<4;++generation) {
            const double scale=1.+.15*generation,dt=.08/(generation+1),mesh_dt=.13;
            const double rho=2.3,mu=.7;
            const bool convection=generation!=3;
            data[0].fluid={rho,mu,dt,0.,convection,0.}; data[0].mesh_dt=mesh_dt;
            std::vector<double> full(n,0.);
            Tet4Topology::Nodal<Point> relative{};
            for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                const double displacement=(scale-1)*reference[a][c];
                relative[a][c]=.2+.3*a-.1*c;
                full[nc*a+4+c]=displacement;
                full[nc*a+c]=relative[a][c]+displacement/mesh_dt;
            }
            operators.update(full,data,root.get());
            const double volume=scale*scale*scale/6.;
            const std::array<Point,4> gradients{{{-1./scale,-1./scale,-1./scale},
                {1./scale,0,0},{0,1./scale,0},{0,0,1./scale}}};
            for(std::size_t kind=0;kind<keys.size();++kind) {
                Mat matrix=nullptr;
                EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(root.get()),keys[kind],reinterpret_cast<PetscObject*>(&matrix)));
                if(!matrix||(generation&&matrix!=first[kind])) throw std::runtime_error("PCD composed matrix identity changed");
                first[kind]=matrix;
                for(int a=0;a<4;++a) for(int b=0;b<4;++b) {
                    double expected=0.;
                    if(kind==0) expected=a==b?volume/4.:0.;
                    else if(a==0) expected=a==b?(kind==1?1.:mu):0.;
                    else {
                        double stiffness=0.;
                        for(int c=0;c<3;++c) stiffness+=volume*gradients[a][c]*gradients[b][c];
                        if(kind==1) expected=stiffness;
                        else {
                            expected=rho/dt*volume*(a==b?2.:1.)/20.+mu*stiffness;
                            if(convection) for(int q=0;q<4;++q) for(int c=0;c<3;++c)
                                expected+=rho*volume*(a==q?2.:1.)/20.*relative[q][c]*gradients[b][c];
                        }
                    }
                    const PetscInt row=nc*a+3,column=nc*b+3;
                    double actual=0.; EONSIM_PETSC(MatGetValues(matrix,1,&row,1,&column,&actual));
                    worst=std::max(worst,std::abs(actual-expected)/std::max(1.,std::abs(expected)));
                }
            }
        }
        if(worst>2e-13) throw std::runtime_error("PCD physical auxiliary closed-form integral mismatch");
        bool rejected=false;
        try { FsiPressureOperators missing(PETSC_COMM_SELF,mesh,reduced,fluid,{11}); }
        catch(const std::runtime_error&) { rejected=true; }
        if(!rejected) throw std::runtime_error("PCD missing auxiliary gauge was not rejected");
        std::cout<<"PCD physical matrices: four ALE/time generations including disabled convection, stable handles, exact mass/Laplace/convection, max_error="<<worst
                 <<", independent Stokes mass-limit actions=6 max_error="<<stokes_error<<"\n";
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; status=1; }
    int any=0; EONSIM_PETSC(MPI_Allreduce(&status,&any,1,MPI_INT,MPI_MAX,PETSC_COMM_WORLD));
    if(!any) try {
        verify_viscosity_collectives(PETSC_COMM_WORLD,true);
        int ranks=0; MPI_Comm_size(PETSC_COMM_WORLD,&ranks);
        if(ranks>1) verify_viscosity_collectives(PETSC_COMM_WORLD,false);
        PetscPrintf(PETSC_COMM_WORLD,"PCD uniform-viscosity collectives and empty fluid owners passed\n");
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; status=1; }
    EONSIM_PETSC(MPI_Allreduce(&status,&any,1,MPI_INT,MPI_MAX,PETSC_COMM_WORLD));
    PetscFinalize();
    return any;
}
