/** Exact matrix-free Newton action: independent nonlinear root, off-rank
 * contributions, constraints, frozen linearizations, P lag and failure recovery. */
#include "eonsim/nonlinear_system.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
void option(const char* key,const char* value) { EONSIM_PETSC(PetscOptionsSetValue(nullptr,key,value)); }
void verify(MPI_Comm comm) {
    int rank=0,ranks=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    require(ranks==1||ranks==2||ranks==4,"Use 1, 2 or 4 MPI ranks");
    AlgebraLayout layout;
    layout.global=4; layout.owned=4/ranks; layout.begin=rank*layout.owned;
    for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
        layout.local_to_global.push_back(row); layout.fields["state"].push_back(row);
    }
    for(PetscInt row=0;row<4;++row)
        if(row<layout.begin||row>=layout.begin+layout.owned) layout.local_to_global.push_back(row);
    layout.diagonal.assign(layout.owned,layout.owned);
    layout.off_diagonal.assign(layout.owned,4-layout.owned);
    PetscInt local[4]{};
    for(std::size_t i=0;i<4;++i) local[layout.local_to_global[i]]=static_cast<PetscInt>(i);
    std::vector<PetscInt> constraints;
    if(3>=layout.begin&&3<layout.begin+layout.owned) constraints.push_back(3);
    std::vector<double> prescribed(constraints.size(),1.75),initial(4,.5);
    const double coupling[4][4]={{0,.11,-.03,.07},{-.06,0,.09,.02},{.04,-.12,0,.05},{.08,.02,-.07,0}};
    const auto target=[](int i) {return 1.+.25*i;};
    const PetscInt ids[]{0,1,2,3};
    SolverConfig settings; settings.relative_tolerance=1e-12; settings.absolute_tolerance=1e-12;
    settings.maximum_iterations=20;
    option("-pc_type","jacobi"); option("-ksp_rtol","1e-12"); option("-ksp_atol","1e-14");
    option("-ksp_max_it","100"); option("-ksp_pc_side","right");
    option("-ksp_norm_type","unpreconditioned"); option("-nonlinear_matrix_free_pc_interval","2");
    for(const char* method:{"fgmres","pipefgmres"}) {
        option("-ksp_type",method);
        NonlinearSystem system(comm,layout);
        bool inject=false;
        PetscInt tangent_calls=0,action_calls=0;
        const auto assemble=[&](const std::vector<double>& x,Vec residual,Mat matrix) {
            if(matrix) ++tangent_calls;
            if(rank!=ranks-1) return; // All other owners have empty local producers.
            double values[4]{},jacobian[16]{};
            for(int i=0;i<4;++i) {
                values[i]=(i+2)*(x[local[i]]*x[local[i]]-target(i)*target(i));
                for(int j=0;j<4;++j) {
                    values[i]+=coupling[i][j]*(x[local[j]]-target(j));
                    jacobian[4*i+j]=coupling[i][j]+(i==j?2*(i+2)*x[local[i]]:0.);
                }
            }
            values[3]+=7.; // Independent raw reaction; constrained equation is replaced by driver.
            EONSIM_PETSC(VecSetValues(residual,4,ids,values,ADD_VALUES));
            if(matrix) EONSIM_PETSC(MatSetValues(matrix,4,ids,4,ids,jacobian,ADD_VALUES));
        };
        NonlinearAssemblyPhases phases;
        phases.jacobian_action=[&](const std::vector<double>& x,const std::vector<double>& direction,Vec result) {
            ++action_calls;
            if(rank!=ranks-1) return;
            double values[4]{};
            for(int i=0;i<4;++i) {
                values[i]=2*(i+2)*x[local[i]]*direction[local[i]];
                for(int j=0;j<4;++j) values[i]+=coupling[i][j]*direction[local[j]];
            }
            EONSIM_PETSC(VecSetValues(result,4,ids,values,ADD_VALUES));
            if(inject) throw std::runtime_error("injected directional failure after off-rank insertion");
        };
        const auto solve=[&] {return system.solve(settings,initial,constraints,prescribed,assemble,phases);};
        const auto check=[&](const NonlinearResult& result) {
            for(int i=0;i<4;++i) {
                require(std::abs(result.values[local[i]]-target(i))<2e-11,"Matrix-free Newton differs from independent exact root");
                require(std::abs(result.raw_residual[local[i]]-(i==3?7.:0.))<2e-10,"Matrix-free solve changed physical reaction");
            }
            require(result.matrix_free_actions>0&&result.assembled_pc_reuses>0,"Matrix-free action or assembled P reuse was not exercised");
            require(result.jacobian_assemblies<result.jacobian_callbacks,"P was assembled for every matrix-free correction");
            require(result.field_residuals[0].equation_rows==3,"Constraint entered the physical field norm");
        };
        const auto first=solve(); check(first);
        const auto repeated=solve(); check(repeated);
        require(repeated.solver_reused,"Matrix-free session did not preserve its shell and ghost plan");
        inject=true; bool caught=false;
        try { (void)solve(); }
        catch(const std::runtime_error& e) { caught=std::string(e.what()).find("injected directional failure")!=std::string::npos; }
        require(caught,"Rank-local directional failure did not propagate");
        inject=false; check(solve());
        require(tangent_calls>0&&action_calls>tangent_calls,"Exact actions did not avoid assembled P work");
        if(rank==0) std::cout<<"matrix_free_oracle method="<<method<<" ranks="<<ranks
            <<" p_assemblies="<<first.jacobian_assemblies<<" p_reuses="<<first.assembled_pc_reuses
            <<" actions="<<first.matrix_free_actions<<" passed=1\n";
    }
    // The optional callback must agree collectively, even at an exact initial root.
    if(ranks>1) {
        NonlinearSystem invalid(comm,layout);
        NonlinearAssemblyPhases phases;
        if(rank==0) phases.jacobian_action=[](const auto&,const auto&,Vec){};
        bool caught=false;
        try { invalid.solve(settings,initial,constraints,prescribed,[](const auto&,Vec,Mat){},phases); }
        catch(const std::runtime_error& e) {caught=std::string(e.what()).find("every rank")!=std::string::npos;}
        require(caught,"Inconsistent matrix-free callback was accepted");
    }
    // An unused interval must not silently pass, even with zero residual.
    {
        NonlinearSystem invalid(comm,layout);
        bool caught=false;
        try { invalid.solve(settings,initial,constraints,prescribed,[](const auto&,Vec,Mat){}); }
        catch(const std::runtime_error& e) {caught=std::string(e.what()).find("requires a matrix-free")!=std::string::npos;}
        require(caught,"Unused matrix-free preconditioner interval was accepted");
    }
}
}
int main(int argc,char** argv) {
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try { EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr)); verify(PETSC_COMM_WORLD);
          EONSIM_PETSC(PetscPopErrorHandler()); }
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1);}
    return PetscFinalize();
}
