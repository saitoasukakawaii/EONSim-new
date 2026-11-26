#include "eonsim/rcr_port_pc.hpp"
#include "eonsim/pc_plan.hpp"
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <vector>

using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool condition,const char* message) {
    int bad=!condition,any=0;
    MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}

// The reference eliminates the whole input matrix, without consulting the
// production port order, response vectors or small Schur factorization.
std::vector<double> reference_solve(const std::vector<double>& input_matrix,const std::vector<double>& input_rhs) {
    std::vector<long double> matrix(input_matrix.begin(),input_matrix.end());
    std::vector<long double> rhs(input_rhs.begin(),input_rhs.end());
    const auto n=rhs.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i)
            if(std::abs(matrix[i*n+k])>std::abs(matrix[pivot*n+k])) pivot=i;
        if(std::abs(matrix[pivot*n+k])<1e-14) throw std::runtime_error("Singular full-matrix reference");
        for(std::size_t j=k;j<n;++j) std::swap(matrix[k*n+j],matrix[pivot*n+j]);
        std::swap(rhs[k],rhs[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const long double multiplier=matrix[i*n+k]/matrix[k*n+k];
            for(std::size_t j=k;j<n;++j) matrix[i*n+j]-=multiplier*matrix[k*n+j];
            rhs[i]-=multiplier*rhs[k];
        }
    }
    for(std::size_t reverse=0;reverse<n;++reverse) {
        const auto i=n-1-reverse;
        for(std::size_t j=i+1;j<n;++j) rhs[i]-=matrix[i*n+j]*rhs[j];
        rhs[i]/=matrix[i*n+i];
    }
    return std::vector<double>(rhs.begin(),rhs.end());
}

struct Example {
    PetscInt n=0,begin=0,end=0;
    std::vector<PetscInt> ports,bulk;
    PetscOwner<Mat,MatDestroy> matrix;
    std::vector<double> dense,scaling;

