#include "eonsim/schur_solver.hpp"
#include <algorithm>
#include <cstring>
#include <stdexcept>
namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool good,const char* message) {
    int bad=!good,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Schur metadata validation communication failed");
    if(any) throw std::runtime_error(message);
}
bool velocity_block3(MPI_Comm comm,const AlgebraLayout& layout) {
    PetscBool enabled=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-schur_velocity_block3",&enabled,nullptr));
    int local=enabled,lo=0,hi=0;
    if(MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS ||
       MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Schur option validation communication failed");
    if(lo!=hi) throw std::runtime_error("Schur velocity block3 option differs between ranks");
    if(!enabled) return false;
    common_check(comm,layout.fields.size()==2&&layout.fields.count("velocity")&&layout.fields.count("pressure"),
                 "Schur velocity block3 requires standalone velocity/pressure fields");
    const auto& rows=layout.fields.at("velocity");
    bool good=layout.owned>=0&&layout.owned_semantics.size()==static_cast<std::size_t>(layout.owned)&&rows.size()%3==0;
    for(std::size_t i=0;good&&i<rows.size();i+=3) {
        DofKey first;
        for(std::size_t c=0;c<3;++c) {
            const auto row=rows[i+c]-layout.begin;
            if(row<0||row>=layout.owned) {good=false;break;}
            const auto& key=layout.owned_semantics[row];
            if(c==0) first=key;
            good=good&&key.domain==DofDomain::fluid&&key.quantity==DofQuantity::velocity&&
                key.kind==DofEntity::vertex&&key.mode==0&&key.space==1&&key.component==c&&
                key.entity==first.entity;
        }
    }
    common_check(comm,good,"Schur velocity block3 requires owned node-major Tet4/P1 velocity triples");
    return true;
}
void set_velocity_block3(MPI_Comm comm,KSP solver,PetscInt owned) {
    Mat a=nullptr,p=nullptr; EONSIM_PETSC(KSPGetOperators(solver,&a,&p));
    for(Mat matrix:{a,p}) {
        PetscInt m=0,n=0,begin=0,end=0;
        EONSIM_PETSC(MatGetSize(matrix,&m,&n));
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        common_check(comm,m==n&&m>0&&m%3==0&&begin%3==0&&end-begin==owned,
                     "Schur velocity submatrix does not preserve complete owned triples");
        // AIJ values/order are unchanged. PETSc3.23.7 GAMG then groups the
        // three components and supplies one constant candidate per component.
        // These are interpolation candidates, not an exact nullspace claim.
        EONSIM_PETSC(MatSetBlockSize(matrix,3));
        if(a==p) break;
    }
}
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
void schur(MPI_Comm comm,KSP solver,const std::vector<PetscInt>& velocity,const std::vector<PetscInt>& pressure,bool block3=false) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_SCHUR));
    EONSIM_PETSC(PCFieldSplitSetSchurFactType(pc,PC_FIELDSPLIT_SCHUR_FACT_FULL));
    EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,PC_FIELDSPLIT_SCHUR_PRE_SELFP,nullptr));
    split_is(comm,pc,"velocity",velocity); split_is(comm,pc,"pressure",pressure);
    EONSIM_PETSC(PCSetUp(pc));
    PetscInt n=0; KSP* sub=nullptr; EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&n,&sub));
    if(n!=2) { PetscFree(sub); throw std::runtime_error("Schur requires two fields"); }
    try {
        if(block3) set_velocity_block3(comm,sub[0],static_cast<PetscInt>(velocity.size()));
        for(PetscInt i=0;i<n;++i) multigrid(sub[i]);
    } catch(...) {PetscFree(sub);throw;}
    EONSIM_PETSC(PetscFree(sub));
}
}
void configure_schur_solver(MPI_Comm comm,KSP solver,const AlgebraLayout& layout,Mat matrix)
{
    const bool block3=velocity_block3(comm,layout);
    if(!layout.fields.count("velocity")||!layout.fields.count("pressure")) throw std::runtime_error("Schur solver requires velocity and pressure fields");
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    if(layout.fields.size()==2) { schur(comm,solver,layout.fields.at("velocity"),layout.fields.at("pressure"),block3); return; }
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
