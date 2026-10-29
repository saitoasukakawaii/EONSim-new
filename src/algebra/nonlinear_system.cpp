#include "eonsim/nonlinear_system.hpp"
#include "eonsim/schur_solver.hpp"
#include "eonsim/time_step.hpp"
#include <cmath>
#include <stdexcept>
#include <iostream>
#include <chrono>
#include <cstring>
#include <algorithm>
#if defined(__linux__)
#include <sys/resource.h>
#endif
namespace eonsim {
namespace {
std::vector<double> local_values(Vec x)
{
    EONSIM_PETSC(VecGhostUpdateBegin(x,INSERT_VALUES,SCATTER_FORWARD));
    EONSIM_PETSC(VecGhostUpdateEnd(x,INSERT_VALUES,SCATTER_FORWARD));
    Vec local; const PetscScalar* a; PetscInt n;
    EONSIM_PETSC(VecGhostGetLocalForm(x,&local));
    EONSIM_PETSC(VecGetLocalSize(local,&n));
    EONSIM_PETSC(VecGetArrayRead(local,&a));
    std::vector<double> values(a,a+n);
    EONSIM_PETSC(VecRestoreArrayRead(local,&a));
    EONSIM_PETSC(VecGhostRestoreLocalForm(x,&local));
    return values;
}
struct Context {
    MPI_Comm comm;
    const AlgebraLayout& layout;
    const std::vector<PetscInt>& constraints;
    const std::vector<double>& prescribed;
    const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble;
    Vec scratch;
    std::string error;
    bool recoverable=false;
    double assembly_seconds=0,ghost_seconds=0;
    void evaluate(Vec x, Vec r, Mat j, bool constrain) {
        const auto begin=std::chrono::steady_clock::now();
        const auto values=local_values(x);
        ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
        EONSIM_PETSC(VecSetOption(r,VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
        EONSIM_PETSC(VecSet(r,0));
        if(j) EONSIM_PETSC(MatZeroEntries(j));
        int failed=0, any_failed=0;
        error.clear(); recoverable=false;
        try { assemble(values,r,j); }
        catch(const StepRejected& e) { error=e.what(); failed=1; }
        catch(const std::exception& e) { error=e.what(); failed=2; }
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
        if(any_failed==1) { recoverable=true; throw StepRejected(error.empty()?"Trial state rejected on another rank":error); }
        if(any_failed) throw std::runtime_error(error.empty() ? "Assembly failed on another rank" : error);
        EONSIM_PETSC(VecAssemblyBegin(r)); EONSIM_PETSC(VecAssemblyEnd(r));
        if(j) { EONSIM_PETSC(MatAssemblyBegin(j,MAT_FINAL_ASSEMBLY)); EONSIM_PETSC(MatAssemblyEnd(j,MAT_FINAL_ASSEMBLY)); }
        if(constrain) {
            std::vector<double> bc(constraints.size());
            for(std::size_t i=0;i<bc.size();++i) bc[i]=values.at(constraints[i]-layout.begin)-prescribed[i];
            EONSIM_PETSC(VecSetValues(r,bc.size(),constraints.data(),bc.data(),INSERT_VALUES));
            EONSIM_PETSC(VecAssemblyBegin(r)); EONSIM_PETSC(VecAssemblyEnd(r));
            if(j) EONSIM_PETSC(MatZeroRows(j,constraints.size(),constraints.data(),1,nullptr,nullptr));
        }
        assembly_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
    }
};
PetscErrorCode function(SNES,Vec x,Vec r,void* pointer)
{
    auto& c=*static_cast<Context*>(pointer);
    try { c.evaluate(x,r,nullptr,true); return PETSC_SUCCESS; }
    catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
PetscErrorCode jacobian(SNES,Vec x,Mat j,Mat,void* pointer)
{
    auto& c=*static_cast<Context*>(pointer);
    try { c.evaluate(x,c.scratch,j,true); return PETSC_SUCCESS; }
    catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
}
NonlinearResult solve_nonlinear(MPI_Comm comm,const AlgebraLayout& l,const SolverConfig& config,
    const std::vector<double>& initial,const std::vector<PetscInt>& constraints,
    const std::vector<double>& prescribed,const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble)
{
    if(initial.size()!=l.local_to_global.size() || constraints.size()!=prescribed.size())
        throw std::runtime_error("Invalid nonlinear state/constraint layout");
    PetscOwner<Vec,VecDestroy> x,r,scratch;
    PetscOwner<Mat,MatDestroy> j;
    PetscOwner<SNES,SNESDestroy> snes;
    const auto ghosts=l.local_to_global.size()-l.owned;
    EONSIM_PETSC(VecCreateGhost(comm,l.owned,l.global,ghosts,l.local_to_global.data()+l.owned,x.put()));
    EONSIM_PETSC(VecDuplicate(x.get(),r.put())); EONSIM_PETSC(VecDuplicate(x.get(),scratch.put()));
    EONSIM_PETSC(VecSetOption(r.get(),VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
    EONSIM_PETSC(VecSetOption(scratch.get(),VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
    PetscScalar* a;
    EONSIM_PETSC(VecGetArray(x.get(),&a));
    for(PetscInt i=0;i<l.owned;++i) a[i]=initial[i];
    for(std::size_t i=0;i<constraints.size();++i) {
        if(constraints[i]<l.begin || constraints[i]>=l.begin+l.owned) throw std::runtime_error("Constraint is not owned");
        a[constraints[i]-l.begin]=prescribed[i];
    }
    EONSIM_PETSC(VecRestoreArray(x.get(),&a));
    EONSIM_PETSC(MatCreateAIJ(comm,l.owned,l.owned,l.global,l.global,0,l.diagonal.data(),0,l.off_diagonal.data(),j.put()));
    EONSIM_PETSC(MatSetOption(j.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    EONSIM_PETSC(MatSetOption(j.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
    Context context{comm,l,constraints,prescribed,assemble,scratch.get(),{}};
    EONSIM_PETSC(SNESCreate(comm,snes.put()));
    EONSIM_PETSC(SNESSetFunction(snes.get(),r.get(),function,&context));
    EONSIM_PETSC(SNESSetJacobian(snes.get(),j.get(),j.get(),jacobian,&context));
    EONSIM_PETSC(SNESSetTolerances(snes.get(),config.absolute_tolerance,config.relative_tolerance,0,config.maximum_iterations,10000));
    KSP ksp; PC pc;
    EONSIM_PETSC(SNESGetKSP(snes.get(),&ksp)); EONSIM_PETSC(KSPGetPC(ksp,&pc));
    EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCLU));
    EONSIM_PETSC(PCFactorSetMatSolverType(pc,MATSOLVERSUPERLU_DIST));
    PetscBool block=PETSC_FALSE,schur=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-schur_pc",&schur,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-block_pc",&block,nullptr));
    if(block&&schur) throw std::runtime_error("Choose block_pc or schur_pc");
    if(block||schur) {
        EONSIM_PETSC(KSPSetType(ksp,KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(ksp,1e-9,1e-13,PETSC_DEFAULT,500));
        EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
        EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_MULTIPLICATIVE));
    }
    EONSIM_PETSC(SNESSetFromOptions(snes.get()));
    PCType type; EONSIM_PETSC(PCGetType(pc,&type));
    if(!schur&&std::strcmp(type,PCFIELDSPLIT)==0) {
        auto fields=l.fields;
        if(fields.count("velocity")&&fields.count("pressure")) {
            fields["flow"]=fields.at("velocity");
            fields["flow"].insert(fields["flow"].end(),fields.at("pressure").begin(),fields.at("pressure").end());
            std::sort(fields["flow"].begin(),fields["flow"].end());
            fields.erase("velocity"); fields.erase("pressure");
        }
        for(const auto& field:fields) {
            PetscOwner<IS,ISDestroy> is;
            EONSIM_PETSC(ISCreateGeneral(comm,field.second.size(),field.second.data(),PETSC_COPY_VALUES,is.put()));
            EONSIM_PETSC(PCFieldSplitSetIS(pc,field.first.c_str(),is.get()));
            if(block) {
                auto option_default=[&](const std::string& suffix,const char* value) {
                    const auto name="-fieldsplit_"+field.first+"_"+suffix;
                    PetscBool found=PETSC_FALSE;
                    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
                    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
                };
                option_default("ksp_type","preonly");
                // 本机 PETSc/SuperLU_DIST 多个同时存活的 LU 因子在析构时出现 communicator
                // use-after-free；分块基线采用 ASM + 局部 ILU，整体直接解仍单独可用。
                option_default("pc_type",field.first=="rigid"?"jacobi":"asm");
                if(field.first!="rigid") {
                    option_default("sub_ksp_type","preonly");
                    option_default("sub_pc_type","ilu");
                }
            }
        }
    }
    const auto solve_begin=std::chrono::steady_clock::now();
    if(schur) {
        context.evaluate(x.get(),r.get(),j.get(),true);
        configure_schur_solver(comm,ksp,l,j.get());
    }
    const auto error=SNESSolve(snes.get(),nullptr,x.get());
    const double solve_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-solve_begin).count();
    const double assembly_seconds=context.assembly_seconds,ghost_seconds=context.ghost_seconds;
    if(error&&context.recoverable) throw StepRejected(context.error);
    if(error && !context.error.empty()) throw std::runtime_error(context.error);
    EONSIM_PETSC(error);
    SNESConvergedReason reason; EONSIM_PETSC(SNESGetConvergedReason(snes.get(),&reason));
    if(reason<=0) throw StepRejected("SNES did not converge: reason="+std::to_string(reason));
    NonlinearResult result;
    context.evaluate(x.get(),r.get(),nullptr,true);
    EONSIM_PETSC(VecNorm(r.get(),NORM_2,&result.residual_norm));
    if(!std::isfinite(result.residual_norm)) throw std::runtime_error("Nonfinite nonlinear residual");
    result.values=local_values(x.get());
    context.evaluate(x.get(),r.get(),nullptr,false);
    result.raw_residual=local_values(r.get());
    EONSIM_PETSC(SNESGetIterationNumber(snes.get(),&result.iterations));
    EONSIM_PETSC(SNESGetLinearSolveIterations(snes.get(),&result.linear_iterations));
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-solver_report",&report,nullptr));
    if(report) {
        MatInfo info; EONSIM_PETSC(MatGetInfo(j.get(),MAT_GLOBAL_SUM,&info));
        PetscLogDouble memory=0; EONSIM_PETSC(PetscMemoryGetCurrentUsage(&memory));
        double peak=memory;
#if defined(__linux__)
        struct rusage usage{};
        if(getrusage(RUSAGE_SELF,&usage)!=0) throw std::runtime_error("Cannot read peak RSS");
        peak=1024.0*usage.ru_maxrss;
#endif
        double local[]={solve_seconds,assembly_seconds,ghost_seconds,memory,peak},maxima[5]{};
        MPI_Allreduce(local,maxima,5,MPI_DOUBLE,MPI_MAX,comm);
        double memory_sum=0; MPI_Allreduce(&memory,&memory_sum,1,MPI_DOUBLE,MPI_SUM,comm);
        double peak_sum=0; MPI_Allreduce(&peak,&peak_sum,1,MPI_DOUBLE,MPI_SUM,comm);
        int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
        KSPType kt; EONSIM_PETSC(KSPGetType(ksp,&kt));
        EONSIM_PETSC(PCGetType(pc,&type));
        if(rank==0) std::cout << "solver_report ranks=" << ranks << " dofs=" << l.global << " nnz=" << info.nz_used
            << " ksp=" << kt << " pc=" << type << " linear_iterations=" << result.linear_iterations
            << " solve_seconds=" << maxima[0] << " assembly_seconds=" << maxima[1] << " ghost_seconds=" << maxima[2]
            << " rss_max_bytes=" << maxima[3] << " rss_sum_bytes=" << memory_sum
            << " peak_rss_max_bytes=" << maxima[4] << " peak_rss_sum_bytes=" << peak_sum << '\n';
    }
    return result;
}
}