    Example(MPI_Comm comm,PetscInt count,bool terminal,bool scaled=false) {
        int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
        n=8+count;
        ports=count==1?std::vector<PetscInt>{1}:count==3?std::vector<PetscInt>{1,6,10}:
            terminal?std::vector<PetscInt>{8,9}:std::vector<PetscInt>{1,6};
        scaling.assign(n,1.);
        if(scaled) { scaling[ports.front()]=1e-5;scaling[ports.back()]=1e5; }
        for(PetscInt i=0;i<n;++i)
            if(std::find(ports.begin(),ports.end(),i)==ports.end()) bulk.push_back(i);
        if(terminal&&size==2) { begin=rank==0?0:8; end=rank==0?8:n; }
        else if(terminal&&size==4) {
            // Rank 2 owns only ports; rank 3 owns no full-system rows.
            const PetscInt cuts[]={0,4,8,10,10}; begin=cuts[rank];end=cuts[rank+1];
        } else { begin=n*rank/size;end=n*(rank+1)/size; }
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,end-begin,nullptr,
                                n-end+begin,nullptr,matrix.put()));
        EONSIM_PETSC(MatSetOption(matrix.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
        fill(0);
    }

    void fill(int phase) {
        const auto k=ports.size();
        dense.assign(n*n,0.);
        const double shift=phase==1?.35:0.;
        for(std::size_t i=0;i<bulk.size();++i) {
            dense[bulk[i]*n+bulk[i]]=2.+.4*i+shift;
            for(std::size_t j=0;j<k;++j) {
                // The bottom coupling is deliberately not -U^T. The last two
                // bulk rows model ALE/mesh columns in a moving-port equation.
                const double u=(phase==2&&j==0)?0.:(.13+.027*i+.09*j)*(1.+shift);
                const double v=(phase==2&&j==0)?0.:(-.19-.013*i+.041*j)*(1.-.2*shift);
                dense[bulk[i]*n+ports[j]]=u;
                dense[ports[j]*n+bulk[i]]=v;
            }
        }
        for(std::size_t i=0;i<k;++i) for(std::size_t j=0;j<k;++j)
            dense[ports[i]*n+ports[j]]=i==j?(.7+.8*i+shift):(.035+.017*i-.021*j);
        if(k==3) {
            // Force a later (k=1) pivot with unequal already-stored L entries.
            // Swapping RHS during forward substitution instead of applying
            // the complete row permutation first gives a wrong result here.
            const double target[3][3]={{1,0,0},{.1,.01,1},{.2,1,.1}};
            for(std::size_t i=0;i<k;++i) for(std::size_t j=0;j<k;++j) {
                double d=target[i][j];
                for(const auto row:bulk)
                    d+=dense[ports[i]*n+row]*dense[row*n+ports[j]]/dense[row*n+row];
                dense[ports[i]*n+ports[j]]=d;
            }
        }
        // A change of port units produces twenty orders of magnitude in
        // port-table row scales without changing the mathematical coupling.
        for(PetscInt i=0;i<n;++i) for(PetscInt j=0;j<n;++j)
            dense[i*n+j]*=scaling[i]*scaling[j];
        publish();
    }

    void publish() {
        std::vector<PetscInt> columns(n);std::iota(columns.begin(),columns.end(),0);
        for(PetscInt i=begin;i<end;++i)
            EONSIM_PETSC(MatSetValues(matrix.get(),1,&i,n,columns.data(),dense.data()+i*n,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    }
};

void configure_diagonal(KSP solver,Mat matrix,PcSchurUpdates*) {
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(PCSetType(pc,PCJACOBI));
}

void verify_action(MPI_Comm comm,KSP solver,const Example& example,int sample) {
    PetscOwner<Vec,VecDestroy> rhs,solution,defect;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),solution.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(rhs.get(),defect.put()));
    std::vector<double> values(example.n);
    for(PetscInt i=0;i<example.n;++i)
        values[i]=example.scaling[i]*(sample==0?.3+.11*i:sample==1?std::sin(.7*(i+1)):
            (std::find(example.ports.begin(),example.ports.end(),i)!=example.ports.end()?1.+.2*i:0.));
    PetscScalar* local=nullptr; EONSIM_PETSC(VecGetArray(rhs.get(),&local));
    for(PetscInt i=example.begin;i<example.end;++i) local[i-example.begin]=values[i];
    EONSIM_PETSC(VecRestoreArray(rhs.get(),&local));
    const auto expected=reference_solve(example.dense,values);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetUp(solver));
    EONSIM_PETSC(PCApply(pc,rhs.get(),solution.get()));
    PCFailedReason pc_failure;EONSIM_PETSC(PCGetFailedReason(pc,&pc_failure));
    check(comm,pc_failure==PC_NOERROR,"Successful RCR application retained a prior PC failure");
    const PetscScalar* actual=nullptr; EONSIM_PETSC(VecGetArrayRead(solution.get(),&actual));
    bool exact=true;
    for(PetscInt i=example.begin;i<example.end;++i)
        exact=exact&&std::isfinite(actual[i-example.begin])&&
            std::abs(actual[i-example.begin]-expected[i])<2e-12*(1+std::abs(expected[i]));
    EONSIM_PETSC(VecRestoreArrayRead(solution.get(),&actual));
    EONSIM_PETSC(MatMult(example.matrix.get(),solution.get(),defect.get()));
    EONSIM_PETSC(VecAXPY(defect.get(),-1.,rhs.get()));
    PetscReal norm=0,rhsnorm=0; EONSIM_PETSC(VecNorm(defect.get(),NORM_2,&norm));
    EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&rhsnorm));
    check(comm,exact&&norm<3e-12*(1+rhsnorm),"RCR PCApply differs from independent full inverse");
    EONSIM_PETSC(VecSet(solution.get(),0.));
    EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason; PetscInt iterations=0;
    EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(KSPGetIterationNumber(solver,&iterations));
    EONSIM_PETSC(MatMult(example.matrix.get(),solution.get(),defect.get()));
    EONSIM_PETSC(VecAXPY(defect.get(),-1.,rhs.get()));
    EONSIM_PETSC(VecNorm(defect.get(),NORM_2,&norm));
    check(comm,reason>0&&iterations<=2&&norm<3e-12*(1+rhsnorm),
          "RCR wrapper failed exact-bulk FGMRES or independent residual");
}

