#include "eonsim/coupled_velocity_pc.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <tuple>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity validation communication failed");
    if(any) throw std::runtime_error("Coupled velocity: "+message);
}
void option_default(const std::string& name,const char* value) {
    PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&set));
    if(!set) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
void common_choice(MPI_Comm comm,int value,bool valid,const std::string& message) {
    int lo=0,hi=0;
    if(MPI_Allreduce(&value,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&value,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity option reduction failed");
    common_check(comm,valid&&lo==hi,message);
}
void response_options(MPI_Comm comm,const std::string& prefix) {
    char value[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+prefix+"ksp_type").c_str(),value,sizeof(value),&set));
    const std::string type=set?value:KSPPREONLY;
    const int choice=type==KSPPREONLY?1:type==KSPFGMRES?2:0;
    common_choice(comm,choice,choice!=0,"response requires identical preonly or fgmres on every rank at "+prefix);
    PetscBool distinct=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,("-"+prefix+"pc_mg_distinct_smoothup").c_str(),&distinct,nullptr));
    common_choice(comm,distinct,true,"distinct smoother selection differs between ranks at "+prefix);
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
struct SparseMode {
    std::vector<PetscInt> rows;
    std::vector<PetscScalar> values;
};
struct FineRows {
    Mat matrix=nullptr,preconditioner=nullptr;
    PetscInt begin=0,end=0,global=0;
    std::vector<char> active;
};
FineRows fine_rows(MPI_Comm comm,KSP solver,const std::vector<DofKey>& semantics,
                  const std::vector<std::array<double,3>>& coordinates,bool rigid,bool gamg) {
    common_choice(comm,rigid,true,"rigid-mode selection differs between ranks");
    FineRows fine;
    EONSIM_PETSC(KSPGetOperators(solver,&fine.matrix,&fine.preconditioner));
    PetscInt columns=0,pbegin=0,pend=0,prows=0,pcolumns=0,cbegin=0,cend=0,pcbegin=0,pcend=0;
    EONSIM_PETSC(MatGetOwnershipRange(fine.matrix,&fine.begin,&fine.end));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(fine.matrix,&cbegin,&cend));
    EONSIM_PETSC(MatGetSize(fine.matrix,&fine.global,&columns));
    EONSIM_PETSC(MatGetOwnershipRange(fine.preconditioner,&pbegin,&pend));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(fine.preconditioner,&pcbegin,&pcend));
    EONSIM_PETSC(MatGetSize(fine.preconditioner,&prows,&pcolumns));
    common_check(comm,fine.global==columns&&fine.end-fine.begin==static_cast<PetscInt>(semantics.size())&&
                 pbegin==fine.begin&&pend==fine.end&&prows==fine.global&&pcolumns==columns&&
                 cbegin==fine.begin&&cend==fine.end&&pcbegin==fine.begin&&pcend==fine.end,
                 "owned metadata or preconditioner does not match the coupled matrix");
    common_check(comm,(!rigid&&coordinates.empty())||coordinates.size()==semantics.size(),
                 "rigid modes require reference coordinates in owned row order");
    fine.active.resize(semantics.size());
    bool valid=true;
    for(PetscInt row=fine.begin;row<fine.end;++row) {
        const auto& key=semantics[row-fine.begin];
        valid=valid&&key.quantity==DofQuantity::velocity&&
            (key.domain==DofDomain::fluid||key.domain==DofDomain::solid)&&key.component<3;
        if(gamg||rigid) valid=valid&&((key.kind==DofEntity::vertex&&key.mode==0&&key.space==1)||
            (key.kind==DofEntity::body&&key.domain==DofDomain::solid&&key.component==0));
        if(rigid&&key.kind==DofEntity::vertex)
            for(double x:coordinates[row-fine.begin]) valid=valid&&std::isfinite(x);
        PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(fine.matrix,row,&count,&indices,&values));
        bool identity=true,diagonal=false;
        for(PetscInt j=0;j<count;++j) {
            valid=valid&&std::isfinite(values[j]);
            if(indices[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
            else identity=identity&&values[j]==0.;
        }
        EONSIM_PETSC(MatRestoreRow(fine.matrix,row,&count,&indices,&values));
        // MatZeroRows retains structural zero entries. Identity is numerical.
        fine.active[row-fine.begin]=!(identity&&diagonal);
    }
    if(gamg) {
        PetscInt block_size=0; EONSIM_PETSC(MatGetBlockSize(fine.preconditioner,&block_size));
        valid=valid&&block_size==1;
    }
    common_check(comm,valid,"nonfinite matrix/coordinates or unsupported velocity semantics (rigid/GAMG requires vertex P1 or a body scalar, GAMG requires scalar AIJ)");
    return fine;
}
long double reduced_sum(MPI_Comm comm,long double local,bool distributed) {
    if(!distributed) return local;
    long double global=0;
    if(MPI_Allreduce(&local,&global,1,MPI_LONG_DOUBLE,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity mode reduction failed");
    return global;
}
// Keep sparse owner-local storage even for global modes. Only scalar products,
// never complete fields, are reduced. Two passes resolve constrained/partial
// component and collinear geometries without adding an arbitrary regularizer.
bool append_mode(MPI_Comm comm,PetscInt begin,std::vector<PetscScalar> candidate,
                 std::vector<SparseMode>& modes,bool distributed) {
    long double initial_squared=0;
    for(auto value:candidate) initial_squared+=static_cast<long double>(value)*value;
    const auto initial=std::sqrt(reduced_sum(comm,initial_squared,distributed));
    if(initial==0) return true;
    for(int pass=0;pass<2;++pass) for(const auto& mode:modes) {
        long double local=0;
        for(std::size_t j=0;j<mode.rows.size();++j)
            local+=static_cast<long double>(mode.values[j])*candidate[mode.rows[j]-begin];
        const auto product=reduced_sum(comm,local,distributed);
        for(std::size_t j=0;j<mode.rows.size();++j)
            candidate[mode.rows[j]-begin]-=static_cast<double>(product*mode.values[j]);
    }
    long double squared=0;
    for(auto value:candidate) squared+=static_cast<long double>(value)*value;
    const auto norm=std::sqrt(reduced_sum(comm,squared,distributed));
    if(!std::isfinite(initial)||!std::isfinite(norm)) return false;
    // Coordinates are centered and scaled before rotations are formed. This
    // threshold is relative to that dimensionless basis, not physical units.
    const long double threshold=256*std::numeric_limits<double>::epsilon()*std::max(1.L,initial);
    if(norm<=threshold) return true;
    SparseMode result;
    for(std::size_t i=0;i<candidate.size();++i) if(candidate[i]!=0) {
        result.rows.push_back(begin+static_cast<PetscInt>(i));
        result.values.push_back(static_cast<double>(candidate[i]/norm));
    }
    modes.push_back(std::move(result));
    return true;
}
struct CoordinateFrame { std::array<long double,3> center{}; long double scale=0; };
CoordinateFrame coordinate_frame(PetscInt begin,const std::vector<PetscInt>& rows,
    const std::vector<std::array<double,3>>& coordinates) {
    CoordinateFrame frame;
    long double sums[4]{};
    for(auto row:rows) {
        for(int c=0;c<3;++c) sums[c]+=coordinates[row-begin][c];
        ++sums[3];
    }
    if(sums[3]>0) for(int c=0;c<3;++c) frame.center[c]=sums[c]/sums[3];
    for(auto row:rows) for(int c=0;c<3;++c)
        frame.scale=std::max(frame.scale,std::abs(static_cast<long double>(coordinates[row-begin][c])-frame.center[c]));
    return frame;
}
double rotation_component(const CoordinateFrame& frame,const std::array<double,3>& coordinate,
                          int component,int axis) {
    if(frame.scale==0||component==axis) return 0;
    const int positive=(axis+1)%3,negative=(axis+2)%3;
    const auto value=component==negative?
        static_cast<long double>(coordinate[positive])-frame.center[positive]:
        frame.center[negative]-static_cast<long double>(coordinate[negative]);
    return static_cast<double>(value/frame.scale);
}
std::vector<SparseMode> local_modes(MPI_Comm comm,const FineRows& fine,
    const std::vector<DofKey>& semantics,const std::vector<std::array<double,3>>& coordinates,bool rigid) {
    std::map<Mode,Group> groups;
    for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) {
        const auto& key=semantics[row-fine.begin];
        groups[{key.domain,key.kind,key.component,key.mode,key.space}].rows.push_back(row);
    }
    std::vector<SparseMode> modes;
    for(const auto& group:groups) {
        const auto& rows=group.second.rows;
        modes.push_back({rows,std::vector<PetscScalar>(rows.size(),1./std::sqrt(static_cast<double>(rows.size())))});
    }
    if(rigid) {
        using VectorGroup=std::tuple<DofEntity,std::uint16_t,std::uint16_t>;
        std::map<VectorGroup,std::vector<PetscInt>> solid;
        for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) {
            const auto& key=semantics[row-fine.begin];
            if(key.domain==DofDomain::solid&&key.kind==DofEntity::vertex&&key.mode==0&&key.space==1)
                solid[{key.kind,key.mode,key.space}].push_back(row);
        }
        bool valid=true;
        for(const auto& group:solid) {
            const auto frame=coordinate_frame(fine.begin,group.second,coordinates);
            for(int axis=0;axis<3;++axis) {
                std::vector<PetscScalar> candidate(fine.end-fine.begin,0);
                for(auto row:group.second) candidate[row-fine.begin]=rotation_component(
                    frame,coordinates[row-fine.begin],semantics[row-fine.begin].component,axis);
                valid=append_mode(comm,fine.begin,std::move(candidate),modes,false)&&valid;
            }
        }
        common_check(comm,valid,"nonfinite local rigid-motion orthogonalization");
    }
    return modes;
}
std::vector<SparseMode> scalar_mode(MPI_Comm comm,const FineRows& fine) {
    std::vector<SparseMode> modes;
    std::vector<PetscScalar> candidate(fine.end-fine.begin,0);
    for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) candidate[row-fine.begin]=1;
    const bool valid=append_mode(comm,fine.begin,std::move(candidate),modes,true);
    common_check(comm,valid,"nonfinite global scalar near mode");
    return modes;
}
}

