#include "eonsim/schur_solver.hpp"
#include <algorithm>
#include <cstring>
#include <stdexcept>
namespace eonsim {
namespace {
void option_default(const std::string& name,const char* value) {
    PetscBool found=PETSC_FALSE; EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
void multigrid(KSP solver) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCGAMG));
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    // 避免多个 SuperLU_DIST 子因子的 communicator 问题；粗层使用迭代解。
    option_default(base+"mg_coarse_ksp_type","gmres"); option_default(base+"mg_coarse_pc_type","jacobi");
    option_default(base+"mg_coarse_ksp_rtol","1e-10"); option_default(base+"mg_coarse_ksp_max_it","200");
    // MG 默认粗层不算残差范数；迭代粗解必须启用真实收敛判断。
    option_default(base+"mg_coarse_ksp_norm_type","unpreconditioned");
    EONSIM_PETSC(KSPSetFromOptions(solver));
}
void split_is(MPI_Comm comm,PC pc,const char* name,const std::vector<PetscInt>& rows) {
    PetscOwner<IS,ISDestroy> is; EONSIM_PETSC(ISCreateGeneral(comm,rows.size(),rows.data(),PETSC_COPY_VALUES,is.put()));
    EONSIM_PETSC(PCFieldSplitSetIS(pc,name,is.get()));
}
void schur(MPI_Comm comm,KSP solver,const std::vector<PetscInt>& velocity,const std::vector<PetscInt>& pressure) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_SCHUR));
    EONSIM_PETSC(PCFieldSplitSetSchurFactType(pc,PC_FIELDSPLIT_SCHUR_FACT_FULL));
    EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,PC_FIELDSPLIT_SCHUR_PRE_SELFP,nullptr));
    split_is(comm,pc,"velocity",velocity); split_is(comm,pc,"pressure",pressure);
    EONSIM_PETSC(PCSetUp(pc));
    PetscInt n=0; KSP* sub=nullptr; EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&n,&sub));
    if(n!=2) { PetscFree(sub); throw std::runtime_error("Schur requires two fields"); }
    for(PetscInt i=0;i<n;++i) multigrid(sub[i]);
    EONSIM_PETSC(PetscFree(sub));
}
}
void configure_schur_solver(MPI_Comm comm,KSP solver,const AlgebraLayout& layout,Mat matrix)
{
    if(!layout.fields.count("velocity")||!layout.fields.count("pressure")) throw std::runtime_error("Schur solver requires velocity and pressure fields");
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    if(layout.fields.size()==2) { schur(comm,solver,layout.fields.at("velocity"),layout.fields.at("pressure")); return; }
    auto fields=layout.fields;
    auto& flow=fields["flow"]; flow=fields.at("velocity"); flow.insert(flow.end(),fields.at("pressure").begin(),fields.at("pressure").end()); std::sort(flow.begin(),flow.end());
    fields.erase("velocity"); fields.erase("pressure");
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_MULTIPLICATIVE));
    for(const auto& field:fields) split_is(comm,pc,field.first.c_str(),field.second);
    EONSIM_PETSC(PCSetUp(pc));
    PetscInt count=0; KSP* sub=nullptr; EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&count,&sub));
    PetscInt offset=0,owned=flow.size();
    if(MPI_Exscan(&owned,&offset,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS) throw std::runtime_error("Flow split numbering failed");
    int rank=0; MPI_Comm_rank(comm,&rank); if(rank==0) offset=0;
    std::vector<PetscInt> velocity,pressure;
    for(PetscInt i=0;i<owned;++i) {
        const auto& p=layout.fields.at("pressure");
        (std::binary_search(p.begin(),p.end(),flow[i])?pressure:velocity).push_back(offset+i);
    }
    int i=0;
    for(const auto& field:fields) {
        if(field.first=="flow") {
            EONSIM_PETSC(KSPSetType(sub[i],KSPPREONLY)); schur(comm,sub[i],velocity,pressure);
        } else if(field.first=="rigid") {
            PC scalar; EONSIM_PETSC(KSPSetType(sub[i],KSPPREONLY)); EONSIM_PETSC(KSPGetPC(sub[i],&scalar)); EONSIM_PETSC(PCSetType(scalar,PCJACOBI));
        } else multigrid(sub[i]);
        ++i;
    }
    EONSIM_PETSC(PetscFree(sub));
}
}
