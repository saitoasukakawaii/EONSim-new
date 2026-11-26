#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace eonsim;
namespace {
int setups=0;
struct CachedDiagonal { Vec inverse=nullptr; };
PetscErrorCode setup(PC pc) {
    CachedDiagonal* state=nullptr; Mat matrix=nullptr;
    PetscCall(PCShellGetContext(pc,&state));
    PetscCall(PCGetOperators(pc,&matrix,nullptr));
    if(!state->inverse) PetscCall(MatCreateVecs(matrix,&state->inverse,nullptr));
    PetscCall(MatGetDiagonal(matrix,state->inverse));
    PetscCall(VecReciprocal(state->inverse));
    ++setups;
    return PETSC_SUCCESS;
}
PetscErrorCode apply(PC pc,Vec x,Vec y) {
    CachedDiagonal* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    PetscCall(VecPointwiseMult(y,state->inverse,x));
    return PETSC_SUCCESS;
}
PetscErrorCode destroy(PC pc) {
    CachedDiagonal* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    PetscCall(VecDestroy(&state->inverse)); delete state;
    return PETSC_SUCCESS;
}
PetscErrorCode create(PC pc) {
    PetscCall(PCSetType(pc,PCSHELL));
    PetscCall(PCShellSetContext(pc,new CachedDiagonal));
    PetscCall(PCShellSetSetUp(pc,setup));
    PetscCall(PCShellSetApply(pc,apply));
    PetscCall(PCShellSetDestroy(pc,destroy));
    return PETSC_SUCCESS;
}
void check(MPI_Comm comm,bool good,const char* message) {
    int bad=!good,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
void option(const char* name,const char* value) { EONSIM_PETSC(PetscOptionsSetValue(nullptr,name,value)); }
void verify(MPI_Comm comm) {
    int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
    check(comm,size==1||size==2||size==4,"Expected 1/2/4 ranks");
    EONSIM_PETSC(PCRegister("adaptive_diagonal_test",create));
    option("-pc_type","adaptive_diagonal_test"); option("-ksp_type","fgmres");
    option("-ksp_rtol","1e-12"); option("-ksp_atol","1e-14");
    option("-nonlinear_adaptive_pc","true"); option("-nonlinear_pc_max_reuse","2");
    option("-nonlinear_pc_change_tolerance","0.05"); option("-nonlinear_pc_iteration_growth","100");
    AlgebraLayout layout; layout.global=12;
    const int active=size==4?3:size;
    layout.owned=rank<active?12/active:0; layout.begin=std::min(rank,active)*(12/active);
    for(PetscInt i=0;i<layout.owned;++i) {
        layout.local_to_global.push_back(layout.begin+i);
        layout.fields["state"].push_back(layout.begin+i);
    }
    layout.fields["state"]; layout.diagonal.assign(layout.owned,1); layout.off_diagonal.assign(layout.owned,0);
    NonlinearSystem system(comm,layout);
    SolverConfig config; config.absolute_tolerance=1e-11; config.relative_tolerance=1e-11;
    NonlinearAssemblyPhases phases; phases.preconditioner_context={.1,.1};
    const std::vector<double> initial(layout.owned,0);
    double multiplier=1,spread=0; bool reject=false;
    const auto assembly=[&](const std::vector<double>& x,Vec r,Mat j) {
        if(reject&&rank==0) throw StepRejected("adaptive rollback probe");
        for(PetscInt i=0;i<layout.owned;++i) {
            const auto row=layout.begin+i;
            const double diagonal=2*multiplier*(1+spread*(row+1));
            EONSIM_PETSC(VecSetValue(r,row,diagonal*(x[i]-(row+1)),ADD_VALUES));
            if(j) EONSIM_PETSC(MatSetValue(j,row,row,diagonal,ADD_VALUES));
        }
    };
    const auto solve=[&]() {
        auto result=system.solve(config,initial,{}, {},assembly,phases);
        bool exact=result.residual_norm<1e-8;
        for(PetscInt i=0;i<layout.owned;++i)
            exact=exact&&std::abs(result.values[i]-(layout.begin+i+1))<1e-9;
        check(comm,exact,"Adaptive PC changed the equation solution or final residual");
        return result;
    };
    const auto first=solve();
    check(comm,setups==1&&first.pc_refreshes==1&&first.pc_reuses==0,"First adaptive PC did not perform one real setup");
    spread=.0001; const auto reused1=solve();
    spread=.0002; const auto reused2=solve();
    check(comm,setups==1&&reused1.pc_reuses==1&&reused2.pc_reuses==1&&
          reused1.jacobian_assemblies==1&&reused2.jacobian_assemblies==1,
          "Fresh Jacobians did not reuse the actual cached numerical PC");
    const auto aged=solve();
    check(comm,setups==2&&aged.pc_age_refreshes==1&&aged.pc_refreshes==1,"Adaptive age bound did not rebuild PC");
    phases.preconditioner_context={.2,.2}; const auto timestep=solve();
    check(comm,setups==3&&timestep.pc_context_refreshes==1,"Time coefficients did not invalidate numerical PC");
    multiplier=2; const auto changed=solve();
    check(comm,setups==4&&changed.pc_drift_refreshes==1,"Matrix drift did not invalidate numerical PC");
    const auto generation=changed.solver_generation;
    reject=true; bool failed=false;
    try {solve();} catch(const StepRejected&) {failed=true;}
    reject=false;
    check(comm,failed,"Expected rejected state was accepted");
    const auto restored=solve();
    check(comm,setups==5&&restored.pc_refreshes==1&&restored.pc_reuses==0&&restored.solver_generation>generation,
          "Rejected nonlinear call retained stale numerical PC state");
    // A deliberately permissive drift threshold isolates the independent
    // iteration-growth trigger using twelve distinct diagonal eigenvalues.
    option("-nonlinear_pc_max_reuse","100"); option("-nonlinear_pc_change_tolerance","1");
    option("-nonlinear_pc_iteration_growth","1");
    multiplier=1; spread=0; const auto baseline=solve(); const int before=setups;
    spread=.2; const auto expensive=solve();
    check(comm,setups==before&&expensive.pc_reuses==1&&expensive.linear_iterations>baseline.linear_iterations+2,
          "Iteration-growth probe failed to use an old PC on the new operator");
    const auto refreshed=solve();
    check(comm,setups==before+1&&refreshed.pc_iteration_refreshes==1&&refreshed.linear_iterations<expensive.linear_iterations,
          "Iteration deterioration did not force the next numerical PC rebuild");
    // Empty context deliberately disallows reuse across unrelated callers.
    phases.preconditioner_context.clear(); const auto untagged=solve();
    check(comm,untagged.pc_refreshes==1&&untagged.pc_context_refreshes==1,"Missing time context reused an unrelated PC");
    // A reused factorization that exhausts its unchanged KSP budget gets one
    // rebuild attempt at the same accepted Newton state. This is an actual
    // Krylov failure, not a manufactured counter or a relaxed stopping gate.
    option("-ksp_max_it","2"); option("-nonlinear_pc_iteration_growth","100");
    phases.preconditioner_context={.1,.1}; spread=0; solve(); const int retry_setups=setups;
    spread=.2; const auto retried=solve();
    check(comm,retried.pc_rebuild_retries==1&&retried.pc_reuses==1&&retried.pc_refreshes==1&&
          setups==retry_setups+1,"Old-PC iteration exhaustion did not perform one bounded rebuild retry");
    option("-snes_lag_jacobian","2"); bool incompatible=false;
    try {solve();} catch(const std::runtime_error& failure) {
        incompatible=std::string(failure.what()).find("Adaptive PC requires")!=std::string::npos;
    }
    check(comm,incompatible,"Adaptive PC silently accepted a stale-Jacobian user policy");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_lag_jacobian"));
    if(rank==0) std::cout<<"adaptive_pc verified real setup counts, fresh operators, age/drift/time/iteration invalidation and rollback on "<<size<<" ranks\n";
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try {verify(PETSC_COMM_WORLD);}
    catch(const std::exception& error) {std::cerr<<error.what()<<'\n'; result=1;}
    PetscFinalize(); return result;
}
