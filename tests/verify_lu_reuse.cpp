/** Stale LU is only a preconditioner: changing operators, factor counts and failure invalidation. */
#include "eonsim/nonlinear_system.hpp"
#include <petsclog.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
int factorizations()
{
    PetscLogEvent event;
    EONSIM_PETSC(PetscLogEventGetId("MatLUFactorNum",&event));
    require(event>=0,"Missing independent LU numeric-factorization event");
    PetscEventPerfInfo info;
    EONSIM_PETSC(PetscLogEventGetPerfInfo(0,event,&info));
    return info.count;
}
void verify(MPI_Comm comm)
{
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    require(ranks==1||ranks==2||ranks==4,"Use1/2/4 ranks");
    AlgebraLayout l;
    l.global=3; const PetscInt chunk=(3+ranks-1)/ranks;
    l.begin=std::min<PetscInt>(3,rank*chunk); l.owned=std::min<PetscInt>(chunk,3-l.begin);
    l.fields["state"]={};
    for(PetscInt row=l.begin;row<l.begin+l.owned;++row) { l.local_to_global.push_back(row); l.fields["state"].push_back(row); }
    for(PetscInt row=0;row<3;++row) if(row<l.begin||row>=l.begin+l.owned) l.local_to_global.push_back(row);
    l.diagonal.assign(l.owned,l.owned); l.off_diagonal.assign(l.owned,3-l.owned);
    PetscInt index[3]; for(std::size_t i=0;i<3;++i) index[l.local_to_global[i]]=i;
    SolverConfig config; config.absolute_tolerance=1e-12; config.relative_tolerance=1e-12;
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_factor_mat_solver_type","mumps"));
    for(bool coo:{false,true}) {
        NonlinearSystem system(comm,l);
        if(coo) {
            std::vector<PetscInt> rows,columns;
            for(PetscInt row=l.begin;row<l.begin+l.owned;++row) for(PetscInt col=0;col<3;++col) { rows.push_back(row); columns.push_back(col); }
            system.set_jacobian_coo(rows,columns);
        }
        int phase=0; bool fail=false; double target[3]{};
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            if(j&&fail&&rank==ranks-1) throw std::runtime_error("deliberate cached-PC callback failure");
            const PetscInt columns[]={0,1,2};
            for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
                const PetscInt next=(row+1)%3;
                const double u=x[index[row]],v=x[index[next]],diagonal=2.3+row+.3*phase;
                const double residual=diagonal*(u-target[row])+.1*(v-target[next])+.2*(u*u*u-target[row]*target[row]*target[row]);
                EONSIM_PETSC(VecSetValue(r,row,residual,ADD_VALUES));
                if(j) {
                    double entries[3]{}; entries[row]=diagonal+.6*u*u; entries[next]=.1;
                    if(coo) std::copy(entries,entries+3,system.jacobian_coo_values()+3*(row-l.begin));
                    else EONSIM_PETSC(MatSetValues(j,1,&row,3,columns,entries,ADD_VALUES));
                }
            }
        };
        const auto solve=[&](PetscInt window,bool exact_initial=false,bool refresh=false) {
            target[0]=.1+.03*phase;target[1]=.2-.01*phase;target[2]=-.15+.02*phase;
            std::vector<double> initial(3,0);
            if(exact_initial) for(int row=0;row<3;++row) initial[index[row]]=target[row];
            const auto result=system.solve(config,initial,{}, {},assemble,window,refresh);
            for(int row=0;row<3;++row) require(std::abs(result.values[index[row]]-target[row])<2e-11,"Stale factors changed the exact current-system solution");
            require(result.residual_norm<2e-11,"Current true nonlinear residual did not converge");
            return result;
        };
        for(phase=0;phase<4;++phase) {
            const int before=factorizations();const auto result=solve(3);const int count=factorizations()-before;
            if(rank==0) std::cout<<"factor_count coo="<<coo<<" phase="<<phase<<" numeric="<<count<<std::endl;
            require(count==(phase%3==0?1:0),"Actual LU factorization count violates reuse/rebuild policy");
            require(result.reused_lu_preconditioner==(phase%3!=0),"Reuse reporting disagrees with actual factors");
            require(result.lu_preconditioner_uses==phase%3+1,"Incorrect successful factor-use count");
        }
        // An exactly solved input must neither build nor consume a factor use.
        const int before_zero=factorizations();const auto zero=solve(3,true);
        require(zero.linear_iterations==0&&factorizations()==before_zero&&zero.lu_preconditioner_uses==1,"Exact initial state caused unnecessary factorization");
        // An explicit request on one rank, even the empty owner at four ranks,
        // must rebuild everywhere and then permit ordinary reuse again.
        ++phase;const int before_refresh=factorizations();const auto refreshed=solve(3,false,rank==ranks-1);
        require(!refreshed.reused_lu_preconditioner&&refreshed.lu_preconditioner_uses==1&&factorizations()-before_refresh==1,"One-rank refresh did not collectively rebuild");
        ++phase;const int after_refresh=factorizations();const auto reused=solve(3);
        require(reused.reused_lu_preconditioner&&reused.lu_preconditioner_uses==2&&factorizations()==after_refresh,"Explicit refresh disabled later reuse");
        // A one-rank options change must invalidate the factor on every rank.
        if(rank==0) EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-eonsim_cache_test","changed"));
        ++phase; const int before_options=factorizations();const auto changed=solve(3);
        require(!changed.reused_lu_preconditioner&&factorizations()-before_options==1,"Options change did not collectively rebuild");
        if(rank==0) EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-eonsim_cache_test"));
        ++phase;solve(3);
        // Reject differing policies collectively, then recover with fresh factors.
        bool rejected=false;
        try { solve(ranks>1?(rank==0?2:3):-1); } catch(const std::runtime_error&) { rejected=true; }
        require(rejected,"Invalid/rank-dependent reuse policy was accepted");
        ++phase;const auto after_policy=solve(3);require(!after_policy.reused_lu_preconditioner,"Invalid policy retained a factor");
        // Failed callbacks may leave a trial Vec locked inside PETSc; the usual
        // vector replacement and this new PC invalidation must both recover.
        fail=true;rejected=false;
        try { solve(3); } catch(const std::runtime_error&) { rejected=true; }
        fail=false;require(rejected,"Rank-local callback failure did not propagate");
        ++phase;const int before_recovery=factorizations();const auto recovered=solve(3);
        require(!recovered.reused_lu_preconditioner&&factorizations()-before_recovery==1,"Failure recovery reused stale execution state");
        for(const char* option:{"-ksp_type","-snes_lag_preconditioner"}) {
            EONSIM_PETSC(PetscOptionsSetValue(nullptr,option,std::string(option)=="-ksp_type"?"preonly":"1"));
            rejected=false;try { solve(3); } catch(const std::runtime_error&) { rejected=true; }
            EONSIM_PETSC(PetscOptionsClearValue(nullptr,option));require(rejected,"Incompatible solve/lag option was accepted");
            ++phase;require(!solve(3).reused_lu_preconditioner,"Rejected options retained cached factors");
        }
        ++phase;const auto disabled=solve(0);require(!disabled.reused_lu_preconditioner&&disabled.lu_preconditioner_uses==0,"Disabled policy retained LU");
        ++phase;require(!solve(3).reused_lu_preconditioner,"Re-enabling reused a discarded factor");
        ++phase;const auto resized=solve(2);require(!resized.reused_lu_preconditioner&&resized.lu_preconditioner_uses==1,"Changed window did not rebuild");
    }
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_factor_mat_solver_type"));
    if(rank==0) std::cout<<"Current nonlinear operators, independent LU counts, empty owner, COO, invalidation and recovery passed on "<<ranks<<" ranks\n";
}
}
int main(int argc,char** argv)
{
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try {
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        EONSIM_PETSC(PetscLogDefaultBegin());verify(PETSC_COMM_WORLD);
        EONSIM_PETSC(PetscPopErrorHandler());
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n';MPI_Abort(PETSC_COMM_WORLD,1); }
    return PetscFinalize();
}
