/** Exact matrix-free Newton action: independent nonlinear root, off-rank
 * contributions, constraints, frozen linearizations, P lag and failure recovery. */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/deflated_fgmres.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
void option(const char* key,const char* value) { EONSIM_PETSC(PetscOptionsSetValue(nullptr,key,value)); }
struct ChangingPc { PetscInt applications=0; bool fail=false; };
PetscErrorCode changing_preconditioner(PC pc,Vec input,Vec output) {
    ChangingPc* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    ++state->applications; PetscCall(VecCopy(input,output));
    int rank=0,size=0; PetscCallMPI(MPI_Comm_rank(PetscObjectComm(reinterpret_cast<PetscObject>(pc)),&rank));
    PetscCallMPI(MPI_Comm_size(PetscObjectComm(reinterpret_cast<PetscObject>(pc)),&size));
    if(state->fail&&rank==size-1) { PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); return PETSC_SUCCESS; }
    // FGMRES must retain each actual right-preconditioned direction; applying
    // a fixed PC to a combined Arnoldi vector is deliberately incorrect here.
    PetscCall(VecScale(output,1.+.2*std::sin(double(state->applications))));
    return PETSC_SUCCESS;
}
void verify_deflated_space(MPI_Comm comm) {
    int rank=0,ranks=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    constexpr PetscInt size=12;
    // The first rank has no rows for every parallel invocation. It must still
    // participate in QR, SVD decisions and the projected PC applications.
    const PetscInt owned=ranks==1?size:rank==0?0:size/(ranks-1);
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,owned,owned,size,size,owned,nullptr,size-owned,nullptr,matrix.put()));
    PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(matrix.get(),&begin,&end));
    const auto assemble=[&](double change) {
        EONSIM_PETSC(MatZeroEntries(matrix.get()));
        for(PetscInt row=begin;row<end;++row) {
            const PetscScalar diagonal=row==0?.025+change:row==1?.07+change:1.+.23*row;
            EONSIM_PETSC(MatSetValue(matrix.get(),row,row,diagonal,INSERT_VALUES));
            EONSIM_PETSC(MatSetValue(matrix.get(),row,(row+1)%size,.017*(1+row%3),INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    };
    assemble(0.);
    PetscOwner<Vec,VecDestroy> exact,rhs,x,work,projected,coarse,correction;
    EONSIM_PETSC(MatCreateVecs(matrix.get(),exact.put(),rhs.put()));
    for(auto* vector:{&x,&work,&projected,&coarse,&correction}) EONSIM_PETSC(VecDuplicate(exact.get(),vector->put()));
    PetscOwner<KSP,KSPDestroy> solver; EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOperators(solver.get(),matrix.get(),matrix.get()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES)); EONSIM_PETSC(KSPSetPCSide(solver.get(),PC_RIGHT));
    EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),12));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-11,1e-13,PETSC_DEFAULT,120));
    PC original=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&original));
    ChangingPc changing_pc; EONSIM_PETSC(PCSetType(original,PCSHELL));
    EONSIM_PETSC(PCShellSetContext(original,&changing_pc));
    EONSIM_PETSC(PCShellSetApply(original,changing_preconditioner));
    configure_deflated_fgmres(solver.get(),2);
    PC wrapper=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&wrapper));
    require(deflated_fgmres_bulk_solver(wrapper)!=nullptr,"Deflation did not retain the configured PC");
    for(int generation=0;generation<3;++generation) {
        if(generation==2) assemble(.013); // Same graph, different current A.
        PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(exact.get(),&values));
        for(PetscInt row=begin;row<end;++row) values[row-begin]=.3+std::sin(.31*(row+1)+.1*generation);
        EONSIM_PETSC(VecRestoreArray(exact.get(),&values));
        EONSIM_PETSC(MatMult(matrix.get(),exact.get(),rhs.get()));
        prepare_deflated_fgmres(solver.get(),rhs.get(),x.get());
        if(generation) {
            // On range(C), the complete two-level preconditioner must be the
            // exact coarse inverse even while its base PC varies.
            EONSIM_PETSC(MatMult(matrix.get(),x.get(),coarse.get()));
            EONSIM_PETSC(PCApply(wrapper,coarse.get(),correction.get()));
            EONSIM_PETSC(VecAXPY(correction.get(),-1.,x.get()));
            PetscReal error=0,scale=0; EONSIM_PETSC(VecNorm(correction.get(),NORM_2,&error));
            EONSIM_PETSC(VecNorm(x.get(),NORM_2,&scale));
            require(error<2e-10*(1+scale),"Two-level deflation fails its exact coarse-image identity");
            EONSIM_PETSC(VecWAXPY(projected.get(),-1.,coarse.get(),rhs.get()));
            EONSIM_PETSC(PCApply(wrapper,projected.get(),correction.get()));
            EONSIM_PETSC(MatMult(matrix.get(),correction.get(),work.get()));
            PetscScalar coupling=0; EONSIM_PETSC(VecDot(coarse.get(),work.get(),&coupling));
            EONSIM_PETSC(VecNorm(work.get(),NORM_2,&scale));
            PetscReal coarse_norm=0; EONSIM_PETSC(VecNorm(coarse.get(),NORM_2,&coarse_norm));
            require(std::abs(coupling)<2e-10*(1+scale*coarse_norm),
                    "Right-deflated Krylov image reintroduced a removed coarse component");
            prepare_deflated_fgmres(solver.get(),rhs.get(),x.get());
        }
        EONSIM_PETSC(KSPSolve(solver.get(),rhs.get(),x.get()));
        KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(solver.get(),&reason));
        require(reason>0,"Deflated FGMRES with varying PC did not converge");
        EONSIM_PETSC(MatMult(matrix.get(),x.get(),work.get())); EONSIM_PETSC(VecAXPY(work.get(),-1.,rhs.get()));
        PetscReal error=0; EONSIM_PETSC(VecNorm(work.get(),NORM_2,&error));
        require(error<2e-10,"Deflated FGMRES failed independent original-operator residual");
        EONSIM_PETSC(VecCopy(x.get(),work.get())); EONSIM_PETSC(VecAXPY(work.get(),-1.,exact.get()));
        EONSIM_PETSC(VecNorm(work.get(),NORM_INFINITY,&error));
        require(error<2e-9,"Deflated FGMRES changed the manufactured discrete solution");
        complete_deflated_fgmres(solver.get(),x.get());
        DeflatedFgmresStats stats;
        require(query_deflated_fgmres_stats(wrapper,stats)&&stats.vectors>0&&stats.vectors<=2&&stats.spectral_updates==generation+1,
                "Bounded Krylov spectral extraction was not executed");
        if(generation) require(stats.projected_applications>0&&stats.projections>0,
                               "Recycling was only a warm start instead of projected FGMRES");
    }
    prepare_deflated_fgmres(solver.get(),rhs.get(),x.get());
    changing_pc.fail=true;
    EONSIM_PETSC(PCApply(wrapper,rhs.get(),correction.get()));
    PCFailedReason propagated=PC_NOERROR; EONSIM_PETSC(PCGetFailedReason(wrapper,&propagated));
    require(propagated==PC_SUBPC_ERROR,"Rank-local base-PC failure was not propagated before projected collectives");
    changing_pc.fail=false; EONSIM_PETSC(PCSetFailedReason(original,PC_NOERROR));
    prepare_deflated_fgmres(solver.get(),rhs.get(),x.get());
    EONSIM_PETSC(PCApply(wrapper,rhs.get(),correction.get()));
    EONSIM_PETSC(PCGetFailedReason(wrapper,&propagated));
    require(propagated==PC_NOERROR,"A fresh deflated generation retained a previous base-PC failure");
    EONSIM_PETSC(KSPSetType(solver.get(),KSPGMRES));
    bool rejected=false;
    try { configure_deflated_fgmres(solver.get(),2); }
    catch(const std::runtime_error& e) { rejected=std::string(e.what()).find("right-preconditioned FGMRES")!=std::string::npos; }
    require(rejected,"Deflation accepted an unsupported nonflexible Krylov method");
    if(rank==0) std::cout<<"deflated_fgmres_oracle ranks="<<ranks<<" empty_owner="<<(ranks>1)
        <<" varying_pc_applications="<<changing_pc.applications<<" generations=3 passed=1\n";
}
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
    double target_shift=0.;
    const auto target=[&](int i) {return 1.+.25*i+(i<3?target_shift:0.);};
    const PetscInt ids[]{0,1,2,3};
    SolverConfig settings; settings.relative_tolerance=1e-12; settings.absolute_tolerance=1e-12;
    settings.maximum_iterations=20;
    option("-pc_type","jacobi"); option("-ksp_rtol","1e-12"); option("-ksp_atol","1e-14");
    option("-ksp_max_it","100"); option("-ksp_pc_side","right");
    option("-ksp_norm_type","unpreconditioned"); option("-nonlinear_matrix_free_pc_interval","2");
    option("-nonlinear_true_residual","true");
    for(const char* method:{"fgmres","pipefgmres"}) for(const bool residual_coo:{false,true}) {
        option("-ksp_type",method);
        NonlinearSystem system(comm,layout);
        // Replacing a locked function target after a failed MatShell action
        // must rebuild its residual COO plan, including empty producer ranks.
        if(residual_coo)
            system.set_residual_coo(rank==ranks-1?std::vector<PetscInt>(ids,ids+4):std::vector<PetscInt>{});
        PetscInt tangent_calls=0,action_calls=0;
        PetscInt fail_action=-1;
        PetscInt assemblies_after_failure=0;
        bool action_failed=false;
        bool failure_in_owned=false,fail_prepare=false;
        std::vector<double> frozen;
        const auto assemble=[&](const std::vector<double>& x,Vec residual,Mat matrix) {
            if(action_failed) ++assemblies_after_failure;
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
            if(residual_coo) std::copy_n(values,4,system.residual_coo_values());
            else EONSIM_PETSC(VecSetValues(residual,4,ids,values,ADD_VALUES));
            if(matrix) EONSIM_PETSC(MatSetValues(matrix,4,ids,4,ids,jacobian,ADD_VALUES));
        };
        NonlinearAssemblyPhases phases;
        phases.prepare_jacobian_action=[&](const std::vector<double>& x) {
            if(fail_prepare&&rank==ranks-1) throw std::runtime_error("injected frozen-state setup failure");
            frozen=x;
        };
        phases.jacobian_action=[&](const std::vector<double>& x,const std::vector<double>& direction,Vec result) {
            require(x==frozen,"Stale frozen-state cache reached matrix-free action");
            ++action_calls;
            if(rank!=ranks-1) return;
            double values[4]{};
            for(int i=0;i<4;++i) {
                values[i]=2*(i+2)*x[local[i]]*direction[local[i]];
                for(int j=0;j<4;++j) values[i]+=coupling[i][j]*direction[local[j]];
            }
            EONSIM_PETSC(VecSetValues(result,4,ids,values,ADD_VALUES));
            if(action_calls==fail_action) {
                action_failed=true;
                throw std::runtime_error("injected directional failure after off-rank insertion");
            }
        };
        if(residual_coo) {
            const auto apply_phase=[&](const std::vector<double>& x,const std::vector<double>& direction,Vec result,bool owned) {
                require(x==frozen,"Phased action used a stale frozen-state cache");
                if(owned) ++action_calls;
                if(rank!=ranks-1) return;
                double values[4]{};
                for(int i=0;i<4;++i) {
                    if((local[i]<layout.owned)==owned)
                        values[i]=2*(i+2)*x[local[i]]*direction[local[i]];
                    for(int j=0;j<4;++j) if((local[j]<layout.owned)==owned)
                        values[i]+=coupling[i][j]*direction[local[j]];
                }
                EONSIM_PETSC(VecSetValues(result,4,ids,values,ADD_VALUES));
                if(action_calls==fail_action&&owned==failure_in_owned) {
                    action_failed=true;
                    throw std::runtime_error("injected directional failure after off-rank insertion");
                }
            };
            // Keep the local dispatcher alive for the callbacks below.
            // Copying it copies only references to this enclosing solve scope.
            phases.jacobian_action_owned=[apply_phase](const auto& x,const auto& d,Vec r) {apply_phase(x,d,r,true);};
            phases.jacobian_action_halo=[apply_phase](const auto& x,const auto& d,Vec r) {apply_phase(x,d,r,false);};
        }
        const auto solve=[&] {return system.solve(settings,initial,constraints,prescribed,assemble,phases);};
        const auto check=[&](const NonlinearResult& result) {
            for(int i=0;i<4;++i) {
                require(std::abs(result.values[local[i]]-target(i))<2e-11,"Matrix-free Newton differs from independent exact root");
                require(std::abs(result.raw_residual[local[i]]-(i==3?7.:0.))<2e-10,"Matrix-free solve changed physical reaction");
            }
            require(result.matrix_free_actions>0&&result.assembled_pc_reuses>0,"Matrix-free action or assembled P reuse was not exercised");
            require(result.true_residual_checks>0,"Current-operator convergence verification was not exercised");
            require(result.jacobian_assemblies<result.jacobian_callbacks,"P was assembled for every matrix-free correction");
            require(result.field_residuals[0].equation_rows==3,"Constraint entered the physical field norm");
            require(result.matrix_free_preparations==result.jacobian_callbacks,"Frozen-state setup did not follow every current linearization");
            require((result.matrix_free_overlapped_actions>0)==residual_coo,"Exact action phase selection was ignored");
        };
        const auto first=solve(); check(first);
        const auto repeated=solve(); check(repeated);
        require(repeated.solver_reused,"Matrix-free session did not preserve its shell and ghost plan");
        auto generation=repeated.solver_generation;
        for(const PetscInt failure_offset:{1,2}) {
            // PIPEFGMRES's first action fills its pipeline. Its second action
            // runs with an outstanding split reduction, which must also drain
            // before this failed solve can be safely retried.
            fail_action=action_calls+failure_offset;
            failure_in_owned=failure_offset==1;
            bool caught=false;
            try { (void)solve(); }
            catch(const std::runtime_error& e) { caught=std::string(e.what()).find("injected directional failure")!=std::string::npos; }
            require(caught,"Rank-local directional failure did not propagate");
            require(assemblies_after_failure==0,"Fatal directional failure reached another physical assembly");
            fail_action=-1;
            action_failed=false;
            const auto recovered=solve(); check(recovered);
            require(!recovered.solver_reused&&recovered.solver_generation==generation+1,
                    "Failed matrix-free session was not retired");
            const auto recovered_repeated=solve(); check(recovered_repeated);
            require(recovered_repeated.solver_reused&&recovered_repeated.solver_generation==recovered.solver_generation,
                    "Recovered matrix-free session or residual plan was not reusable");
            generation=recovered_repeated.solver_generation;
        }
        fail_prepare=true;
        bool prepare_caught=false;
        try { (void)solve(); }
        catch(const std::runtime_error& e) {prepare_caught=std::string(e.what()).find("injected frozen-state setup failure")!=std::string::npos;}
        require(prepare_caught,"Frozen-state failure was not propagated collectively");
        fail_prepare=false;
        check(solve());
        if(!residual_coo) {
            option("-nonlinear_inexact_newton","true"); option("-nonlinear_krylov_recycle","2");
            const auto seeded=solve(); check(seeded);
            require(seeded.inexact_linear_solves>0&&seeded.recycle_vectors>0&&seeded.recycle_vectors<=2,
                    "Inexact forcing/recycled Krylov correction space was not exercised");
            target_shift=.035;
            const auto advanced=solve(); check(advanced);
            require(advanced.solver_reused&&advanced.recycle_projections>0,
                    "Recycled subspace did not cross the solve boundary with a changed RHS/operator");
            target_shift=0.;
            EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_matrix_free_pc_interval"));
            NonlinearSystem assembled_system(comm,layout);
            const auto assembled_first=assembled_system.solve(settings,initial,constraints,prescribed,assemble);
            target_shift=.021;
            const auto assembled_next=assembled_system.solve(settings,initial,constraints,prescribed,assemble);
            for(int i=0;i<4;++i)
                require(std::abs(assembled_next.values[local[i]]-target(i))<2e-11,
                        "Assembled inexact/recycled Newton changed the independent root");
            require(assembled_first.inexact_linear_solves>0&&assembled_next.recycle_projections>0&&assembled_next.solver_reused,
                    "Assembled solver did not retain its recycled correction space");
            target_shift=0.;
            option("-nonlinear_matrix_free_pc_interval","2");
            EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_inexact_newton"));
            EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_krylov_recycle"));
            if(std::string(method)=="fgmres") {
                option("-nonlinear_krylov_deflation","2");
                const auto seeded_deflation=solve(); check(seeded_deflation);
                target_shift=.017;
                const auto deflated_next=solve(); check(deflated_next);
                require(deflated_next.solver_reused&&deflated_next.deflation_vectors>0&&deflated_next.deflation_vectors<=2&&
                        deflated_next.deflation_projections>0&&deflated_next.deflation_applications>0&&
                        deflated_next.deflation_spectral_updates>0,
                        "Nonlinear driver failed to preserve actual deflation across current operators");
                target_shift=0.;
                fail_action=action_calls+1;
                bool deflated_failure=false;
                try { (void)solve(); }
                catch(const std::runtime_error& e) {deflated_failure=std::string(e.what()).find("injected directional failure")!=std::string::npos;}
                require(deflated_failure,"Failure during recycle-image refresh did not propagate");
                fail_action=-1; action_failed=false;
                const auto deflated_recovered=solve(); check(deflated_recovered);
                require(!deflated_recovered.solver_reused&&deflated_recovered.solver_generation==deflated_next.solver_generation+1,
                        "Failed deflated session retained its stale recycle space");
                EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_krylov_deflation"));
            }
        }
        require(tangent_calls>0&&action_calls>tangent_calls,"Exact actions did not avoid assembled P work");
        if(rank==0) std::cout<<"matrix_free_oracle method="<<method<<" residual_coo="<<residual_coo<<" ranks="<<ranks
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
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_matrix_free_pc_interval"));
    for(const auto& policy:std::vector<std::pair<const char*,const char*>>{
            {"-ksp_convergence_test","skip"},{"-ksp_converged_maxits","true"}}) {
        option(policy.first,policy.second);
        NonlinearSystem invalid(comm,layout);
        bool caught=false;
        try { invalid.solve(settings,initial,constraints,prescribed,[](const auto&,Vec,Mat){}); }
        catch(const std::runtime_error& e) {caught=std::string(e.what()).find("residual-based convergence")!=std::string::npos;}
        require(caught,"True residual guard accepted a convergence test that ignores residuals");
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,policy.first));
    }
    verify_deflated_space(comm);
}
}
int main(int argc,char** argv) {
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try { EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr)); verify(PETSC_COMM_WORLD);
          EONSIM_PETSC(PetscPopErrorHandler()); }
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1);}
    return PetscFinalize();
}