void verify_adaptive(MPI_Comm comm) {
    Example example(comm,2,true);
    AlgebraLayout layout;
    layout.begin=example.begin;layout.owned=example.end-example.begin;layout.global=example.n;
    std::vector<PetscInt> local_position(example.n,-1);
    for(PetscInt i=example.begin;i<example.end;++i) {
        local_position[i]=static_cast<PetscInt>(layout.local_to_global.size());
        layout.local_to_global.push_back(i);
        DofKey key;key.entity=100+i;
        if(i==3||i>=8) {
            key.quantity=DofQuantity::pressure;
            if(i>=8) key.kind=DofEntity::boundary;
            layout.fields["pressure"].push_back(i);
        } else if(i>=6) {
            key.domain=DofDomain::mesh;key.quantity=DofQuantity::displacement;
            layout.fields["mesh"].push_back(i);
        } else if(i>=4) {
            key.domain=DofDomain::solid;
            layout.fields["structure"].push_back(i);
        } else layout.fields["velocity"].push_back(i);
        layout.owned_semantics.push_back(key);
    }
    for(PetscInt i=0;i<example.n;++i) if(local_position[i]<0) {
        local_position[i]=static_cast<PetscInt>(layout.local_to_global.size());
        layout.local_to_global.push_back(i);
    }
    for(const char* field:{"velocity","pressure","mesh","structure"}) layout.fields[field];
    layout.diagonal.assign(layout.owned,layout.owned);
    layout.off_diagonal.assign(layout.owned,layout.global-layout.owned);
    const std::vector<std::pair<const char*,const char*>> options{
        {"-pc_plan_rcr_ports","true"},{"-nonlinear_adaptive_pc","true"},
        {"-nonlinear_pc_max_reuse","2"},{"-nonlinear_pc_change_tolerance","0.05"},
        {"-nonlinear_pc_iteration_growth","100"},{"-ksp_rtol","1e-12"},{"-ksp_atol","1e-14"}};
    for(const auto& option:options) EONSIM_PETSC(PetscOptionsSetValue(nullptr,option.first,option.second));
    NonlinearSystem system(comm,layout);
    SolverConfig config;config.pc_recipe="hybrid";config.relative_tolerance=1e-10;config.absolute_tolerance=1e-12;
    NonlinearAssemblyPhases phases;phases.preconditioner_context={.1,.1};
    const std::vector<double> initial(layout.local_to_global.size(),0.);
    double drift=0;bool reject=false;int rank=0;MPI_Comm_rank(comm,&rank);
    const auto assembly=[&](const std::vector<double>& x,Vec residual,Mat jacobian) {
        if(reject&&rank==0) throw StepRejected("RCR cache rollback probe");
        for(PetscInt i=example.begin;i<example.end;++i) {
            double sum=0;
            for(PetscInt j=0;j<example.n;++j) {
                const double a=example.dense[i*example.n+j]+(i==j?drift*(i+1):0.);
                sum+=a*(x.at(local_position[j])-(.4+.2*j));
                if(jacobian) EONSIM_PETSC(MatSetValue(jacobian,i,j,a,ADD_VALUES));
            }
            EONSIM_PETSC(VecSetValue(residual,i,sum,ADD_VALUES));
        }
    };
    const auto solve=[&]() {
        auto result=system.solve(config,initial,{}, {},assembly,phases);
        bool exact=result.residual_norm<1e-9;
        for(PetscInt i=0;i<layout.owned;++i)
            exact=exact&&std::abs(result.values[i]-(.4+.2*(layout.begin+i)))<2e-10;
        check(comm,exact,"Adaptive RCR preconditioner changed full-system solution");
        return result;
    };
    const auto first=solve();
    check(comm,first.pc_refreshes==1&&first.pc_reuses==0,"Initial RCR preconditioner was not built");
    drift=1e-6;const auto reused=solve();
    check(comm,reused.pc_refreshes==0&&reused.pc_reuses==1&&reused.jacobian_assemblies==1,
          "Fresh RCR Jacobian did not retain the eligible low-rank PC");
    check(comm,reused.solver_reused&&reused.solver_generation==first.solver_generation&&
          reused.user_schur_updates==0&&reused.user_schur_updates<reused.jacobian_assemblies,
          "RCR adaptive reuse silently rebuilt its USER responses or solver generation");
    drift=2e-6;const auto reused_again=solve();
    check(comm,reused_again.pc_refreshes==0&&reused_again.pc_reuses==1,"Second RCR reuse was lost");
    const auto aged=solve();
    check(comm,aged.pc_refreshes==1&&aged.pc_age_refreshes==1,"RCR cache age did not force refresh");
    phases.preconditioner_context={.2,.2};const auto changed_time=solve();
    check(comm,changed_time.pc_refreshes==1&&changed_time.pc_context_refreshes==1,
          "Changed time coefficients did not invalidate the RCR low-rank cache");
    drift=.3;const auto changed_operator=solve();
    check(comm,changed_operator.pc_refreshes==1&&changed_operator.pc_drift_refreshes==1,
          "Large operator drift did not invalidate the RCR low-rank cache");
    reject=true;bool rejected=false;
    try { solve(); } catch(const StepRejected&) {rejected=true;}
    reject=false;check(comm,rejected,"RCR cache failure probe was accepted");
    const auto recovered=solve();
    check(comm,recovered.pc_refreshes==1&&recovered.pc_reuses==0&&
          recovered.solver_generation>changed_operator.solver_generation,
          "Rejected nonlinear state retained an old RCR response cache");
    EONSIM_PETSC(PetscPrintf(comm,
        "rcr_adaptive_verification reused_generation=%" PetscInt_FMT " fresh_jacobians=%" PetscInt_FMT
        " reused_user_updates=%" PetscInt_FMT " recovered_generation=%" PetscInt_FMT "\n",
        reused.solver_generation,reused.jacobian_assemblies+reused_again.jacobian_assemblies,
        reused.user_schur_updates+reused_again.user_schur_updates,recovered.solver_generation));
    for(const auto& option:options) EONSIM_PETSC(PetscOptionsClearValue(nullptr,option.first));
}

