#include "eonsim/coupled_velocity_pc.hpp"
#include <cmath>
#include <map>
#include <tuple>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Two-level velocity validation communication failed");
    if(any) throw std::runtime_error("Two-level velocity: "+message);
}
void option_default(const std::string& name,const char* value) {
    PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&set));
    if(!set) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
void smoother_defaults(KSP solver) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPRICHARDSON));
    EONSIM_PETSC(KSPSetNormType(solver,KSP_NORM_NONE));
    EONSIM_PETSC(KSPSetTolerances(solver,PETSC_DEFAULT,PETSC_DEFAULT,PETSC_DEFAULT,1));
    EONSIM_PETSC(PCSetType(pc,PCASM));
    EONSIM_PETSC(PCASMSetOverlap(pc,1));
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    option_default(base+"sub_ksp_type","preonly");
    option_default(base+"sub_pc_type","ilu");
    option_default(base+"sub_pc_factor_levels","1");
    option_default(base+"sub_pc_factor_mat_ordering_type","rcm");
    EONSIM_PETSC(KSPSetFromOptions(solver));
}
// Subdomain modes deliberately remain separate across material domains and
// finite-element spaces; equal component numbers alone do not identify a mode.
using Mode=std::tuple<DofDomain,DofEntity,std::uint16_t,std::uint16_t,std::uint16_t>;
struct Group { std::vector<PetscInt> rows; };
}

void validate_coupled_velocity_twolevel_options(MPI_Comm comm,const std::string& prefix) {
    const auto base="-"+prefix;
    char solver_type[64]{}; PetscBool solver_set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"ksp_type").c_str(),solver_type,sizeof(solver_type),&solver_set));
    common_check(comm,!solver_set||std::string(solver_type)==KSPFGMRES||std::string(solver_type)==KSPPREONLY,
                 "twolevel requires fgmres or preonly for a variable coarse solve at "+prefix);
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","mg"},{"pc_mg_type","multiplicative"},
        {"pc_mg_galerkin","both"},{"pc_mg_adapt_interp_coarse_space","none"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
    PetscInt levels=2; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+"pc_mg_levels").c_str(),&levels,&set));
    common_check(comm,!set||levels==2,"pc_mg_levels must be 2 (the all-identity case collapses to one level)");
    PetscBool adapt=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_adapt_cr").c_str(),&adapt,nullptr));
    common_check(comm,!adapt,"adaptive coarse spaces require an independent implementation");
}

