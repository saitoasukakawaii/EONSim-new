#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <iostream>
#include <limits>
#include <sstream>
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

    // The first Newton correction of this C1 separable problem has J=I and
    // takes every unknown from zero to one. Thereafter F_i=d_i*(x_i^2-2):
    // stale I needs more than two Krylov iterations, while the rebuilt diagonal
    // is exact up to a common scale throughout the remaining Newton trajectory.
    // Five accepted steps are needed at this tolerance. Failing at the second
    // correction therefore distinguishes a total budget of four from a reset
    // budget of four after one already accepted step.
    option("-nonlinear_pc_max_reuse","100"); option("-nonlinear_pc_change_tolerance","1");
    option("-nonlinear_pc_iteration_growth","100"); option("-snes_linesearch_type","basic");
    option("-snes_max_funcs","10");
    NonlinearSystem budget_system(comm,layout);
    SolverConfig budget_config; budget_config.absolute_tolerance=1e-9;
    budget_config.relative_tolerance=0; budget_config.maximum_iterations=4;
    NonlinearAssemblyPhases budget_phases; budget_phases.preconditioner_context={1};
    std::vector<double> tangent_states;
    const auto nonlinear=[&](const std::vector<double>& x,Vec r,Mat j) {
        if(j) tangent_states.push_back(x.empty()?0.:x.front());
        for(PetscInt i=0;i<layout.owned;++i) {
            const auto row=layout.begin+i;
            const double d=row+1,value=x[i],shift=value-1;
            double residual=d*(value*value-2),diagonal=2*d*value;
            if(value<1) {
                const double a=6*d-2,b=4*d-1;
                residual+=a*shift*shift+b*shift*shift*shift;
                diagonal+=2*a*shift+3*b*shift*shift;
            }
            EONSIM_PETSC(VecSetValue(r,row,residual,ADD_VALUES));
            if(j) EONSIM_PETSC(MatSetValue(j,row,row,diagonal,ADD_VALUES));
        }
    };
    const auto late_retry=[&]() {
        return tangent_states.size()>=3&&(layout.owned==0||
            (std::abs(tangent_states[0])<1e-12&&std::abs(tangent_states[1]-1)<1e-12&&
             std::abs(tangent_states[2]-1)<1e-12));
    };
    const auto limited_solve=[&]() {
        tangent_states.clear();
        return budget_system.solve(budget_config,initial,{}, {},nonlinear,budget_phases);
    };
    bool iteration_limited=false;
    try {limited_solve();} catch(const StepRejected& error) {
        iteration_limited=std::string(error.what()).find(
            "reason="+std::to_string(static_cast<int>(SNES_DIVERGED_MAX_IT)))!=std::string::npos;
    }
    check(comm,iteration_limited&&late_retry(),"Fresh-PC retry reset the caller's total Newton iteration budget");
    option("-snes_max_it","10"); option("-snes_max_funcs","4");
    bool function_limited=false;
    try {limited_solve();} catch(const StepRejected& error) {
        function_limited=std::string(error.what()).find(
            "reason="+std::to_string(static_cast<int>(SNES_DIVERGED_FUNCTION_COUNT)))!=std::string::npos;
    }
    check(comm,function_limited&&late_retry(),"Fresh-PC retry reset the caller's function evaluation budget");
    // These PETSc options override budget_config.maximum_iterations=4. Restore
    // both effective limits after the retry so the retained solver can complete
    // the same five-step problem at the next physical context.
    option("-snes_max_it","5"); option("-snes_max_funcs","5");
    const auto within_budget=limited_solve();
    check(comm,within_budget.pc_rebuild_retries==1&&within_budget.iterations==5&&late_retry(),
          "Retry did not honor the effective PETSc budget or failed before an accepted Newton step");
    budget_phases.preconditioner_context={2};
    const auto next_budget=limited_solve();
    check(comm,next_budget.solver_reused&&next_budget.solver_generation==within_budget.solver_generation&&
          next_budget.pc_rebuild_retries==1&&next_budget.iterations==5&&late_retry(),
          "Retained adaptive session kept the retry's reduced Newton/function budgets");
    // On the second correction the larger RHS drives eta to its upper bound.
    // The same RHS is retried with a fresh PC. Its first eta must restart.
    option("-nonlinear_inexact_newton","true"); option("-nonlinear_true_residual","true");
    option("-nonlinear_forcing_initial","1e-4"); option("-nonlinear_forcing_max","1e-3");
    const std::string protocol(64,'c');
    option("-linear_protocol_hash",protocol.c_str()); option("-linear_report","true");
    budget_phases.step=1;
    const auto forcing_solve=[&]() {
        NonlinearSystem fresh(comm,layout);
        tangent_states.clear();
        return fresh.solve(budget_config,initial,{}, {},nonlinear,budget_phases);
    };
    option("-snes_max_it","4"); iteration_limited=false;
    try {forcing_solve();} catch(const StepRejected& error) {
        iteration_limited=std::string(error.what()).find(
            "reason="+std::to_string(static_cast<int>(SNES_DIVERGED_MAX_IT)))!=std::string::npos;
    }
    check(comm,iteration_limited&&late_retry(),"Inexact retry lost the original Newton budget");
    option("-snes_max_it","5");
    std::ostringstream receipt;
    auto* output=std::cout.rdbuf(receipt.rdbuf());
    NonlinearResult forced;
    try {forced=forcing_solve();} catch(...) {std::cout.rdbuf(output); throw;}
    std::cout.rdbuf(output);
    check(comm,forced.pc_rebuild_retries==1&&forced.iterations==5&&late_retry(),
          "Inexact fixture missed the bounded retry at the accepted state");
    bool exhausted=false,restarted=false;
    if(rank==0) {
        std::istringstream events(receipt.str());
        std::string line;
        double failed_rhs=0;
        while(std::getline(events,line)) {
            if(line.find("linear_iteration_limit_residual solve=2 ")!=0&&
               line.find("linear_residual solve=3 ")!=0) continue;
            auto value=[&](const std::string& key) {
                const auto pos=line.find(" "+key+"=");
                const auto invalid=std::numeric_limits<double>::quiet_NaN();
                if(pos==std::string::npos) return invalid;
                const auto begin=pos+key.size()+2;
                const auto end=line.find(' ',begin);
                const char* last=line.data()+(end==std::string::npos?line.size():end);
                double number=0;
                const auto parsed=std::from_chars(line.data()+begin,last,number);
                return parsed.ec==std::errc{}&&parsed.ptr==last&&std::isfinite(number)?number:invalid;
            };
            const double eta=value("requested_rtol"),rhs=value("rhs_norm"),limit=value("limit");
            const bool valid=line.find("protocol_hash="+protocol+" ")!=std::string::npos&&
                value("step")==1&&value("attempt")==1&&value("forcing")==1&&value("base_rtol")==1e-12&&
                value("requested_atol")==1e-14&&limit==std::max(1e-14,eta*rhs);
            if(line.find("linear_iteration_limit_residual")==0) {
                failed_rhs=rhs;
                exhausted=valid&&value("pc_attempt")==1&&value("newton")==2&&eta==1e-3&&
                    value("ksp_reason")==KSP_DIVERGED_ITS&&value("ksp_iterations")==2&&value("norm")>limit;
            } else {
                restarted=valid&&exhausted&&rhs==failed_rhs&&value("pc_attempt")==2&&value("newton")==1&&
                    eta==1e-4&&value("ksp_reason")>0&&value("ksp_reason")!=KSP_CONVERGED_ITS&&
                    value("ksp_iterations")>0&&value("ksp_iterations")<=2&&value("norm")<=limit;
            }
            std::cout<<line<<'\n';
        }
    }
    check(comm,rank!=0||(exhausted&&restarted),"Failed KSP gate or first retry forcing disagrees with its receipt");
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