void validate_coupled_velocity_twolevel_options(MPI_Comm comm,const std::string& prefix) {
    const auto base="-"+prefix;
    response_options(comm,prefix);
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
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,bool rigid_modes) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_twolevel_options(comm,prefix);
    const auto fine=fine_rows(comm,solver,owned_semantics,owned_coordinates,rigid_modes,false);
    const auto modes=local_modes(comm,fine,owned_semantics,owned_coordinates,rigid_modes);
    const auto begin=fine.begin,end=fine.end,global=fine.global;
    std::vector<PetscInt> nonzeros(end-begin,0);
    for(const auto& mode:modes) for(auto row:mode.rows) ++nonzeros[row-begin];
    PetscInt local_count=static_cast<PetscInt>(modes.size()),coarse_begin=0,global_count=0;
    int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&local_count,&coarse_begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local_count,&global_count,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
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

    if(global_count==0) {
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
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local_count,global,global_count,
            0,nonzeros.data(),0,nullptr,interpolation.put()));
        EONSIM_PETSC(MatSetOption(interpolation.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
        PetscInt column=coarse_begin;
        for(const auto& mode:modes) {
            for(std::size_t i=0;i<mode.rows.size();++i)
                EONSIM_PETSC(MatSetValue(interpolation.get(),mode.rows[i],column,mode.values[i],INSERT_VALUES));
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
        "pc_twolevel prefix=%s global_modes=%" PetscInt_FMT " levels=%d identity=%d rigid_modes=%d\n",
        prefix.empty()?"-":prefix.c_str(),global_count,global_count?2:1,global_count?0:1,static_cast<int>(rigid_modes)));
}