void configure_coupled_velocity_twolevel(MPI_Comm comm,KSP solver,
                                        const std::vector<DofKey>& owned_semantics) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_twolevel_options(comm,prefix);
    Mat matrix=nullptr; EONSIM_PETSC(KSPGetOperators(solver,&matrix,nullptr));
    PetscInt begin=0,end=0,global=0,columns=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&global,&columns));
    common_check(comm,global==columns&&end-begin==static_cast<PetscInt>(owned_semantics.size()),
                 "owned semantics do not match the coupled matrix");

    std::map<Mode,Group> groups;
    std::vector<PetscInt> nonzeros(end-begin,0);
    bool valid=true;
    for(PetscInt row=begin;row<end;++row) {
        const auto& key=owned_semantics[row-begin];
        valid=valid&&key.quantity==DofQuantity::velocity&&
            (key.domain==DofDomain::fluid||key.domain==DofDomain::solid)&&key.component<3;
        PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&values));
        bool identity=true,diagonal=false;
        for(PetscInt j=0;j<count;++j) {
            valid=valid&&std::isfinite(values[j]);
            if(indices[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
            else identity=identity&&values[j]==0.;
        }
        EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&values));
        // MatZeroRows retains zero structural entries. Test values, not nnz.
        if(identity&&diagonal) continue;
        groups[{key.domain,key.kind,key.component,key.mode,key.space}].rows.push_back(row);
        nonzeros[row-begin]=1;
    }
    common_check(comm,valid,"nonfinite matrix or unsupported velocity semantics");
    PetscInt local_modes=static_cast<PetscInt>(groups.size()),coarse_begin=0,global_modes=0;
    int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&local_modes,&coarse_begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local_modes,&global_modes,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Two-level velocity mode count communication failed");
    if(rank==0) coarse_begin=0;

    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    // Apply PCMG once by default. The tolerance-dependent coarse GMRES still
    // makes this action variable, so the outer FSI solve remains FGMRES.
    // Keep the bounded budget for an explicit FGMRES option applied below.
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCMG));
    EONSIM_PETSC(PCMGSetLevels(pc,2,nullptr));
    EONSIM_PETSC(PCMGSetType(pc,PC_MG_MULTIPLICATIVE));
    EONSIM_PETSC(PCMGSetGalerkin(pc,PC_MG_GALERKIN_BOTH));
    EONSIM_PETSC(KSPSetFromOptions(solver));

    if(global_modes==0) {
        // All rows are exactly the identity. There is no unconstrained coarse
        // space, and a single Jacobi action is an exact solve, not a failed MG.
        EONSIM_PETSC(PCMGSetLevels(pc,1,nullptr));
        EONSIM_PETSC(PCMGSetGalerkin(pc,PC_MG_GALERKIN_NONE));
        KSP identity_solver=nullptr; EONSIM_PETSC(PCMGGetSmoother(pc,0,&identity_solver));
        PC identity_pc; EONSIM_PETSC(KSPGetPC(identity_solver,&identity_pc));
        EONSIM_PETSC(KSPSetType(identity_solver,KSPPREONLY));
        EONSIM_PETSC(PCSetType(identity_pc,PCJACOBI));
    } else {
        PetscOwner<Mat,MatDestroy> interpolation;
        // Every coarse column is owned by the same rank as its contributing
        // rows. Empty ranks and ranks containing only constraints have no columns.
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local_modes,global,global_modes,
            0,nonzeros.data(),0,nullptr,interpolation.put()));
        EONSIM_PETSC(MatSetOption(interpolation.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
        PetscInt column=coarse_begin;
        for(const auto& item:groups) {
            const auto& rows=item.second.rows;
            const PetscScalar value=1./std::sqrt(static_cast<double>(rows.size()));
            for(const auto row:rows)
                EONSIM_PETSC(MatSetValue(interpolation.get(),row,column,value,INSERT_VALUES));
            ++column;
        }
        EONSIM_PETSC(MatAssemblyBegin(interpolation.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(interpolation.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(PCMGSetInterpolation(pc,1,interpolation.get()));
        // PETSc owns a reference to P and computes/reuses P^T A P at setup;
        // no root-matrix copy or user numeric-refresh callback is necessary.
        // The Down getter itself creates a distinct Up smoother in PETSc;
        // use the shared getter unless the user requested distinct smoothers.
        KSP down=nullptr; EONSIM_PETSC(PCMGGetSmoother(pc,1,&down));
        smoother_defaults(down);
        PetscBool distinct=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_distinct_smoothup").c_str(),&distinct,nullptr));
        if(distinct) {
            KSP up=nullptr; EONSIM_PETSC(PCMGGetSmootherUp(pc,1,&up));
            if(up!=down) smoother_defaults(up);
        }
        KSP coarse=nullptr; EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
        PC coarse_pc; EONSIM_PETSC(KSPGetPC(coarse,&coarse_pc));
        EONSIM_PETSC(KSPSetType(coarse,KSPGMRES));
        EONSIM_PETSC(KSPSetTolerances(coarse,1e-10,PETSC_DEFAULT,PETSC_DEFAULT,200));
        EONSIM_PETSC(KSPSetNormType(coarse,KSP_NORM_UNPRECONDITIONED));
        EONSIM_PETSC(PCSetType(coarse_pc,PCJACOBI));
        EONSIM_PETSC(KSPSetFromOptions(coarse));
    }
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) EONSIM_PETSC(PetscPrintf(comm,
        "pc_twolevel prefix=%s global_modes=%" PetscInt_FMT " levels=%d identity=%d\n",
        prefix.empty()?"-":prefix.c_str(),global_modes,global_modes?2:1,global_modes?0:1));
}
} // namespace eonsim
