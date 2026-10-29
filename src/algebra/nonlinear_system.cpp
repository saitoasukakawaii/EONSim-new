#include "eonsim/nonlinear_system.hpp"
#include <cmath>
#include <stdexcept>
#include <iostream>
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
    void evaluate(Vec x, Vec r, Mat j, bool constrain) {
        const auto values=local_values(x);
        EONSIM_PETSC(VecSet(r,0));
        if(j) EONSIM_PETSC(MatZeroEntries(j));
        int failed=0, any_failed=0;
        try { assemble(values,r,j); }
        catch(const std::exception& e) { error=e.what(); failed=1; }
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
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
    EONSIM_PETSC(SNESSetFromOptions(snes.get()));
    const auto error=SNESSolve(snes.get(),nullptr,x.get());
    if(error && !context.error.empty()) throw std::runtime_error(context.error);
    EONSIM_PETSC(error);
    SNESConvergedReason reason; EONSIM_PETSC(SNESGetConvergedReason(snes.get(),&reason));
    if(reason<=0) throw std::runtime_error("SNES did not converge: reason="+std::to_string(reason));
    NonlinearResult result;
    context.evaluate(x.get(),r.get(),nullptr,true);
    EONSIM_PETSC(VecNorm(r.get(),NORM_2,&result.residual_norm));
    if(!std::isfinite(result.residual_norm)) throw std::runtime_error("Nonfinite nonlinear residual");
    result.values=local_values(x.get());
    context.evaluate(x.get(),r.get(),nullptr,false);
    result.raw_residual=local_values(r.get());
    EONSIM_PETSC(SNESGetIterationNumber(snes.get(),&result.iterations));
    EONSIM_PETSC(SNESGetLinearSolveIterations(snes.get(),&result.linear_iterations));
    return result;
}
}