void run(MPI_Comm comm) {
    int size=0;MPI_Comm_size(comm,&size);
    check(comm,size==1||size==2||size==4,"Expected 1, 2 or 4 ranks");
    struct Case {PetscInt ports;bool terminal,scaled;};
    for(const auto spec:std::vector<Case>{{1,false,false},{2,false,false},{2,true,false},
                                         {3,false,false},{2,false,true}}) {
        Example example(comm,spec.ports,spec.terminal,spec.scaled);
        std::vector<PetscInt> local_ports;
        for(const auto row:example.ports) if(row>=example.begin&&row<example.end) local_ports.push_back(row);
        PcSchurUpdates updates;
        PetscOwner<KSP,KSPDestroy> solver; EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-13,1e-14,PETSC_DEFAULT,30));
        EONSIM_PETSC(KSPSetOperators(solver.get(),example.matrix.get(),example.matrix.get()));
        configure_rcr_port_pc(comm,solver.get(),example.matrix.get(),local_ports,configure_diagonal,&updates);
        PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
        for(int phase=0;phase<4;++phase) {
            if(phase) {example.fill(phase);updates.refresh(example.matrix.get());}
            for(int sample=0;sample<3;++sample) verify_action(comm,solver.get(),example,sample);
            RcrPortPcStats stats;
            check(comm,query_rcr_port_pc_stats(pc,stats)&&stats.ports==spec.ports&&
                  stats.rebuilds==phase+1&&stats.response_solves==spec.ports*(phase+1)&&
                  stats.setup_reductions==phase+1&&stats.applications>0&&
                  stats.apply_reductions==stats.applications,
                  "RCR cache rebuilt during apply or used more than one batched port reduction");
        }
        // Exact zero S, produced without reference to the implementation's
        // floating-point summation order. A failed rebuild must invalidate the
        // old usable factors until a successful collective refresh occurs.
        for(const auto row:example.ports) for(PetscInt col=0;col<example.n;++col) {
            example.dense[row*example.n+col]=0.;
            example.dense[col*example.n+row]=0.;
        }
        example.publish();
        bool rejected=false;
        try { updates.refresh(example.matrix.get()); }
        catch(const LinearSolveFailure&) { rejected=true; }
        check(comm,rejected,"Singular port Schur factor was not rejected collectively");
        PetscOwner<Vec,VecDestroy> rhs,solution;
        EONSIM_PETSC(MatCreateVecs(example.matrix.get(),solution.put(),rhs.put()));
        EONSIM_PETSC(VecSet(rhs.get(),1.));
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        const auto stale_error=PCApply(pc,rhs.get(),solution.get());
        EONSIM_PETSC(PetscPopErrorHandler());
        PCFailedReason failure; EONSIM_PETSC(PCGetFailedReason(pc,&failure));
        check(comm,stale_error!=0||failure!=PC_NOERROR,"Failed refresh reused old RCR factors");
        example.fill(0); updates.refresh(example.matrix.get());
        verify_action(comm,solver.get(),example,1);
        // Exercise the actual numerical failure flag, independently of the
        // not-ready error above. One owner's nonfinite port RHS is carried by
        // the same batched reduction to every rank and cannot be accepted.
        EONSIM_PETSC(VecSet(rhs.get(),1.));
        PetscScalar* data=nullptr; EONSIM_PETSC(VecGetArray(rhs.get(),&data));
        const auto port=example.ports.front();
        if(port>=example.begin&&port<example.end)
            data[port-example.begin]=std::numeric_limits<double>::quiet_NaN();
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&data));
        EONSIM_PETSC(PCApply(pc,rhs.get(),solution.get()));
        EONSIM_PETSC(PCGetFailedReason(pc,&failure));
        check(comm,failure==PC_SUBPC_ERROR,"Nonfinite port RHS did not propagate numerical PC failure");
        updates.refresh(example.matrix.get());
        EONSIM_PETSC(PCGetFailedReason(pc,&failure));
        check(comm,failure==PC_NOERROR,"Successful RCR refresh retained a failed root PC flag");
        verify_action(comm,solver.get(),example,0);
    }
    verify_adaptive(comm);
    EONSIM_PETSC(PetscPrintf(comm,
        "RCR single/multi-port full inverse, nontranspose coupling, port-only/empty ranks and refresh passed\n"));
}
}

int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try { run(PETSC_COMM_WORLD); }
    catch(const std::exception& failure) {
        std::cerr<<"RCR port verification failed: "<<failure.what()<<'\n'; result=1;
    }
    PetscFinalize(); return result;
}