void validate_coupled_velocity_gamg_options(MPI_Comm comm,const std::string& prefix) {
    response_options(comm,prefix);
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","gamg"},{"pc_gamg_type","agg"},{"pc_mg_type","multiplicative"},
        {"pc_mg_cycle_type","v"},{"pc_mg_galerkin","external"},
        {"pc_mg_adapt_interp_coarse_space","none"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
    PetscBool fixed_levels=PETSC_FALSE,adapt=PETSC_FALSE,reuse=PETSC_TRUE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+"pc_mg_levels").c_str(),&fixed_levels));
    common_check(comm,!fixed_levels,"GAMG determines its levels; use pc_gamg_ options at "+prefix);
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_adapt_cr").c_str(),&adapt,nullptr));
    common_check(comm,!adapt,"adaptive coarse spaces require an independent implementation");
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_gamg_reuse_interpolation").c_str(),&reuse,nullptr));
    common_choice(comm,reuse,true,"GAMG interpolation reuse differs between ranks at "+prefix);
}

void configure_coupled_velocity_gamg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,bool rigid_modes) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_gamg_options(comm,prefix);
    common_check(comm,!rigid_modes,"scalar GAMG cannot use rigid near modes; choose twolevel with rigid modes");
    const auto fine=fine_rows(comm,solver,owned_semantics,owned_coordinates,false,true);
    const auto modes=scalar_mode(comm,fine);
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCGAMG));
    EONSIM_PETSC(PCGAMGSetType(pc,PCGAMGAGG));
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    EONSIM_PETSC(PCMGSetType(pc,PC_MG_MULTIPLICATIVE));
    // GAMG creates levels during setup; PCMGSetCycleType requires them to
    // exist. Its deferred MG-options pass applies this default afterwards.
    option_default(base+"pc_mg_cycle_type","v");
    EONSIM_PETSC(PCGAMGSetReuseInterpolation(pc,PETSC_TRUE));
    // PETSc creates the levels during setup. Prefix defaults reach every new
    // smoother, including rebuilt levels when interpolation reuse is disabled.
    // ASM handles the nonsymmetric coupled matrix without assuming it is SPD.
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"mg_levels_ksp_type","richardson"},{"mg_levels_ksp_norm_type","none"},
        {"mg_levels_ksp_max_it","1"},{"mg_levels_pc_type","asm"},
        {"mg_levels_pc_asm_overlap","1"},{"mg_levels_sub_ksp_type","preonly"},
        {"mg_levels_sub_pc_type","ilu"},{"mg_levels_sub_pc_factor_levels","1"},
        {"mg_levels_sub_pc_factor_mat_ordering_type","rcm"},
        {"mg_coarse_ksp_type","gmres"},{"mg_coarse_pc_type","jacobi"},
        {"mg_coarse_ksp_rtol","1e-10"},{"mg_coarse_ksp_max_it","200"},
        {"mg_coarse_ksp_norm_type","unpreconditioned"}})
        option_default(base+option.first,option.second.c_str());

    if(!modes.empty()) {
        PetscOwner<Vec,VecDestroy> vector;
        EONSIM_PETSC(MatCreateVecs(fine.preconditioner,vector.put(),nullptr));
        EONSIM_PETSC(VecSet(vector.get(),0));
        PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(vector.get(),&values));
        for(std::size_t j=0;j<modes.front().rows.size();++j)
            values[modes.front().rows[j]-fine.begin]=modes.front().values[j];
        EONSIM_PETSC(VecRestoreArray(vector.get(),&values));
        PetscOwner<MatNullSpace,MatNullSpaceDestroy> near_space;
        const Vec near_vector=vector.get();
        EONSIM_PETSC(MatNullSpaceCreate(comm,PETSC_FALSE,1,&near_vector,near_space.put()));
        EONSIM_PETSC(MatSetNearNullSpace(fine.preconditioner,near_space.get()));
        if(fine.matrix!=fine.preconditioner)
            EONSIM_PETSC(MatSetNearNullSpace(fine.matrix,near_space.get()));
        // PETSc retains the vectors through MatNullSpace references. This is a
        // single scalar constant over all active components and the body, not
        // a vector-elasticity nullspace. With blocksize 1, AGG's fixed-column QR
        // can create redundant columns if separate vector modes vanish within
        // a scalar aggregate; global orthogonality would not prevent that.
    } else {
        // A matrix may previously have carried this optional near space before
        // a constraint-triggered solver rebuild. Do not retain obsolete modes.
        EONSIM_PETSC(MatSetNearNullSpace(fine.preconditioner,nullptr));
        if(fine.matrix!=fine.preconditioner) EONSIM_PETSC(MatSetNearNullSpace(fine.matrix,nullptr));
    }
    EONSIM_PETSC(KSPSetFromOptions(solver));
    PetscInt levels=1,coarse_rows=fine.global;
    if(modes.empty()) {
        // Every row is the identity. Avoid AMG setup with an empty near space.
        EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
        EONSIM_PETSC(PCSetType(pc,PCJACOBI));
        EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    } else {
        // This setup establishes the actual hierarchy once; repeated setup on
        // unchanged matrices is a PETSc no-op. Subsequent numeric changes use
        // GAMG's native MatPtAP refresh, never stale coarse numerical matrices.
        EONSIM_PETSC(PCSetUp(pc));
        EONSIM_PETSC(PCMGGetLevels(pc,&levels));
        KSP coarse=nullptr; Mat coarse_matrix=nullptr;
        EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
        EONSIM_PETSC(KSPGetOperators(coarse,&coarse_matrix,nullptr));
        EONSIM_PETSC(MatGetSize(coarse_matrix,&coarse_rows,nullptr));
    }
    PetscBool report=PETSC_FALSE,reuse=PETSC_TRUE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_gamg_reuse_interpolation").c_str(),&reuse,nullptr));
    if(report) EONSIM_PETSC(PetscPrintf(comm,
        "pc_coupled_gamg prefix=%s near_modes=%zu levels=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
        " identity=%d reuse_interpolation=%d basis=scalar_constant\n",prefix.empty()?"-":prefix.c_str(),
        modes.size(),levels,coarse_rows,modes.empty()?1:0,static_cast<int>(reuse)));
}
} // namespace eonsim
