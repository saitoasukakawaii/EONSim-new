#include "eonsim/schur_solver.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <stdexcept>
#include <sstream>
namespace eonsim {
namespace {
void collective_check(MPI_Comm comm,bool valid,const std::string& message) {
    int local=valid?1:0,all=0;
    if(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Schur solver validation communication failed");
    if(!all) throw std::runtime_error("Schur solver: "+message);
}
struct SubSolvers { KSP* values=nullptr; ~SubSolvers(){PetscFree(values);} };
PetscErrorCode check_schur_inner_solve(KSP solver,Vec,Vec solution,void* context) {
    // MatSchurComplement calls KSPSolve without the KSPCheckSolve used by
    // PCFieldSplit's triangular factors. Preserve a bounded ITS iterate, but
    // flag breakdown/PC failures before the subsequent Schur matrix product.
    return KSPCheckSolve(solver,static_cast<PC>(context),solution);
}
void option_default(const std::string& name,const char* value) {
    PetscBool found=PETSC_FALSE; EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
void multigrid(KSP solver) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCGAMG));
    // The declared Pmat supplies preconditioning blocks; Amat can be an
    // implicit Schur operator. GAMG's MG constructor enables useAmat, and
    // that flag survives a user PC-type change (for example to BJacobi).
    // Reset the default before options, preserving explicit -pc_use_amat.
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
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
    // Apply options after defaults and IS registration, otherwise the default
    // FULL/SELFP above overwrites user choices made by SNESSetFromOptions.
    EONSIM_PETSC(KSPSetFromOptions(solver));
    EONSIM_PETSC(PCSetUp(pc));
    configure_schur_subsolvers(comm,pc,multigrid,multigrid);
}
}
SchurAuxiliaryOptions validate_schur_auxiliary_options(MPI_Comm comm,
    const std::string& prefix,const std::string& second_name) {
    const std::string base="-"+prefix;
    const std::string second=base+"fieldsplit_"+second_name;
    char* options=nullptr;
    EONSIM_PETSC(PetscOptionsGetAll(nullptr,&options));
    std::istringstream stream(options?options:"");
    EONSIM_PETSC(PetscFree(options));
    SchurAuxiliaryOptions result;
    std::string token;
    while(stream>>token) {
        result.inner=result.inner||token.rfind(second+"_inner_",0)==0;
        result.upper=result.upper||token.rfind(second+"_upper_",0)==0;
    }
    char value[32]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,
        (base+"pc_fieldsplit_schur_fact_type").c_str(),value,sizeof(value),&set));
    const std::string factor=set?value:"full";
    const int kind=factor=="full"?1:factor=="lower"?2:factor=="upper"?3:factor=="diag"?4:0;
    const int local[3]={result.inner?1:0,result.upper?1:0,kind};
    int minimum[3]{},maximum[3]{};
    if(MPI_Allreduce(local,minimum,3,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(local,maximum,3,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Schur auxiliary option communication failed");
    collective_check(comm,std::equal(minimum,minimum+3,maximum)&&kind!=0,
        "factorization and inner/upper solver activation must be valid and identical on every rank at "+prefix);
    // In PETSc UPPER applies the main A00 KSP; kspupper is specific to FULL.
    collective_check(comm,!result.upper||kind==1,
        "separate Schur upper solver requires full factorization at "+prefix);
    return result;
}
void configure_schur_subsolvers(MPI_Comm comm,PC pc,
    const std::function<void(KSP)>& configure_a00,
    const std::function<void(KSP)>& configure_second) {
    PetscInt count=0; SubSolvers sub;
    EONSIM_PETSC(PCFieldSplitSchurGetSubKSP(pc,&count,&sub.values));
    collective_check(comm,(count==2||count==3)&&sub.values,
        "expected main A00, Schur and optional upper solvers");
    Mat schur_matrix=nullptr; KSP inner=nullptr;
    EONSIM_PETSC(PCFieldSplitSchurGetS(pc,&schur_matrix));
    EONSIM_PETSC(MatSchurComplementGetKSP(schur_matrix,&inner));
    EONSIM_PETSC(PCFieldSplitSchurRestoreS(pc,&schur_matrix));
    // PCFieldSplitGetSubKSP returns the *interior* A00 KSP in Schur mode.
    // It can differ from the factor's main solve, so configuring that array
    // alone leaves the main/upper solvers with unrelated PETSc defaults.
    const std::array<KSP,3> inverse_solvers{{sub.values[0],inner,count==3?sub.values[2]:nullptr}};
    for(std::size_t i=0;i<inverse_solvers.size();++i) {
        const auto current=inverse_solvers[i];
        if(current&&std::find(inverse_solvers.begin(),inverse_solvers.begin()+i,current)==inverse_solvers.begin()+i)
            configure_a00(current);
    }
    configure_second(sub.values[1]);
    // The containing PC owns its Schur matrix and interior KSP. Its borrowed
    // lifetime therefore covers this callback, including the default alias of
    // the main A00 solve. EONSim owns child postsolve callbacks in this setup.
    EONSIM_PETSC(KSPSetPostSolve(inner,check_schur_inner_solve,pc));
}
// Old entry point keeps its flow/structure/rigid prefixes. Its topology is fixed.
void validate_schur_solver_options(MPI_Comm comm,KSP solver,const AlgebraLayout& layout) {
    int valid=layout.fields.count("velocity")&&layout.fields.count("pressure"),all=0;
    MPI_Allreduce(&valid,&all,1,MPI_INT,MPI_MIN,comm);
    if(!all) throw std::runtime_error("Schur solver requires velocity and pressure fields");
    const char* prefix=nullptr;
    EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    const std::string root=prefix?prefix:"";
    const bool independent=layout.fields.size()==2;
    const auto check_node=[&](const std::string& node,bool schur_node) {
        const std::string base="-"+node;
        for(const auto& option:std::vector<std::pair<std::string,std::string>>{
            {"pc_type","fieldsplit"},{"pc_fieldsplit_type",schur_node?"schur":"multiplicative"}}) {
            char value[128]{}; PetscBool set=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
            if(set&&std::string(value)!=option.second) valid=0;
        }
        if(schur_node) {
            validate_schur_auxiliary_options(comm,node,"pressure");
        }
    };
    check_node(root,independent);
    if(!independent) check_node(root+"fieldsplit_flow_",true);
    MPI_Allreduce(&valid,&all,1,MPI_INT,MPI_MIN,comm);
    if(!all) throw std::runtime_error("Legacy Schur options changed fixed topology");
}
void configure_schur_solver(MPI_Comm comm,KSP solver,const AlgebraLayout& layout,Mat matrix)
{
    validate_schur_solver_options(comm,solver,layout);
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    if(layout.fields.size()==2) { schur(comm,solver,layout.fields.at("velocity"),layout.fields.at("pressure")); return; }
    auto fields=layout.fields;
    auto& flow=fields["flow"]; flow=fields.at("velocity"); flow.insert(flow.end(),fields.at("pressure").begin(),fields.at("pressure").end()); std::sort(flow.begin(),flow.end());
    fields.erase("velocity"); fields.erase("pressure");
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_MULTIPLICATIVE));
    for(const auto& field:fields) split_is(comm,pc,field.first.c_str(),field.second);
    EONSIM_PETSC(KSPSetFromOptions(solver));
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
            EONSIM_PETSC(KSPSetFromOptions(sub[i]));
        } else multigrid(sub[i]);
        ++i;
    }
    EONSIM_PETSC(PetscFree(sub));
}
}
