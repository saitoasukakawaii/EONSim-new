#include "eonsim/fsi_pressure_operators.hpp"
#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <numeric>

using namespace eonsim;
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
        EONSIM_PETSC(MatCreateSeqAIJ(PETSC_COMM_SELF,n,n,1,nullptr,root.put()));
        for(PetscInt row=0;row<n;++row) EONSIM_PETSC(MatSetValue(root.get(),row,row,1,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(root.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(root.get(),MAT_FINAL_ASSEMBLY));
        Tet4Topology::Nodal<Point> reference{};
        for(int a=0;a<4;++a) reference[a]=mesh.nodes[a].position;
        std::vector<FsiElementData> data; data.emplace_back(reference);
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
                    if(a==0||b==0) expected=a==b?1.:0.;
                    else if(kind==0) expected=a==b?volume/4.:0.;
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
        std::cout<<"PCD physical matrices: four ALE/time generations including disabled convection, stable handles, exact mass/Laplace/convection, max_error="<<worst<<"\n";
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; status=1; }
    PetscFinalize();
    return status;
}
