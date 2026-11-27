#include "eonsim/nonlinear_system.hpp"
#include <cstdint>
#include "eonsim/schur_solver.hpp"
#include "eonsim/pc_plan.hpp"
#include "eonsim/rcr_port_pc.hpp"
#include "eonsim/interface_patch_pc.hpp"
#include "eonsim/pressure_schur_pc.hpp"
#include "eonsim/monolithic_fsi_mg.hpp"
#include "eonsim/deflated_fgmres.hpp"
#include "eonsim/time_step.hpp"
#include <cmath>
#include <stdexcept>
#include <iostream>
#include <chrono>
#include <cstring>
#include <algorithm>
#include <iomanip>
#include <limits>
#include <sstream>
#include <set>
#include <optional>
#if defined(__linux__)
#include <sys/resource.h>
#endif
namespace eonsim {
namespace {
// 显式的小算例诊断：检验真实已装配 J/R 的跨 rank 置换，不修改生产布局。
// VecPermute 不支持非本地置换，故向量使用同一 IS 的分布式 scatter。
void verify_operator_permutation(MPI_Comm comm,Mat matrix,Vec residual) {
    PetscInt begin,end,size;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&size,nullptr));
    std::vector<PetscInt> reverse;
    for(PetscInt i=begin;i<end;++i) reverse.push_back(size-1-i);
    PetscOwner<IS,ISDestroy> source,destination;
    EONSIM_PETSC(ISCreateGeneral(comm,end-begin,reverse.data(),PETSC_COPY_VALUES,source.put()));
    EONSIM_PETSC(ISCreateStride(comm,end-begin,begin,1,destination.put()));
    PetscOwner<Mat,MatDestroy> permuted;
    EONSIM_PETSC(MatPermute(matrix,source.get(),source.get(),permuted.put()));
    PetscOwner<Vec,VecDestroy> direction,action,mapped_direction,mapped_action,actual,mapped_residual;
    EONSIM_PETSC(MatCreateVecs(matrix,direction.put(),action.put()));
    EONSIM_PETSC(VecDuplicate(direction.get(),mapped_direction.put()));
    EONSIM_PETSC(VecDuplicate(action.get(),mapped_action.put()));
    EONSIM_PETSC(VecDuplicate(action.get(),actual.put()));
    EONSIM_PETSC(VecDuplicate(action.get(),mapped_residual.put()));
    PetscOwner<VecScatter,VecScatterDestroy> scatter;
    EONSIM_PETSC(VecScatterCreate(direction.get(),source.get(),mapped_direction.get(),destination.get(),scatter.put()));
    const auto map=[&](Vec from,Vec to) {
        EONSIM_PETSC(VecScatterBegin(scatter.get(),from,to,INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),from,to,INSERT_VALUES,SCATTER_FORWARD));
    };
    PetscScalar* values;
    EONSIM_PETSC(VecGetArray(direction.get(),&values));
    for(PetscInt i=begin;i<end;++i) values[i-begin]=std::sin(.37*(i+1))+.2*std::cos(.13*(i+1));
    EONSIM_PETSC(VecRestoreArray(direction.get(),&values));
    EONSIM_PETSC(MatMult(matrix,direction.get(),action.get()));
    map(direction.get(),mapped_direction.get()); map(action.get(),mapped_action.get());
    EONSIM_PETSC(MatMult(permuted.get(),mapped_direction.get(),actual.get()));
    PetscReal scale,error;
    EONSIM_PETSC(VecNorm(mapped_action.get(),NORM_INFINITY,&scale));
    EONSIM_PETSC(VecAXPY(actual.get(),-1,mapped_action.get()));
    EONSIM_PETSC(VecNorm(actual.get(),NORM_INFINITY,&error));
    if(!std::isfinite(scale)||!std::isfinite(error)||error>1e-11*(1+scale)) throw std::runtime_error("Assembled Jacobian permutation mismatch");
    map(residual,mapped_residual.get());
    EONSIM_PETSC(VecScatterBegin(scatter.get(),mapped_residual.get(),actual.get(),INSERT_VALUES,SCATTER_REVERSE));
    EONSIM_PETSC(VecScatterEnd(scatter.get(),mapped_residual.get(),actual.get(),INSERT_VALUES,SCATTER_REVERSE));
    EONSIM_PETSC(VecAXPY(actual.get(),-1,residual));
    PetscReal residual_error;
    EONSIM_PETSC(VecNorm(actual.get(),NORM_INFINITY,&residual_error));
    if(!std::isfinite(residual_error)||residual_error!=0) throw std::runtime_error("Assembled residual permutation mismatch");
    // 已知离散解的右端 J*v，检查真实切线的置换线性求解，而非只比较矩阵尺寸。
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOperators(solver.get(),permuted.get(),permuted.get()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPPREONLY));
    PC pc; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    EONSIM_PETSC(PCSetType(pc,PCLU));
    EONSIM_PETSC(PCFactorSetMatSolverType(pc,MATSOLVERSUPERLU_DIST));
    const auto solve_checked=[&](Vec rhs,Vec solution) {
        const auto solve_error=KSPSolve(solver.get(),rhs,solution);
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
        PCFailedReason pc_failure=PC_NOERROR;
        const auto reason_error=KSPGetConvergedReason(solver.get(),&reason);
        const auto pc_error=PCGetFailedReason(pc,&pc_failure);
        // PETSc 3.19 PREONLY 可在局部 PC 失败后返回不同 reason；进入后续规约前共同拒绝。
        int failed=solve_error||reason_error||pc_error||reason<=0||pc_failure!=PC_NOERROR,any_failed=0;
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
        if(any_failed) throw std::runtime_error("Assembled permutation reference solve failed");
    };
    solve_checked(mapped_action.get(),actual.get());
    EONSIM_PETSC(VecAXPY(actual.get(),-1,mapped_direction.get()));
    PetscReal solution_error; EONSIM_PETSC(VecNorm(actual.get(),NORM_INFINITY,&solution_error));
    if(!std::isfinite(solution_error)||solution_error>2e-8)
        throw std::runtime_error("Assembled permutation solve mismatch");
    // 同一因子求解真实 Newton 右端；逆映射后由原始 J/R 验证修正方程。
    solve_checked(mapped_residual.get(),actual.get());
    EONSIM_PETSC(VecScatterBegin(scatter.get(),actual.get(),direction.get(),INSERT_VALUES,SCATTER_REVERSE));
    EONSIM_PETSC(VecScatterEnd(scatter.get(),actual.get(),direction.get(),INSERT_VALUES,SCATTER_REVERSE));
    EONSIM_PETSC(MatMult(matrix,direction.get(),action.get()));
    EONSIM_PETSC(VecAXPY(action.get(),-1,residual));
    PetscReal correction_error,residual_scale;
    EONSIM_PETSC(VecNorm(action.get(),NORM_2,&correction_error));
    EONSIM_PETSC(VecNorm(residual,NORM_2,&residual_scale));
    if(!std::isfinite(correction_error)||correction_error>1e-8+1e-7*residual_scale)
        throw std::runtime_error("Permuted Newton correction fails original equations");
    EONSIM_PETSC(PetscPrintf(comm,"operator_permutation dofs=%" PetscInt_FMT " action_error=%.17g residual_error=%.17g solution_error=%.17g correction_error=%.17g\n",size,double(error),double(residual_error),double(solution_error),double(correction_error)));
}
// 只读取已存在的求解器；尤其不调用 PCSetUp 或会创建新对象的 PCMGGetSmootherUp。
PetscErrorCode describe_solver(KSP ksp,int rank,const std::string& path,
                               std::set<KSP>& visited,std::ostringstream& out)
{
    if(!ksp||!visited.insert(ksp).second) return PETSC_SUCCESS;
    PC pc; KSPType kt; PCType pt; const char* prefix=nullptr;
    KSPConvergedReason reason; PCFailedReason failure;
    PetscInt iterations; PetscReal norm; KSPNormType norm_type;
    PetscCall(KSPGetType(ksp,&kt)); PetscCall(KSPGetPC(ksp,&pc)); PetscCall(PCGetType(pc,&pt));
    PetscCall(KSPGetOptionsPrefix(ksp,&prefix)); PetscCall(KSPGetConvergedReason(ksp,&reason));
    PetscCall(PCGetFailedReason(pc,&failure)); PetscCall(KSPGetIterationNumber(ksp,&iterations));
    PetscCall(KSPGetResidualNorm(ksp,&norm)); PetscCall(KSPGetNormType(ksp,&norm_type));
    // KSPGetOperators can create an absent matrix: inspect presence before borrowing it.
    PetscBool operator_set=PETSC_FALSE;
    PetscInt rows=-1,columns=-1,local_rows=-1,local_columns=-1;
    PetscCall(KSPGetOperatorsSet(ksp,&operator_set,nullptr));
    if(operator_set) {
        Mat matrix=nullptr;
        PetscCall(KSPGetOperators(ksp,&matrix,nullptr));
        PetscCall(MatGetSize(matrix,&rows,&columns));
        PetscCall(MatGetLocalSize(matrix,&local_rows,&local_columns));
    }
    out<<"solver_node rank="<<rank<<" path="<<path<<" prefix="<<(prefix&&*prefix?prefix:"-")
       <<" ksp="<<(kt?kt:"unset")<<" pc="<<(pt?pt:"unset")
       <<" ksp_reason="<<reason<<" ksp_reason_name="<<KSPConvergedReasons[reason]
       <<" pc_reason="<<failure<<" pc_reason_name="<<PCFailedReasons[failure]
       <<" operator_set="<<operator_set<<" operator_rows="<<rows<<" operator_columns="<<columns
       <<" operator_local_rows="<<local_rows<<" operator_local_columns="<<local_columns
       <<" last_iterations="<<iterations<<" reported_norm="<<norm<<" norm_type="<<norm_type<<'\n';
    if(!pt) return PETSC_SUCCESS;
    std::vector<std::pair<std::string,KSP>> children;
    PetscInt count=0; KSP* sub=nullptr;
    if(std::strcmp(pt,PCFIELDSPLIT)==0) {
        PCCompositeType split_type;
        PetscCall(PCFieldSplitGetType(pc,&split_type));
        if(split_type==PC_COMPOSITE_SCHUR) {
            // The ordinary getter returns the interior A00 solve, which can
            // differ from the factor's main solve. Keep field0/field1 stable
            // and expose distinct auxiliary contexts without setting them up.
            PetscCall(PCFieldSplitSchurGetSubKSP(pc,&count,&sub));
            if(count>0) children.emplace_back("field0",sub[0]);
            if(count>1) children.emplace_back("field1",sub[1]);
            KSP main=count>0?sub[0]:nullptr,upper=count>2?sub[2]:nullptr;
            PetscCall(PetscFree(sub));
            Mat schur_matrix=nullptr; KSP inner=nullptr;
            PetscCall(PCFieldSplitSchurGetS(pc,&schur_matrix));
            if(schur_matrix) {
                const auto error=MatSchurComplementGetKSP(schur_matrix,&inner);
                PetscCall(PCFieldSplitSchurRestoreS(pc,&schur_matrix));
                if(error) return error;
            }
            if(inner&&inner!=main) children.emplace_back("inner",inner);
            if(upper&&upper!=main&&upper!=inner) children.emplace_back("upper",upper);
        } else {
            PetscCall(PCFieldSplitGetSubKSP(pc,&count,&sub));
            for(PetscInt i=0;i<count;++i) children.emplace_back("field"+std::to_string(i),sub[i]);
            PetscCall(PetscFree(sub));
        }
        // FieldSplit arrays belong to the caller; all child KSPs are borrowed.
    } else if(std::strcmp(pt,PCSHELL)==0) {
        if(KSP bulk=deflated_fgmres_bulk_solver(pc)) children.emplace_back("deflated_bulk",bulk);
        DeflatedFgmresStats deflated;
        if(query_deflated_fgmres_stats(pc,deflated))
            out<<"deflated_fgmres_stats rank="<<rank<<" path="<<path<<" capacity="<<deflated.capacity
               <<" vectors="<<deflated.vectors<<" refreshes="<<deflated.refreshes
               <<" projections="<<deflated.projections<<" applications="<<deflated.applications
               <<" projected_applications="<<deflated.projected_applications
               <<" candidates="<<deflated.candidates<<" rank_drops="<<deflated.rank_drops
               <<" spectral_updates="<<deflated.spectral_updates<<" operator_actions="<<deflated.operator_actions
               <<" projection_reductions="<<deflated.projection_reductions
               <<" failure_reductions="<<deflated.failure_reductions
               <<" smallest_response="<<deflated.smallest_retained_response
               <<" largest_response="<<deflated.largest_retained_response<<'\n';
        if(KSP bulk=rcr_port_bulk_solver(pc)) children.emplace_back("rcr_bulk",bulk);
        if(KSP bulk=interface_patch_bulk_solver(pc)) children.emplace_back("interface_bulk",bulk);
        if(KSP auxiliary=pressure_schur_auxiliary_solver(pc)) children.emplace_back("pressure_aux",auxiliary);
        if(KSP coarse=monolithic_fsi_mg_coarse_solver(pc)) children.emplace_back("monolithic_coarse",coarse);
        MonolithicFsiMgStats multigrid;
        if(query_monolithic_fsi_mg_stats(pc,multigrid))
        {
            PetscInt schur_applications=0,zero_lift_skips=0,vanka_color_stages=0,vanka_residual_products=0;
            for(const auto& smoother:multigrid.smoothers) {
                schur_applications+=smoother.schur_applications;
                zero_lift_skips+=smoother.zero_lift_skips;
                vanka_color_stages+=smoother.patches.color_stages;
                vanka_residual_products+=smoother.patches.residual_products;
            }
            out<<"monolithic_mg_stats rank="<<rank<<" path="<<path<<" levels="<<multigrid.levels
               <<" applications="<<multigrid.applications<<" refreshes="<<multigrid.refreshes
               <<" coarse_processes="<<multigrid.coarse_processes<<" fp32="<<multigrid.single_precision
               <<" cycle="<<(multigrid.k_cycle?"k":multigrid.w_cycle?"w":"v")
               <<" level_matvecs="<<multigrid.level_matvecs<<" zero_start_skips="<<multigrid.zero_start_skips
               <<" coarse_revisits="<<multigrid.coarse_revisits
               <<" coarse_solves="<<multigrid.coarse_solves<<" coarse_iterations="<<multigrid.coarse_iterations
               <<" smoother_applications="<<multigrid.smoother_applications
               <<" coarse_krylov_directions="<<multigrid.coarse_krylov_directions
               <<" coarse_krylov_rank_drops="<<multigrid.coarse_krylov_rank_drops
               <<" coarse_krylov_rejections="<<multigrid.coarse_krylov_rejections
               <<" coarse_krylov_reductions="<<multigrid.coarse_krylov_reductions
               <<" coarse_krylov_max_residual_ratio="<<multigrid.coarse_krylov_max_residual_ratio
               <<" fp32_value_bytes="<<multigrid.fp32_value_bytes
               <<" matrix_free_fine_actions="<<multigrid.matrix_free_fine_actions
               <<" fine_bootstrap_actions="<<multigrid.fine_bootstrap_actions
               <<" hierarchy_rebuilds="<<multigrid.hierarchy_rebuilds
               <<" divergence_rebuilds="<<multigrid.divergence_rebuilds
               <<" drift_rebuilds="<<multigrid.drift_rebuilds
               <<" age_rebuilds="<<multigrid.age_rebuilds
               <<" unchanged_divergence_reuses="<<multigrid.unchanged_divergence_reuses
               <<" hierarchy_reuses="<<multigrid.hierarchy_reuses<<" symbolic_reuses="<<multigrid.symbolic_reuses
               <<" adaptive_rebuilds="<<multigrid.adaptive_rebuilds<<" adaptive_probes="<<multigrid.adaptive_probes
               <<" batched_reduction_groups="<<multigrid.batched_reduction_groups
               <<" operator_complexity="<<multigrid.operator_complexity
               <<" hierarchy_numeric_drift="<<multigrid.hierarchy_numeric_drift
               <<" adaptive_residual_ratio="<<multigrid.adaptive_residual_ratio
               <<" schur_applications="<<schur_applications
               <<" braess_zero_lift_skips="<<zero_lift_skips
               <<" vanka_color_stages="<<vanka_color_stages
               <<" vanka_residual_products="<<vanka_residual_products<<'\n';
        }
        InterfacePatchPcStats patch_stats;
        if(query_interface_patch_pc_stats(pc,patch_stats))
            out<<"interface_patch_stats rank="<<rank<<" path="<<path<<" patches="<<patch_stats.patches
               <<" largest_patch="<<patch_stats.largest_patch<<" rebuilds="<<patch_stats.rebuilds
               <<" applications="<<patch_stats.applications<<" fp32="<<patch_stats.fp32_patches
               <<" fp64="<<patch_stats.fp64_patches<<" setup_fallbacks="<<patch_stats.setup_fallbacks
               <<" apply_fallbacks="<<patch_stats.apply_fallbacks<<" refinements="<<patch_stats.refinements
               <<" factor_batches="<<patch_stats.factor_batches<<" numeric_factorizations="<<patch_stats.numeric_factorizations
               <<" cached_factorizations="<<patch_stats.cached_factorizations
               <<" factor_bytes="<<patch_stats.factor_bytes<<'\n';
        RcrPortPcStats stats;
        if(query_rcr_port_pc_stats(pc,stats))
            out<<"rcr_port_stats rank="<<rank<<" path="<<path<<" ports="<<stats.ports
               <<" rebuilds="<<stats.rebuilds<<" responses="<<stats.response_solves
               <<" setup_reductions="<<stats.setup_reductions<<" applications="<<stats.applications
               <<" apply_reductions="<<stats.apply_reductions
               <<" exact_bulk_actions="<<stats.exact_bulk_actions<<'\n';
    } else if(std::strcmp(pt,PCASM)==0||std::strcmp(pt,PCBJACOBI)==0) {
        if(std::strcmp(pt,PCASM)==0) { PetscCall(PCASMGetSubKSP(pc,&count,nullptr,&sub)); }
        else { PetscCall(PCBJacobiGetSubKSP(pc,&count,nullptr,&sub)); }
        for(PetscInt i=0;i<count;++i) children.emplace_back("local"+std::to_string(i),sub[i]);
        // ASM/BJacobi 的数组也为借用，不能释放。
    } else if(std::strcmp(pt,PCMG)==0||std::strcmp(pt,PCGAMG)==0) {
        PetscCall(PCMGGetLevels(pc,&count));
        for(PetscInt level=0;level<count;++level) {
            KSP smoother; PetscCall(PCMGGetSmoother(pc,level,&smoother));
            children.emplace_back(level?"down"+std::to_string(level):"coarse",smoother);
        }
    }
    for(const auto& child:children) {
        const auto child_path=path+"/"+child.first;
        const auto error=describe_solver(child.second,rank,child_path,visited,out);
        if(error) out<<"solver_node_unavailable rank="<<rank<<" path="<<child_path<<" petsc_error="<<error<<'\n';
    }
    return PETSC_SUCCESS;
}
std::string local_solver_report(KSP ksp,int rank)
{
    std::ostringstream out; out<<std::setprecision(16);
    std::set<KSP> visited;
    // 部分 setup 失败时子求解器可能尚不存在；诊断失败不能覆盖原求解失败。
    const auto handler_error=PetscPushErrorHandler(PetscReturnErrorHandler,nullptr);
    if(handler_error) return "solver_node_unavailable rank="+std::to_string(rank)+" error=handler\n";
    const auto error=describe_solver(ksp,rank,"root",visited,out);
    const auto pop_error=PetscPopErrorHandler();
    if(error||pop_error) out<<"solver_node_unavailable rank="<<rank<<" path=root petsc_error="<<(error?error:pop_error)<<'\n';
    return out.str();
}
bool accepted(const FieldResidual& f)
{
    return std::isfinite(f.rms)&&std::isfinite(f.limit)&&std::isfinite(f.constraint_max)&&
        f.rms<=f.limit&&f.constraint_max<=f.tolerance.constraint_tolerance;
}
// LAPACK-style scaled sum of squares plus the independent constraint maximum.
// Every reduction item is exactly three doubles; no global maximum pass is
// required and neither very small nor very large finite residuals are squared.
void merge_field_norms(void* input,void* output,int* count,MPI_Datatype*)
{
    const auto* in=static_cast<const double*>(input);
    auto* out=static_cast<double*>(output);
    for(int i=0;i<*count;++i) {
        const auto k=3*i;
        const double a=in[k],b=out[k];
        if(!std::isfinite(a)||!std::isfinite(b)) {
            out[k]=std::numeric_limits<double>::infinity(); out[k+1]=1.;
        } else if(a>b) {
            const double ratio=b/a;
            out[k]=a; out[k+1]=in[k+1]+out[k+1]*ratio*ratio;
        } else if(b>0) {
            const double ratio=a/b;
            out[k+1]+=in[k+1]*ratio*ratio;
        }
        out[k+2]=std::max(in[k+2],out[k+2]);
    }
}
struct FieldAcceptance {
    MPI_Comm comm;
    std::vector<FieldResidual> values;
    std::vector<std::vector<PetscInt>> equations,constraints;
    std::vector<double> squares,sums,peaks,maxima;
    bool has_constraints=false;
    PetscBool fused_reductions=PETSC_TRUE;
    MPI_Datatype norm_type=MPI_DATATYPE_NULL;
    MPI_Op norm_operation=MPI_OP_NULL;
    std::vector<double> local_norms,global_norms;
    PetscInt reduction_calls=0;

    FieldAcceptance(MPI_Comm communicator,const AlgebraLayout& l,const SolverConfig& config,
                    const std::vector<PetscInt>& bc):comm(communicator) {
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_fused_reductions",&fused_reductions,nullptr));
        if(!config.fields.empty()) {
            for(const auto& f:config.fields) if(!l.fields.count(f.first))
                throw std::runtime_error("Unknown solver field for this layout: "+f.first);
            for(const auto& f:l.fields) if(!config.fields.count(f.first))
                throw std::runtime_error("Missing solver field: "+f.first);
        }
        std::vector<bool> fixed(l.owned,false),seen(l.owned,false);
        int invalid=l.fields.empty(),any_invalid=0;
        for(auto id:bc) {
            if(id<l.begin||id>=l.begin+l.owned) { invalid=1; continue; }
            if(fixed[id-l.begin]) invalid=1;
            fixed[id-l.begin]=true;
        }
        for(const auto& f:l.fields) {
            FieldResidual entry; entry.name=f.first;
            if(config.fields.empty()) {
                entry.tolerance.absolute_tolerance=entry.tolerance.constraint_tolerance=config.absolute_tolerance;
                entry.tolerance.relative_tolerance=config.relative_tolerance;
            } else entry.tolerance=config.fields.at(f.first);
            values.push_back(entry); equations.emplace_back(); constraints.emplace_back();
            for(auto id:f.second) {
                if(id<l.begin||id>=l.begin+l.owned) { invalid=1; continue; }
                const auto row=id-l.begin;
                if(seen[row]) invalid=1;
                seen[row]=true;
                (fixed[row]?constraints.back():equations.back()).push_back(row);
            }
        }
        for(bool present:seen) if(!present) invalid=1;
        const int local_policy[]{invalid,int(fused_reductions),int(!fused_reductions)};
        int global_policy[3]{};
        MPI_Allreduce(local_policy,global_policy,3,MPI_INT,MPI_MAX,comm);
        any_invalid=global_policy[0];
        if(global_policy[1]&&global_policy[2])
            throw std::runtime_error("Nonlinear fused reduction policy must agree on every rank");
        if(any_invalid) throw std::runtime_error("Nonlinear fields must partition owned rows and constraints must be unique/owned");
        std::vector<PetscInt> local(2*values.size()),global(local.size());
        for(std::size_t i=0;i<values.size();++i) {
            local[2*i]=equations[i].size(); local[2*i+1]=constraints[i].size();
        }
        MPI_Allreduce(local.data(),global.data(),static_cast<int>(global.size()),MPIU_INT,MPI_SUM,comm);
        for(std::size_t i=0;i<values.size();++i) {
            values[i].equation_rows=global[2*i]; values[i].constraint_rows=global[2*i+1];
            has_constraints=has_constraints||global[2*i+1]>0;
        }
        squares.resize(values.size()); sums.resize(values.size());
        peaks.resize(2*values.size()); maxima.resize(2*values.size());
        if(fused_reductions) {
            local_norms.resize(3*values.size()); global_norms.resize(3*values.size());
            if(MPI_Type_contiguous(3,MPI_DOUBLE,&norm_type)!=MPI_SUCCESS||
               MPI_Type_commit(&norm_type)!=MPI_SUCCESS||
               MPI_Op_create(merge_field_norms,1,&norm_operation)!=MPI_SUCCESS)
                throw std::runtime_error("Cannot create nonlinear field norm reduction");
        }
    }
    ~FieldAcceptance() {
        if(norm_operation!=MPI_OP_NULL) MPI_Op_free(&norm_operation);
        if(norm_type!=MPI_DATATYPE_NULL) MPI_Type_free(&norm_type);
    }
    FieldAcceptance(const FieldAcceptance&)=delete;
    FieldAcceptance& operator=(const FieldAcceptance&)=delete;
    void measure(Vec r,bool initial=false) {
        const PetscScalar* a;
        EONSIM_PETSC(VecGetArrayRead(r,&a));
        if(fused_reductions) {
            std::fill(local_norms.begin(),local_norms.end(),0.);
            for(std::size_t i=0;i<values.size();++i) {
                auto* norm=local_norms.data()+3*i;
                for(auto row:equations[i]) {
                    const double v=std::abs(a[row]/values[i].tolerance.residual_scale);
                    if(!std::isfinite(v)) {norm[0]=std::numeric_limits<double>::infinity();norm[1]=1.;}
                    else if(v>norm[0]) {
                        const double ratio=norm[0]/v;
                        norm[1]=1.+norm[1]*ratio*ratio; norm[0]=v;
                    } else if(norm[0]>0&&std::isfinite(norm[0])) {
                        const double ratio=v/norm[0]; norm[1]+=ratio*ratio;
                    }
                }
                for(auto row:constraints[i]) {
                    const double v=std::abs(a[row]/values[i].tolerance.constraint_scale);
                    norm[2]=std::isfinite(v)?std::max(norm[2],v):std::numeric_limits<double>::infinity();
                }
            }
            EONSIM_PETSC(VecRestoreArrayRead(r,&a));
            if(MPI_Allreduce(local_norms.data(),global_norms.data(),static_cast<int>(values.size()),
                             norm_type,norm_operation,comm)!=MPI_SUCCESS)
                throw std::runtime_error("Nonlinear field norm reduction failed");
            ++reduction_calls;
            for(std::size_t i=0;i<values.size();++i) {
                maxima[2*i]=global_norms[3*i]; maxima[2*i+1]=global_norms[3*i+2];
                sums[i]=global_norms[3*i+1];
            }
        } else {
        std::fill(squares.begin(),squares.end(),0.);
        std::fill(peaks.begin(),peaks.end(),0.);
        for(std::size_t i=0;i<values.size();++i) {
            const auto& t=values[i].tolerance;
            for(auto row:equations[i]) {
                const double v=std::abs(a[row]/t.residual_scale);
                peaks[2*i]=std::isfinite(v)?std::max(peaks[2*i],v):std::numeric_limits<double>::infinity();
            }
            for(auto row:constraints[i]) {
                const double v=std::abs(a[row]/t.constraint_scale);
                peaks[2*i+1]=std::isfinite(v)?std::max(peaks[2*i+1],v):std::numeric_limits<double>::infinity();
            }
        }
        MPI_Allreduce(peaks.data(),maxima.data(),static_cast<int>(maxima.size()),MPI_DOUBLE,MPI_MAX,comm);
        // 先归一化再平方，避免极小/极大残量的平方下溢/上溢改变接受结论。
        for(std::size_t i=0;i<values.size();++i) if(maxima[2*i]>0&&std::isfinite(maxima[2*i]))
            for(auto row:equations[i]) {
                const double v=(a[row]/values[i].tolerance.residual_scale)/maxima[2*i];
                squares[i]+=v*v;
            }
        EONSIM_PETSC(VecRestoreArrayRead(r,&a));
        // 各字段合并规约；物理方程用 RMS，约束用最大误差，避免局部违约被大量零行稀释。
        MPI_Allreduce(squares.data(),sums.data(),static_cast<int>(sums.size()),MPI_DOUBLE,MPI_SUM,comm);
        reduction_calls+=2;
        }
        for(std::size_t i=0;i<values.size();++i) {
            auto& f=values[i];
            f.rms=std::isfinite(maxima[2*i])?(f.equation_rows?maxima[2*i]*std::sqrt(sums[i]/f.equation_rows):0):maxima[2*i];
            f.constraint_max=maxima[2*i+1];
            if(initial) {
                f.initial_rms=f.rms;
                f.limit=f.tolerance.absolute_tolerance+f.tolerance.relative_tolerance*f.initial_rms;
                if(!std::isfinite(f.initial_rms)||!std::isfinite(f.limit))
                    throw StepRejected("Nonfinite initial field residual or limit: "+f.name);
            }
        }
    }
    bool passes() const { return std::all_of(values.begin(),values.end(),accepted); }
    void report() const {
        int rank; MPI_Comm_rank(comm,&rank);
        if(rank) return;
        std::ostringstream out; out<<std::setprecision(16);
        for(const auto& f:values) out<<"field_residual name="<<f.name<<" equation_rows="<<f.equation_rows
            <<" constraint_rows="<<f.constraint_rows<<" residual_scale="<<f.tolerance.residual_scale
            <<" initial_rms="<<f.initial_rms<<" rms="<<f.rms<<" limit="<<f.limit
            <<" constraint_scale="<<f.tolerance.constraint_scale<<" constraint_max="<<f.constraint_max
            <<" constraint_limit="<<f.tolerance.constraint_tolerance<<" accepted="<<accepted(f)<<'\n';
        std::cout<<out.str();
    }
};
// The Jacobian and residual stay current. Only the application of P may use
// bounded old numerical factors, with a collective drift/age/iteration policy.
// Setting SNES's PC lag in its Jacobian callback avoids relying on KSP's
// presolve/setup ordering (which changed in PETSc 3.26).
struct AdaptivePcState {
    bool enabled=false,ready=false,force=true,pending=false,pending_rebuild=false,failed_reuse=false;
    PetscInt maximum_reuse=4,age=0,reference_iterations=0;
    PetscInt rebuilds=0,reuses=0,drift_rebuilds=0,age_rebuilds=0,iteration_rebuilds=0,context_rebuilds=0;
    double change_tolerance=.1,iteration_growth=1.5,monitor_seconds=0;
    bool iteration_trigger=false,context_trigger=false;
    std::vector<double> time_context,reference_diagonal,reference_row_sum;
    PetscOwner<Vec,VecDestroy> diagonal,row_sum;
    void initialize(MPI_Comm comm,Mat matrix,bool eligible,KSP solver) {
        PetscBool requested=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_adaptive_pc",&requested,nullptr));
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-nonlinear_pc_max_reuse",&maximum_reuse,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_pc_change_tolerance",&change_tolerance,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_pc_iteration_growth",&iteration_growth,nullptr));
        KSPType type=nullptr; EONSIM_PETSC(KSPGetType(solver,&type));
        const double settings[]={static_cast<double>(requested),static_cast<double>(maximum_reuse),
            change_tolerance,iteration_growth};
        double low[4]{},high[4]{};
        MPI_Allreduce(settings,low,4,MPI_DOUBLE,MPI_MIN,comm);
        MPI_Allreduce(settings,high,4,MPI_DOUBLE,MPI_MAX,comm);
        bool valid=std::equal(low,low+4,high)&&maximum_reuse>=1&&maximum_reuse<=1000&&
            std::isfinite(change_tolerance)&&change_tolerance>0&&change_tolerance<=1&&
            std::isfinite(iteration_growth)&&iteration_growth>=1;
        valid=valid&&(!requested||(eligible&&type&&
            (std::strcmp(type,KSPFGMRES)==0||std::strcmp(type,KSPPIPEFGMRES)==0)));
        int bad=!valid,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
        if(any) throw std::runtime_error("Adaptive PC requires default Newton, fresh Jacobians, flexible GMRES, no manual PC lag/reuse/EW, and identical valid policy options");
        enabled=requested;
        if(enabled) {
            EONSIM_PETSC(MatCreateVecs(matrix,diagonal.put(),nullptr));
            EONSIM_PETSC(VecDuplicate(diagonal.get(),row_sum.put()));
        }
    }
    void begin_solve(const std::vector<double>& context) {
        rebuilds=reuses=drift_rebuilds=age_rebuilds=iteration_rebuilds=context_rebuilds=0;
        monitor_seconds=0; pending=false; failed_reuse=false;
        if(!enabled) return;
        // Without a physical time-coefficient token only intra-solve reuse is
        // permitted. A new caller cannot accidentally reuse unknown history.
        if(context.empty()||context!=time_context) {
            force=true;
            context_trigger=ready;
        }
        time_context=context;
    }
    bool decide(Mat matrix) {
        const auto start=std::chrono::steady_clock::now();
        EONSIM_PETSC(MatGetDiagonal(matrix,diagonal.get()));
        EONSIM_PETSC(MatGetRowSumAbs(matrix,row_sum.get()));
        PetscInt local_size=0; EONSIM_PETSC(VecGetLocalSize(diagonal.get(),&local_size));
        const PetscScalar *diag=nullptr,*rows=nullptr;
        EONSIM_PETSC(VecGetArrayRead(diagonal.get(),&diag));
        EONSIM_PETSC(VecGetArrayRead(row_sum.get(),&rows));
        double drift=0;
        if(ready) for(PetscInt i=0;i<local_size;++i) {
            const auto relative=[](double value,double reference,double scale) {
                if(!std::isfinite(value)||!std::isfinite(reference)) return std::numeric_limits<double>::infinity();
                if(!std::isfinite(scale)) return std::numeric_limits<double>::infinity();
                return scale>0?std::abs(value/scale-reference/scale):0.;
            };
            // Stabilized pressure diagonals may be tiny compared with the
            // velocity-pressure couplings in the same row. Normalize both
            // samples by that row's absolute sum, not by a near-zero diagonal;
            // unrelated physical fields still never share one global scale.
            const double scale=std::max(std::abs(rows[i]),std::abs(reference_row_sum[i]));
            drift=std::max({drift,relative(diag[i],reference_diagonal[i],scale),
                           relative(rows[i],reference_row_sum[i],scale)});
        }
        double local[]={drift,static_cast<double>(!ready||force||age>=maximum_reuse||iteration_trigger)},global[2]{};
        MPI_Allreduce(local,global,2,MPI_DOUBLE,MPI_MAX,PetscObjectComm(reinterpret_cast<PetscObject>(matrix)));
        const bool rebuild=global[1]!=0||global[0]>change_tolerance;
        if(rebuild) {
            reference_diagonal.resize(local_size); reference_row_sum.resize(local_size);
            for(PetscInt i=0;i<local_size;++i) {
                reference_diagonal[i]=diag[i]; reference_row_sum[i]=rows[i];
            }
            if(ready&&global[0]>change_tolerance) ++drift_rebuilds;
            if(ready&&age>=maximum_reuse) ++age_rebuilds;
            if(iteration_trigger) ++iteration_rebuilds;
            if(context_trigger) ++context_rebuilds;
            ++rebuilds;
            age=0; force=false; iteration_trigger=false; context_trigger=false;
        } else ++reuses;
        EONSIM_PETSC(VecRestoreArrayRead(row_sum.get(),&rows));
        EONSIM_PETSC(VecRestoreArrayRead(diagonal.get(),&diag));
        pending=true; pending_rebuild=rebuild;
        monitor_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        return rebuild;
    }
    PetscErrorCode complete(KSP solver) {
        if(!enabled||!pending) return PETSC_SUCCESS;
        KSPConvergedReason reason; PetscInt iterations=0;
        PetscCall(KSPGetConvergedReason(solver,&reason));
        PetscCall(KSPGetIterationNumber(solver,&iterations));
        pending=false;
        failed_reuse=!pending_rebuild&&reason==KSP_DIVERGED_ITS;
        if(reason<=0) { ready=false; force=true; return PETSC_SUCCESS; }
        ready=true;
        if(pending_rebuild) reference_iterations=iterations;
        else {
            ++age;
            const double threshold=std::max(static_cast<double>(reference_iterations+2),
                                             iteration_growth*reference_iterations);
            if(iterations>threshold) iteration_trigger=true;
        }
        return PETSC_SUCCESS;
    }
};
/** Optional inexact forcing and a bounded recycled correction space. The
 * retained directions are combinations generated by earlier Krylov solves;
 * their images are recomputed with the CURRENT operator before every use.
 * No old Jacobian, RHS, or nonlinear/physical state is reused. */
struct LinearPolicy {
    bool inexact=false;
    PetscInt capacity=0,deflation_capacity=0,forcing_solves=0,projections=0;
    double initial_eta=.1,maximum_eta=.5,gamma=.9,alpha=1.5;
    double base_rtol=0,base_atol=0,base_dtol=0,requested_rtol=0,previous_rhs=0,previous_eta=0;
    PetscInt maximum_iterations=0;
    double seconds=0;
    std::vector<PetscOwner<Vec,VecDestroy>> basis;
    PetscOwner<Vec,VecDestroy> residual;
    bool active() const { return inexact||capacity>0||deflation_capacity>0; }
    void initialize(MPI_Comm comm,KSP ksp,Vec prototype,bool eligible) {
        PetscBool requested=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_inexact_newton",&requested,nullptr));
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-nonlinear_krylov_recycle",&capacity,nullptr));
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-nonlinear_krylov_deflation",&deflation_capacity,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_forcing_initial",&initial_eta,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_forcing_max",&maximum_eta,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_forcing_gamma",&gamma,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-nonlinear_forcing_alpha",&alpha,nullptr));
        EONSIM_PETSC(KSPGetTolerances(ksp,&base_rtol,&base_atol,&base_dtol,&maximum_iterations));
        const double values[]={double(requested),double(capacity),initial_eta,maximum_eta,gamma,alpha,double(deflation_capacity)};
        double low[7]{},high[7]{};
        MPI_Allreduce(values,low,7,MPI_DOUBLE,MPI_MIN,comm);
        MPI_Allreduce(values,high,7,MPI_DOUBLE,MPI_MAX,comm);
        KSPType type=nullptr; PetscBool scaled=PETSC_FALSE,nonzero=PETSC_FALSE,knoll=PETSC_FALSE;
        EONSIM_PETSC(KSPGetType(ksp,&type)); EONSIM_PETSC(KSPGetDiagonalScale(ksp,&scaled));
        EONSIM_PETSC(KSPGetInitialGuessNonzero(ksp,&nonzero)); EONSIM_PETSC(KSPGetInitialGuessKnoll(ksp,&knoll));
        bool other_guess=false;
        for(const char* name:{"-ksp_guess_type","-ksp_fischer_guess"}) {
            PetscBool found=PETSC_FALSE; EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name,&found));
            other_guess=other_guess||found;
        }
        bool valid=std::equal(low,low+7,high)&&capacity>=0&&capacity<=32&&
            deflation_capacity>=0&&deflation_capacity<=32&&!(capacity&&deflation_capacity)&&
            std::isfinite(initial_eta)&&std::isfinite(maximum_eta)&&std::isfinite(gamma)&&std::isfinite(alpha)&&
            initial_eta>0&&initial_eta<=maximum_eta&&maximum_eta<1&&gamma>0&&gamma<=1&&alpha>1&&alpha<=2;
        if(requested||capacity||deflation_capacity) valid=valid&&eligible&&!scaled&&type&&
            (std::strcmp(type,KSPFGMRES)==0||std::strcmp(type,KSPPIPEFGMRES)==0);
        if(deflation_capacity) valid=valid&&type&&std::strcmp(type,KSPFGMRES)==0;
        if(requested) valid=valid&&base_rtol>0&&base_rtol<=initial_eta;
        if(capacity||deflation_capacity) valid=valid&&!nonzero&&!knoll&&!other_guess;
        int invalid=!valid,any=0; MPI_Allreduce(&invalid,&any,1,MPI_INT,MPI_MAX,comm);
        if(any) throw std::runtime_error("Inexact Newton/recycling requires ordinary fresh Newton, flexible GMRES, identical bounded forcing options, no diagonal scaling or conflicting initial-guess policy; deflation requires fgmres and cannot combine with correction warm starts");
        inexact=requested;
        if(active()) EONSIM_PETSC(VecDuplicate(prototype,residual.put()));
    }
    void begin_solve(KSP ksp) {
        forcing_solves=projections=0; previous_rhs=0; previous_eta=initial_eta; seconds=0;
        requested_rtol=base_rtol;
        if(deflation_capacity) { PC pc=nullptr; EONSIM_PETSC(KSPGetPC(ksp,&pc)); reset_deflated_fgmres_stats(pc); }
        if(inexact) EONSIM_PETSC(KSPSetTolerances(ksp,base_rtol,base_atol,base_dtol,maximum_iterations));
    }
    void before(KSP ksp,Vec b,Vec x) {
        if(!active()) return;
        PetscReal rhs=0; EONSIM_PETSC(VecNorm(b,NORM_2,&rhs));
        if(!std::isfinite(rhs)) throw std::runtime_error("Nonfinite inexact Newton right-hand side");
        if(inexact) {
            double eta=initial_eta;
            if(previous_rhs>0) {
                eta=gamma*std::pow(rhs/previous_rhs,alpha);
                // EW-II safeguard avoids an abrupt oversolve after a single
                // unusually successful Newton step; the original tolerance
                // is the lower bound, never a relaxed final acceptance gate.
                const double safeguard=gamma*std::pow(previous_eta,alpha);
                if(safeguard>.1) eta=std::max(eta,safeguard);
            }
            requested_rtol=std::clamp(eta,base_rtol,maximum_eta);
            previous_eta=requested_rtol; previous_rhs=rhs; ++forcing_solves;
            EONSIM_PETSC(KSPSetTolerances(ksp,requested_rtol,base_atol,base_dtol,maximum_iterations));
        }
        if(deflation_capacity) {
            const auto start=std::chrono::steady_clock::now();
            prepare_deflated_fgmres(ksp,b,x);
            seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            return;
        }
        if(!capacity) return;
        const auto start=std::chrono::steady_clock::now();
        EONSIM_PETSC(KSPSetInitialGuessNonzero(ksp,PETSC_FALSE));
        EONSIM_PETSC(VecSet(x,0.));
        if(rhs>0&&!basis.empty()) {
            Mat a=nullptr; EONSIM_PETSC(KSPGetOperators(ksp,&a,nullptr));
            std::vector<PetscOwner<Vec,VecDestroy>> directions,images;
            for(const auto& stored:basis) {
                PetscOwner<Vec,VecDestroy> u,c;
                EONSIM_PETSC(VecDuplicate(x,u.put())); EONSIM_PETSC(VecDuplicate(x,c.put()));
                EONSIM_PETSC(VecCopy(stored.get(),u.get())); EONSIM_PETSC(MatMult(a,u.get(),c.get()));
                PetscReal original=0; EONSIM_PETSC(VecNorm(c.get(),NORM_2,&original));
                if(!std::isfinite(original)) throw std::runtime_error("Nonfinite current recycled operator image");
                for(int pass=0;pass<2;++pass) for(std::size_t i=0;i<images.size();++i) {
                    PetscScalar coefficient=0; EONSIM_PETSC(VecDot(images[i].get(),c.get(),&coefficient));
                    EONSIM_PETSC(VecAXPY(c.get(),-coefficient,images[i].get()));
                    EONSIM_PETSC(VecAXPY(u.get(),-coefficient,directions[i].get()));
                }
                PetscReal norm=0; EONSIM_PETSC(VecNorm(c.get(),NORM_2,&norm));
                if(!std::isfinite(norm)) throw std::runtime_error("Nonfinite orthogonalized recycled operator image");
                if(norm<=128*std::numeric_limits<double>::epsilon()*original||norm==0) continue;
                EONSIM_PETSC(VecScale(c.get(),1./norm)); EONSIM_PETSC(VecScale(u.get(),1./norm));
                PetscScalar coefficient=0; EONSIM_PETSC(VecDot(c.get(),b,&coefficient));
                EONSIM_PETSC(VecAXPY(x,coefficient,u.get()));
                directions.push_back(std::move(u)); images.push_back(std::move(c));
            }
            // Reject a numerically harmful projection; this is only a starting
            // guess, so zero is always a safe fallback for the same equations.
            EONSIM_PETSC(MatMult(a,x,residual.get())); EONSIM_PETSC(VecAXPY(residual.get(),-1.,b));
            PetscReal norm=0; EONSIM_PETSC(VecNorm(residual.get(),NORM_2,&norm));
            if(std::isfinite(norm)&&norm<rhs&&!images.empty()) {
                EONSIM_PETSC(KSPSetInitialGuessNonzero(ksp,PETSC_TRUE)); ++projections;
            } else EONSIM_PETSC(VecSet(x,0.));
        }
        seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    }
    void after(KSP ksp,Vec b,Vec x) {
        if(!active()) return;
        KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(ksp,&reason));
        if(reason>0) {
            Mat a=nullptr; EONSIM_PETSC(KSPGetOperators(ksp,&a,nullptr));
            EONSIM_PETSC(MatMult(a,x,residual.get())); EONSIM_PETSC(VecAXPY(residual.get(),-1.,b));
            PetscReal error=0,rhs=0;
            EONSIM_PETSC(VecNorm(residual.get(),NORM_2,&error)); EONSIM_PETSC(VecNorm(b,NORM_2,&rhs));
            const double limit=base_atol+requested_rtol*rhs;
            if(!std::isfinite(error)||!std::isfinite(rhs)||!std::isfinite(limit)||
               error>limit*(1+64*std::numeric_limits<double>::epsilon()))
                throw std::runtime_error("Inexact/recycled correction failed current-operator true residual gate");
            if(deflation_capacity) {
                const auto start=std::chrono::steady_clock::now();
                complete_deflated_fgmres(ksp,x);
                seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            }
            if(capacity) {
                const auto start=std::chrono::steady_clock::now();
                // Keep recent independent correction directions, with bounded
                // distributed vector storage. Failure retires the workspace.
                if(basis.size()==static_cast<std::size_t>(capacity)) basis.erase(basis.begin());
                PetscOwner<Vec,VecDestroy> candidate;
                EONSIM_PETSC(VecDuplicate(x,candidate.put())); EONSIM_PETSC(VecCopy(x,candidate.get()));
                PetscReal original=0; EONSIM_PETSC(VecNorm(candidate.get(),NORM_2,&original));
                for(int pass=0;pass<2;++pass) for(const auto& q:basis) {
                    PetscScalar coefficient=0; EONSIM_PETSC(VecDot(q.get(),candidate.get(),&coefficient));
                    EONSIM_PETSC(VecAXPY(candidate.get(),-coefficient,q.get()));
                }
                PetscReal norm=0; EONSIM_PETSC(VecNorm(candidate.get(),NORM_2,&norm));
                if(std::isfinite(norm)&&norm>128*std::numeric_limits<double>::epsilon()*original&&norm>0) {
                    EONSIM_PETSC(VecScale(candidate.get(),1./norm)); basis.push_back(std::move(candidate));
                }
                seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            }
        }
        if(inexact) EONSIM_PETSC(KSPSetTolerances(ksp,base_rtol,base_atol,base_dtol,maximum_iterations));
    }
};
struct LinearDiagnostics {
    std::optional<FieldAcceptance> fields;
    PetscOwner<Vec,VecDestroy> residual;
    std::chrono::steady_clock::time_point begin;
    double solve_seconds=0,diagnostic_seconds=0;
    PetscInt started=0,completed=0;
    bool enabled=false;
    AdaptivePcState* adaptive_pc=nullptr;
    LinearPolicy* policy=nullptr;
    std::string policy_error;
    int collective_pc_failure=0;
    void reset() {
        solve_seconds=diagnostic_seconds=0.;
        started=completed=0; collective_pc_failure=0; policy_error.clear();
    }
};
PetscErrorCode linear_begin(KSP ksp,Vec b,Vec x,void* pointer)
{
    auto& d=*static_cast<LinearDiagnostics*>(pointer);
    ++d.started; d.begin=std::chrono::steady_clock::now();
    try { if(d.policy) d.policy->before(ksp,b,x); }
    catch(const std::exception& e) { d.policy_error=e.what(); return PETSC_ERR_LIB; }
    return PETSC_SUCCESS;
}
PetscErrorCode linear_end(KSP ksp,Vec b,Vec x,void* pointer)
{
    auto& d=*static_cast<LinearDiagnostics*>(pointer);
    const auto end=std::chrono::steady_clock::now();
    d.solve_seconds+=std::chrono::duration<double>(end-d.begin).count();
    ++d.completed;
    if(!d.fields) return PETSC_SUCCESS;
    // 使用实际 KSP 算子和右端项；独立副本不改变非线性验收基线。
    // An exhausted KSP returns its last iterate. Other failures may leave x undefined; diagonal scaling changes coordinates.
    try {
        KSPConvergedReason reason; PetscBool scaled;
        EONSIM_PETSC(KSPGetConvergedReason(ksp,&reason));
        EONSIM_PETSC(KSPGetDiagonalScale(ksp,&scaled));
        int rank; MPI_Comm_rank(d.fields->comm,&rank);
        const bool iteration_limit=reason==KSP_DIVERGED_ITS;
        if((reason<=0&&!iteration_limit)||scaled) {
            if(rank==0) std::cout<<"linear_residual_unavailable solve="<<d.completed
                <<" reason="<<(scaled?"diagonal_scaling":"unconverged")<<'\n';
        } else {
            Mat a; EONSIM_PETSC(KSPGetOperators(ksp,&a,nullptr));
            EONSIM_PETSC(MatMult(a,x,d.residual.get()));
            EONSIM_PETSC(VecAXPY(d.residual.get(),-1.,b));
            PetscReal norm,rhs;
            EONSIM_PETSC(VecNorm(d.residual.get(),NORM_2,&norm));
            EONSIM_PETSC(VecNorm(b,NORM_2,&rhs));
            d.fields->measure(d.residual.get());
            if(rank==0) {
                std::ostringstream out; out<<std::setprecision(16);
                const char* prefix=iteration_limit?"linear_iteration_limit":"linear";
                out<<prefix<<"_residual solve="<<d.completed<<" norm="<<norm<<" rhs_norm="<<rhs;
                if(d.policy&&d.policy->active()) out<<" requested_rtol="<<d.policy->requested_rtol
                    <<" requested_atol="<<d.policy->base_atol<<" forcing="<<d.policy->inexact;
                out<<'\n';
                for(const auto& f:d.fields->values)
                    out<<prefix<<"_field_residual solve="<<d.completed<<" name="<<f.name
                       <<" rms="<<f.rms<<" constraint_max="<<f.constraint_max
                       <<" residual_scale="<<f.tolerance.residual_scale
                       <<" constraint_scale="<<f.tolerance.constraint_scale<<'\n';
                std::cout<<out.str();
            }
        }
    } catch(const std::exception& e) {
        // C++ 异常不能穿越 PETSc 回调；诊断不改变原有求解失败分类。
        int rank; MPI_Comm_rank(d.fields->comm,&rank);
        if(rank==0) std::cout<<"linear_residual_unavailable solve="<<d.completed<<" detail="<<e.what()<<'\n';
    }
    d.diagnostic_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-end).count();
    return PETSC_SUCCESS;
}
// PETSc 3.19 PREONLY can return success on one rank and PC_FAILED on another
// (src/ksp/ksp/impls/preonly/preonly.c). Protect solver control flow BEFORE
// diagnostics or SNES branch on that rank-local reason. This safety check is
// independent of reporting; it neither sets up a PC nor changes a reason code.
PetscErrorCode linear_complete(KSP ksp,Vec b,Vec x,void* pointer)
{
    auto& d=*static_cast<LinearDiagnostics*>(pointer);
#if PETSC_VERSION_LT(3,20,0)
    PC pc; PCFailedReason failure;
    PetscCall(KSPGetPC(ksp,&pc));
    PetscCall(PCGetFailedReasonRank(pc,&failure));
    // PC_SETUP_ERROR is negative in 3.19: reduce a flag, not the enum value.
    const int local=failure!=PC_NOERROR;
    PetscCallMPI(MPI_Allreduce(&local,&d.collective_pc_failure,1,MPI_INT,MPI_MAX,
                              PetscObjectComm(reinterpret_cast<PetscObject>(ksp))));
    if(d.collective_pc_failure) return PETSC_ERR_NOT_CONVERGED;
#endif
    if(d.adaptive_pc) PetscCall(d.adaptive_pc->complete(ksp));
    try { if(d.policy) d.policy->after(ksp,b,x); }
    catch(const std::exception& e) { d.policy_error=e.what(); return PETSC_ERR_LIB; }
    if(d.enabled) return linear_end(ksp,b,x,pointer);
    return PETSC_SUCCESS;
}

void local_values(Vec x,std::vector<double>& values)
{
    EONSIM_PETSC(VecGhostUpdateBegin(x,INSERT_VALUES,SCATTER_FORWARD));
    EONSIM_PETSC(VecGhostUpdateEnd(x,INSERT_VALUES,SCATTER_FORWARD));
    Vec local; const PetscScalar* a; PetscInt n;
    EONSIM_PETSC(VecGhostGetLocalForm(x,&local));
    EONSIM_PETSC(VecGetLocalSize(local,&n));
    EONSIM_PETSC(VecGetArrayRead(local,&a));
    if(n) values.assign(a,a+n);
    else values.clear();
    EONSIM_PETSC(VecRestoreArrayRead(local,&a));
    EONSIM_PETSC(VecGhostRestoreLocalForm(x,&local));
}
void prepare_residual_coo(Vec vector,const std::vector<PetscInt>& rows,
                          std::vector<PetscObjectId>& prepared)
{
    PetscObjectId id=0;
    EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(vector),&id));
    if(std::find(prepared.begin(),prepared.end(),id)!=prepared.end()) return;
    EONSIM_PETSC(VecSetOption(vector,VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
    EONSIM_PETSC(VecSetPreallocationCOO(vector,static_cast<PetscCount>(rows.size()),rows.data()));
    // IDs cannot dangle and do not keep SNES work vectors alive. Every rank
    // sees the same sequence of callback-vector roles, even with no local COO.
    prepared.push_back(id);
}
struct Context {
    MPI_Comm comm;
    const AlgebraLayout& layout;
    const std::vector<PetscInt>& constraints;
    const std::vector<double>& prescribed;
    const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble;
    FieldAcceptance& acceptance;
    Vec scratch;
    std::vector<double>& values;
    std::vector<PetscScalar>* coo_values;
    const std::vector<PetscInt>* residual_coo_rows;
    std::vector<PetscScalar>* residual_coo_values;
    std::vector<PetscObjectId>& residual_coo_vectors;
    std::string error;
    bool recoverable=false;
    PetscInt domain_rejections=0;
    double assembly_seconds=0,ghost_seconds=0;
    double ghost_overlap_seconds=0;
    PetscInt ghost_exchanges=0;
    const NonlinearAssemblyPhases* phases=nullptr;
    double callback_seconds=0,failure_sync_seconds=0,assembly_finalize_seconds=0,constraint_seconds=0;
    PcSchurUpdates* pc_updates=nullptr;
    AdaptivePcState* adaptive_pc=nullptr;
    PetscInt jacobian_assemblies=0,jacobian_callbacks=0,initial_jacobian_reuses=0,user_schur_updates=0;
    Vec initial_trial=nullptr;
    Mat initial_jacobian=nullptr;
    bool matrix_free=false;
    Vec direction_ghost=nullptr;
    PetscInt assembled_pc_interval=1,matrix_free_actions=0,assembled_pc_reuses=0;
    PetscInt matrix_free_preparations=0,matrix_free_overlapped_actions=0;
    double matrix_free_seconds=0,matrix_free_overlap_seconds=0,matrix_free_ghost_seconds=0;
    PetscInt true_residual_checks=0,true_residual_rejections=0;
    double true_residual_seconds=0;
    std::vector<double> operator_state={},direction={};
    std::string action_error={}; // Fatal and sticky until this solve exits.
    void prepare_direction() {
        if(!phases||!phases->prepare_jacobian_action) return;
        int failed=0,any_failed=0;
        std::string detail;
        try { phases->prepare_jacobian_action(operator_state); }
        catch(const StepRejected& e) { failed=1; detail=e.what(); }
        catch(const std::exception& e) { failed=2; detail=e.what(); }
        catch(...) { failed=2; detail="Unknown frozen-state setup failure"; }
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
        if(any_failed) {
            int rank=0,origin=0; MPI_Comm_rank(comm,&rank);
            const int candidate=failed==any_failed?rank:std::numeric_limits<int>::max();
            MPI_Allreduce(&candidate,&origin,1,MPI_INT,MPI_MIN,comm);
            int length=static_cast<int>(detail.size()); MPI_Bcast(&length,1,MPI_INT,origin,comm);
            detail.resize(length); MPI_Bcast(detail.data(),length,MPI_CHAR,origin,comm);
            detail="Matrix-free setup origin_rank="+std::to_string(origin)+": "+detail;
            if(any_failed==1) throw StepRejected(detail);
            throw std::runtime_error(detail);
        }
        ++matrix_free_preparations;
    }
    void apply_direction(Vec input,Vec output) {
        if(!phases||!phases->jacobian_action||operator_state.size()!=layout.local_to_global.size())
            throw std::runtime_error("Matrix-free operator has no current Newton state/action");
        const auto begin=std::chrono::steady_clock::now();
        EONSIM_PETSC(VecCopy(input,direction_ghost));
        PetscScalar* entries=nullptr;
        EONSIM_PETSC(VecGetArrayWrite(output,&entries));
        std::fill_n(entries,layout.owned,0.);
        EONSIM_PETSC(VecRestoreArrayWrite(output,&entries));
        EONSIM_PETSC(VecSetOption(output,VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
        int failed=0,any_failed=0;
        std::string detail;
        const auto call=[&](const auto& action) {
            try { action(operator_state,direction,output); }
            catch(const std::exception& e) { failed=1; detail=e.what(); }
            catch(...) { failed=1; detail="Unknown directional kernel failure"; }
        };
        const auto ghost_begin=std::chrono::steady_clock::now();
        if(phases->jacobian_action_owned) {
            direction.assign(layout.local_to_global.size(),0.);
            const PetscScalar* owned=nullptr;
            EONSIM_PETSC(VecGetArrayRead(direction_ghost,&owned));
            std::copy_n(owned,layout.owned,direction.data());
            EONSIM_PETSC(VecRestoreArrayRead(direction_ghost,&owned));
            EONSIM_PETSC(VecGhostUpdateBegin(direction_ghost,INSERT_VALUES,SCATTER_FORWARD));
            const auto work_begin=std::chrono::steady_clock::now();
            matrix_free_ghost_seconds+=std::chrono::duration<double>(work_begin-ghost_begin).count();
            call(phases->jacobian_action_owned);
            const auto wait_begin=std::chrono::steady_clock::now();
            matrix_free_overlap_seconds+=std::chrono::duration<double>(wait_begin-work_begin).count();
            // An owned-phase exception cannot leave a forward exchange pending.
            EONSIM_PETSC(VecGhostUpdateEnd(direction_ghost,INSERT_VALUES,SCATTER_FORWARD));
            Vec local=nullptr; const PetscScalar* all=nullptr;
            EONSIM_PETSC(VecGhostGetLocalForm(direction_ghost,&local));
            EONSIM_PETSC(VecGetArrayRead(local,&all));
            std::copy_n(all,direction.size(),direction.data());
            EONSIM_PETSC(VecRestoreArrayRead(local,&all));
            EONSIM_PETSC(VecGhostRestoreLocalForm(direction_ghost,&local));
            matrix_free_ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-wait_begin).count();
            if(!failed) call(phases->jacobian_action_halo);
            ++matrix_free_overlapped_actions;
        } else {
            local_values(direction_ghost,direction);
            matrix_free_ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-ghost_begin).count();
            call(phases->jacobian_action);
        }
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
        // Drain off-rank entries even after a local exception, exactly as for
        // ordinary residual assembly. No pending operation outlives this call.
        EONSIM_PETSC(VecAssemblyBegin(output)); EONSIM_PETSC(VecAssemblyEnd(output));
        if(any_failed) {
            int rank=0,origin=0; MPI_Comm_rank(comm,&rank);
            const int candidate=failed?rank:std::numeric_limits<int>::max();
            MPI_Allreduce(&candidate,&origin,1,MPI_INT,MPI_MIN,comm);
            int length=static_cast<int>(detail.size()); MPI_Bcast(&length,1,MPI_INT,origin,comm);
            detail.resize(length); MPI_Bcast(detail.data(),length,MPI_CHAR,origin,comm);
            throw std::runtime_error("Matrix-free action origin_rank="+std::to_string(origin)+": "+detail);
        }
        if(!constraints.empty()) {
            EONSIM_PETSC(VecGetArray(output,&entries));
            for(const auto row:constraints) entries[row-layout.begin]=direction[row-layout.begin];
            EONSIM_PETSC(VecRestoreArray(output,&entries));
        }
        ++matrix_free_actions;
        matrix_free_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
    }
    void remember_initial_jacobian(Vec x,Mat j) {
        // The already synchronized trial buffer is the snapshot. Any later
        // physical evaluation invalidates this one-use entry before changing it.
        initial_trial=x; initial_jacobian=j;
    }
    bool consume_initial_jacobian(Vec x,Mat j) {
        if(!initial_jacobian) return false;
        int same=x==initial_trial&&j==initial_jacobian,all=0;
        initial_trial=nullptr; initial_jacobian=nullptr;
        if(same) {
            const PetscScalar* trial;
            EONSIM_PETSC(VecGetArrayRead(x,&trial));
            same=std::equal(values.begin(),values.begin()+layout.owned,trial);
            EONSIM_PETSC(VecRestoreArrayRead(x,&trial));
        }
        // A change on any owner invalidates every rank, including an empty
        // owner. No private PETSc state API or full-vector copy is required.
        if(MPI_Allreduce(&same,&all,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Initial Jacobian reuse communication failed");
        if(all) ++initial_jacobian_reuses;
        return all!=0;
    }
    void refresh_user_schur(Mat j) {
        if(!pc_updates) return;
        pc_updates->refresh(j);
        user_schur_updates+=static_cast<PetscInt>(pc_updates->refreshers.size());
    }
    void prepare_preconditioner(SNES snes,Mat j,bool user_current=false) {
        bool refresh=true;
        if(adaptive_pc&&adaptive_pc->enabled) {
            // A rejected trial cannot authorize retaining its prior factors.
            if(domain_rejections) adaptive_pc->force=true;
            refresh=adaptive_pc->decide(j);
            EONSIM_PETSC(SNESSetLagPreconditioner(snes,refresh?1:-1));
        }
        if(refresh&&!user_current) refresh_user_schur(j);
    }
    void apply_constraints(Vec r,Mat j) {
        if(!acceptance.has_constraints) return;
        // Only owned rows are replaced. A Jacobian-only callback has no
        // residual consumer, but its matrix still needs the constraint rows.
        if(r&&!constraints.empty()) {
            PetscScalar* entries;
            EONSIM_PETSC(VecGetArray(r,&entries));
            for(std::size_t i=0;i<constraints.size();++i) {
                const auto row=constraints[i]-layout.begin;
                entries[row]=values[row]-prescribed[i];
            }
            EONSIM_PETSC(VecRestoreArray(r,&entries));
        }
        if(j) EONSIM_PETSC(MatZeroRows(j,constraints.size(),constraints.data(),1,nullptr,nullptr));
    }
    void evaluate(Vec x, Vec r, Mat j, bool constrain,bool publish_residual=true) {
        if(!action_error.empty()) throw std::runtime_error(action_error);
        // A residual evaluation, rejected trial or new tangent must not leave
        // a startup Jacobian eligible for a later line-search/Newton state.
        initial_trial=nullptr; initial_jacobian=nullptr;
        const auto begin=std::chrono::steady_clock::now();
        EONSIM_PETSC(VecSetOption(r,VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
        // 极小残量的 PETSc NORM_2 可能下溢并缓存为零，VecSet(0) 会据此跳过清零。
        // 始终覆盖 owned 数据，保证重复评价不累加旧残量；最终 raw_residual 的 ghost 由 local_values 同步。
        PetscScalar* residual;
        EONSIM_PETSC(VecGetArrayWrite(r,&residual));
        std::fill_n(residual,layout.owned,0.);
        EONSIM_PETSC(VecRestoreArrayWrite(r,&residual));
        if(residual_coo_values) std::fill(residual_coo_values->begin(),residual_coo_values->end(),0.);
        if(j) {
            if(coo_values) std::fill(coo_values->begin(),coo_values->end(),0.);
            else EONSIM_PETSC(MatZeroEntries(j));
        }
        int failed=0, any_failed=0;
        error.clear(); recoverable=false;
        double callback_time=0;
        const auto call_local=[&](const auto& callback) {
            const auto start=std::chrono::steady_clock::now();
            try { callback(values,r,j); }
            catch(const StepRejected& e) { error=e.what(); failed=1; }
            catch(const std::exception& e) { error=e.what(); failed=2; }
            catch(...) { error="Unknown local assembly failure"; failed=2; }
            const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            callback_time+=elapsed;
            return elapsed;
        };
        const auto ghost_begin=std::chrono::steady_clock::now();
        ++ghost_exchanges;
        if(phases&&phases->owned) {
            // Copy the send-side state before Begin; neither PETSc storage nor
            // the receive-side ghost values are accessed by the owned phase.
            const PetscScalar* owned;
            EONSIM_PETSC(VecGetArrayRead(x,&owned));
            if(layout.owned) std::copy_n(owned,layout.owned,values.begin());
            EONSIM_PETSC(VecRestoreArrayRead(x,&owned));
            EONSIM_PETSC(VecGhostUpdateBegin(x,INSERT_VALUES,SCATTER_FORWARD));
            const auto posted=std::chrono::steady_clock::now();
            ghost_seconds+=std::chrono::duration<double>(posted-ghost_begin).count();
            ghost_overlap_seconds+=call_local(phases->owned);
            const auto wait_begin=std::chrono::steady_clock::now();
            // Complete outstanding communication even if a local kernel failed.
            // Other ranks may still be computing; error collectives come later.
            EONSIM_PETSC(VecGhostUpdateEnd(x,INSERT_VALUES,SCATTER_FORWARD));
            Vec local; const PetscScalar* entries;
            EONSIM_PETSC(VecGhostGetLocalForm(x,&local));
            EONSIM_PETSC(VecGetArrayRead(local,&entries));
            if(values.size()>static_cast<std::size_t>(layout.owned))
                std::copy_n(entries+layout.owned,values.size()-layout.owned,values.begin()+layout.owned);
            EONSIM_PETSC(VecRestoreArrayRead(local,&entries));
            EONSIM_PETSC(VecGhostRestoreLocalForm(x,&local));
            ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-wait_begin).count();
            if(!failed) call_local(phases->halo);
        } else {
            local_values(x,values);
            ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-ghost_begin).count();
            call_local(assemble);
        }
        const auto sync_begin=std::chrono::steady_clock::now();
        MPI_Allreduce(&failed,&any_failed,1,MPI_INT,MPI_MAX,comm);
        const auto assembly_begin=std::chrono::steady_clock::now();
        const double sync_time=std::chrono::duration<double>(assembly_begin-sync_begin).count();
        // 被拒试探点可能已留下远程插入；先共同完成部分装配，清空 stash，下一次评价才能重新开始。
        if(!residual_coo_values) {
            // Independent Vec/Mat stashes can communicate concurrently. Keep
            // the same Begin/End order on every rank, including rejected trials.
            EONSIM_PETSC(VecAssemblyBegin(r));
            if(j&&!coo_values) EONSIM_PETSC(MatAssemblyBegin(j,MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(VecAssemblyEnd(r));
            if(j&&!coo_values) EONSIM_PETSC(MatAssemblyEnd(j,MAT_FINAL_ASSEMBLY));
        } else {
            if(!any_failed&&publish_residual) {
                // A line search may supply its own VecDuplicate of the residual;
                // prepare that actual target once rather than assuming inheritance.
                prepare_residual_coo(r,*residual_coo_rows,residual_coo_vectors);
                EONSIM_PETSC(VecSetValuesCOO(r,residual_coo_values->data(),INSERT_VALUES));
            } else if(any_failed) {
                EONSIM_PETSC(VecAssemblyBegin(r)); EONSIM_PETSC(VecAssemblyEnd(r));
            }
            if(j&&!coo_values) {
                EONSIM_PETSC(MatAssemblyBegin(j,MAT_FINAL_ASSEMBLY));
                EONSIM_PETSC(MatAssemblyEnd(j,MAT_FINAL_ASSEMBLY));
            }
        }
        // COO publication is collective and only follows successful callbacks.
        if(j&&coo_values&&!any_failed) EONSIM_PETSC(MatSetValuesCOO(j,coo_values->data(),INSERT_VALUES));
        const auto constraint_begin=std::chrono::steady_clock::now();
        const double assembly_time=std::chrono::duration<double>(constraint_begin-assembly_begin).count();
        if(any_failed) {
            int rank,origin; MPI_Comm_rank(comm,&rank);
            const int source=failed==any_failed?rank:std::numeric_limits<int>::max();
            MPI_Allreduce(&source,&origin,1,MPI_INT,MPI_MIN,comm);
            int length=static_cast<int>(error.size()); MPI_Bcast(&length,1,MPI_INT,origin,comm);
            error.resize(length); MPI_Bcast(error.data(),length,MPI_CHAR,origin,comm);
            error="callback phase="+std::string(j?"jacobian":"residual")+
                  " origin_rank="+std::to_string(origin)+": "+error;
            if(any_failed==1) { recoverable=true; throw StepRejected(error); }
            throw std::runtime_error(error);
        }
        if(constrain) apply_constraints(publish_residual?r:nullptr,j);
        if(j&&phases&&phases->after_jacobian) phases->after_jacobian(values,j);
        const auto end=std::chrono::steady_clock::now();
        // These phase totals cover only evaluations that completed successfully, like assembly_seconds.
        callback_seconds+=callback_time;
        failure_sync_seconds+=sync_time;
        assembly_finalize_seconds+=assembly_time;
        constraint_seconds+=std::chrono::duration<double>(end-constraint_begin).count();
        assembly_seconds+=std::chrono::duration<double>(end-begin).count();
        if(j) ++jacobian_assemblies;
    }
};
struct ActiveContext { Context* current=nullptr; };
PetscErrorCode matrix_free_multiply(Mat matrix,Vec input,Vec output) {
    ActiveContext* active=nullptr;
    PetscCall(MatShellGetContext(matrix,&active));
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    if(c.action_error.empty()) {
        try { c.apply_direction(input,output); return PETSC_SUCCESS; }
        catch(const std::exception& e) {
            c.action_error=e.what(); c.error=c.action_error; c.recoverable=false;
        }
    }
    // PIPEFGMRES may have an outstanding VecMDotBegin around this action.
    // Returning an error here would skip its VecMDotEnd and poison subsequent
    // solves on the communicator. Supply finite temporary data so PETSc drains
    // the reduction, then terminate at its convergence callback. The sticky
    // error also prevents further physical kernels and any accepted result.
    PetscScalar* entries=nullptr;
    PetscCall(VecGetArrayWrite(output,&entries));
    std::fill_n(entries,c.layout.owned,0.);
    PetscCall(VecRestoreArrayWrite(output,&entries));
    return PETSC_SUCCESS;
}
struct KrylovConvergence {
    ActiveContext* callbacks=nullptr;
    bool verify_residual=false;
    PetscOwner<Vec,VecDestroy> solution_work,residual;
    PetscErrorCode (*original)(KSP,PetscInt,PetscReal,KSPConvergedReason*,void*)=nullptr;
    void* original_context=nullptr;
    PetscErrorCode (*original_destroy)(void*)=nullptr;
    ~KrylovConvergence() { if(original_destroy) (void)original_destroy(original_context); }
};
PetscErrorCode guarded_krylov_convergence(KSP ksp,PetscInt iteration,PetscReal norm,
                                        KSPConvergedReason* reason,void* pointer)
{
    auto& guard=*static_cast<KrylovConvergence*>(pointer);
    if(!guard.callbacks||!guard.callbacks->current||!guard.original) return PETSC_ERR_ARG_WRONGSTATE;
    auto& context=*guard.callbacks->current;
    if(!context.action_error.empty()) {
        // Both supported Krylov methods invoke this after their reductions.
        *reason=KSP_DIVERGED_BREAKDOWN;
        return PETSC_SUCCESS;
    }
    KSPConvergedReason proposed=KSP_CONVERGED_ITERATING;
    PetscCall(guard.original(ksp,iteration,norm,&proposed,guard.original_context));
    if(!guard.verify_residual||proposed<=0) {
        *reason=proposed;
        return PETSC_SUCCESS;
    }
    // Flexible GMRES's recurrence can underestimate ||b-Ax|| when scaled or
    // inexact PCs generate nearly dependent directions. Verify only proposed
    // convergence, using the same configured test and the exact current A.
    // Rejecting a false convergence continues the existing Krylov cycle; its
    // ordinary restart rebuilds b-Ax. Never reset the iteration budget, change
    // tolerances, mutate PETSc internals, or re-enter KSPSolve from a callback.
    // Do not publish the proposed reason yet: public KSPBuildSolution returns
    // the old restart solution once ksp's reason is no longer ITERATING.
    const auto start=std::chrono::steady_clock::now();
    if(!guard.residual.get()) {
        Vec solution=nullptr;
        PetscCall(KSPGetSolution(ksp,&solution));
        PetscCall(VecDuplicate(solution,guard.solution_work.put()));
        PetscCall(VecDuplicate(solution,guard.residual.put()));
    }
    Vec residual=nullptr; PetscReal actual=0;
    PetscCall(KSPBuildResidual(ksp,guard.solution_work.get(),guard.residual.get(),&residual));
    PetscCall(VecNorm(residual,NORM_2,&actual));
    ++context.true_residual_checks;
    if(!context.action_error.empty()) *reason=KSP_DIVERGED_BREAKDOWN;
    else PetscCall(guard.original(ksp,iteration,actual,reason,guard.original_context));
    if(*reason<=0) ++context.true_residual_rejections;
    context.true_residual_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    return PETSC_SUCCESS;
}
PetscErrorCode destroy_krylov_convergence(void* pointer)
{
    auto* guard=static_cast<KrylovConvergence*>(pointer);
    const auto error=guard->original_destroy?guard->original_destroy(guard->original_context):PETSC_SUCCESS;
    guard->original_destroy=nullptr;
    delete guard;
    return error;
}
PetscErrorCode function(SNES snes,Vec x,Vec r,void* pointer)
{
    auto* active=static_cast<ActiveContext*>(pointer);
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    try { c.evaluate(x,r,nullptr,true); return PETSC_SUCCESS; }
    catch(const StepRejected& e) { c.error=e.what(); ++c.domain_rejections; return SNESSetFunctionDomainError(snes); }
    catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
PetscErrorCode jacobian(SNES snes,Vec x,Mat j,Mat p,void* pointer)
{
    auto* active=static_cast<ActiveContext*>(pointer);
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    try {
        ++c.jacobian_callbacks;
        if(c.matrix_free) {
            const bool startup=c.consume_initial_jacobian(x,p);
            const bool refresh=startup||c.jacobian_callbacks==1||c.domain_rejections||
                (c.jacobian_callbacks-1)%c.assembled_pc_interval==0;
            if(!startup&&refresh) c.evaluate(x,c.scratch,p,true,false);
            if(startup||refresh) c.operator_state=c.values;
            else {
                local_values(x,c.operator_state);
                ++c.assembled_pc_reuses;
            }
            c.prepare_direction();
            if(refresh&&!startup) c.refresh_user_schur(p);
            EONSIM_PETSC(SNESSetLagPreconditioner(snes,refresh?1:-1));
            // Increase shell state after a new linearization even when P is
            // retained. Its action always consumes the new frozen state.
            EONSIM_PETSC(MatAssemblyBegin(j,MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(j,MAT_FINAL_ASSEMBLY));
            return PETSC_SUCCESS;
        }
        if(c.consume_initial_jacobian(x,j)) {
            c.prepare_preconditioner(snes,j,true);
            return PETSC_SUCCESS;
        }
        // The fused physical callback may compute residual values while forming
        // J, but SNES consumes only J here. Ordinary Vec stashes still drain;
        // COO needs neither a scratch communication plan nor a publication.
        c.evaluate(x,c.scratch,j,true,false);
        // Refresh only after successful assembly, including constraint row replacement.
        c.prepare_preconditioner(snes,j);
        return PETSC_SUCCESS;
    }
    catch(const StepRejected& e) { c.error=e.what(); ++c.domain_rejections; return SNESSetJacobianDomainError(snes); }
    catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
PetscErrorCode convergence(SNES snes,PetscInt iteration,PetscReal xnorm,PetscReal stepnorm,
                          PetscReal fnorm,SNESConvergedReason* reason,void* pointer)
{
    auto* active=static_cast<ActiveContext*>(pointer);
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    try {
        EONSIM_PETSC(SNESConvergedDefault(snes,iteration,xnorm,stepnorm,fnorm,reason,nullptr));
        if(*reason>0) {
            Vec r; EONSIM_PETSC(SNESGetFunction(snes,&r,nullptr,nullptr));
            c.acceptance.measure(r);
            if(!c.acceptance.passes()) *reason=SNES_CONVERGED_ITERATING;
        }
        return PETSC_SUCCESS;
    } catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
std::string petsc_options_snapshot()
{
    char* text=nullptr;
    EONSIM_PETSC(PetscOptionsGetAll(nullptr,&text));
    const std::string result=text?text:"";
    EONSIM_PETSC(PetscFree(text));
    return result;
}
bool requires_exact_multigrid_action(KSP solver) {
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    MonolithicFsiMgStats stats;
    if(query_monolithic_fsi_mg_stats(pc,stats)) return stats.matrix_free_fine;
    if(KSP bulk=deflated_fgmres_bulk_solver(pc)) return requires_exact_multigrid_action(bulk);
    if(KSP bulk=interface_patch_bulk_solver(pc)) return requires_exact_multigrid_action(bulk);
    if(KSP bulk=rcr_port_bulk_solver(pc)) return requires_exact_multigrid_action(bulk);
    return false;
}
// A reduced RCR bulk receives E^T A E through its owned zero-port lift, while
// full-layout wrappers retain the same exact current Newton action.
void bind_exact_multigrid_action(KSP solver,Mat exact) {
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    if(set_monolithic_fsi_mg_fine_operator(pc,exact)) return;
    if(KSP bulk=deflated_fgmres_bulk_solver(pc)) bind_exact_multigrid_action(bulk,exact);
    else if(KSP bulk=interface_patch_bulk_solver(pc)) bind_exact_multigrid_action(bulk,exact);
    else if(KSP bulk=rcr_port_bulk_solver(pc)) {
        if(requires_exact_multigrid_action(bulk)) (void)rcr_port_bulk_exact_operator(pc,exact);
    }
}
bool same_solver_config(const SolverConfig& a,const SolverConfig& b)
{
    if(a.pc_recipe!=b.pc_recipe||a.relative_tolerance!=b.relative_tolerance||
       a.absolute_tolerance!=b.absolute_tolerance||a.maximum_iterations!=b.maximum_iterations||
       a.fields.size()!=b.fields.size()) return false;
    auto left=a.fields.begin(),right=b.fields.begin();
    for(;left!=a.fields.end();++left,++right) {
        const auto& x=left->second; const auto& y=right->second;
        if(left->first!=right->first||x.residual_scale!=y.residual_scale||
           x.absolute_tolerance!=y.absolute_tolerance||x.relative_tolerance!=y.relative_tolerance||
           x.constraint_scale!=y.constraint_scale||x.constraint_tolerance!=y.constraint_tolerance) return false;
    }
    return true;
}
}
struct NonlinearSystem::Workspace {
    SolverConfig config;
    std::vector<PetscInt> constraint_rows;
    std::string options;
    FieldAcceptance acceptance;
    LinearDiagnostics diagnostics;
    AdaptivePcState adaptive_pc;
    LinearPolicy linear_policy;
    PcBlock plan;
    PcSchurUpdates pc_updates; // Must outlive the SNES/KSP/PC holding its USER matrices.
    ActiveContext callbacks;
    PetscBool block=PETSC_FALSE,schur=PETSC_FALSE,report=PETSC_FALSE,rank_report=PETSC_FALSE;
    bool semantic=false,pc_configured=false,reusable=false;
    bool matrix_free=false;
    bool verify_true_residual=false;
    PetscInt assembled_pc_interval=1;
    PetscOwner<Vec,VecDestroy> direction_ghost;
    PetscOwner<Mat,MatDestroy> action_matrix;
    PetscReal initial_lambda=1;
    PetscOwner<SNES,SNESDestroy> snes; // Destroy first, before callback/PC refresh storage.

    Workspace(MPI_Comm comm,const AlgebraLayout& layout,const SolverConfig& settings,
              const std::vector<PetscInt>& constraints)
        :config(settings),constraint_rows(constraints),acceptance(comm,layout,config,constraints) {}
    void initialize(MPI_Comm comm,const AlgebraLayout& l,Vec r,Mat j,bool use_matrix_free) {
        matrix_free=use_matrix_free;
        EONSIM_PETSC(SNESCreate(comm,snes.put()));
        EONSIM_PETSC(SNESSetFunction(snes.get(),r,function,&callbacks));
        if(matrix_free) {
            EONSIM_PETSC(VecDuplicate(r,direction_ghost.put()));
            EONSIM_PETSC(MatCreateShell(comm,l.owned,l.owned,l.global,l.global,&callbacks,action_matrix.put()));
            EONSIM_PETSC(MatShellSetOperation(action_matrix.get(),MATOP_MULT,
                reinterpret_cast<void(*)(void)>(matrix_free_multiply)));
            EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-nonlinear_matrix_free_pc_interval",&assembled_pc_interval,nullptr));
            PetscInt low=0,high=0;
            MPI_Allreduce(&assembled_pc_interval,&low,1,MPIU_INT,MPI_MIN,comm);
            MPI_Allreduce(&assembled_pc_interval,&high,1,MPIU_INT,MPI_MAX,comm);
            if(low!=high||low<1||high>1000) throw std::runtime_error("Matrix-free P interval must be identical and between 1 and 1000");
        }
        EONSIM_PETSC(SNESSetJacobian(snes.get(),matrix_free?action_matrix.get():j,j,jacobian,&callbacks));
        EONSIM_PETSC(SNESSetTolerances(snes.get(),config.absolute_tolerance,config.relative_tolerance,0,config.maximum_iterations,10000));
        EONSIM_PETSC(SNESSetConvergenceTest(snes.get(),convergence,&callbacks,nullptr));
        KSP ksp; PC pc;
        EONSIM_PETSC(SNESGetKSP(snes.get(),&ksp)); EONSIM_PETSC(KSPGetPC(ksp,&pc));
        EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCLU));
        EONSIM_PETSC(PCFactorSetMatSolverType(pc,MATSOLVERSUPERLU_DIST));
        if(matrix_free) {
            EONSIM_PETSC(KSPSetType(ksp,KSPFGMRES));
            EONSIM_PETSC(KSPSetTolerances(ksp,1e-9,1e-13,PETSC_DEFAULT,500));
        }
        block=PETSC_FALSE; schur=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-schur_pc",&schur,nullptr));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-block_pc",&block,nullptr));
        char recipe_option[32]{}; PetscBool recipe_set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_recipe",recipe_option,sizeof(recipe_option),&recipe_set));
        const std::string recipe=recipe_set?recipe_option:config.pc_recipe;
        semantic=!recipe.empty();
        int enabled=semantic,enabled_min=0,enabled_max=0;
        MPI_Allreduce(&enabled,&enabled_min,1,MPI_INT,MPI_MIN,comm);
        MPI_Allreduce(&enabled,&enabled_max,1,MPI_INT,MPI_MAX,comm);
        if(enabled_min!=enabled_max) throw std::runtime_error("PC recipe enablement differs between ranks");
        int conflict=(block&&schur)||(semantic&&(block||schur)),any_conflict=0;
        MPI_Allreduce(&conflict,&any_conflict,1,MPI_INT,MPI_MAX,comm);
        if(any_conflict) throw std::runtime_error("Choose only one PC recipe, block_pc or schur_pc");
        PetscBool nodal_option=PETSC_FALSE,velocity_option=PETSC_FALSE,structure_option=PETSC_FALSE,
            coarse_option=PETSC_FALSE,aggregate_option=PETSC_FALSE,port_option=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_schur_approx",&nodal_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_velocity_solver",&velocity_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_structure_approx",&structure_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_velocity_coarse_space",&coarse_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_velocity_aggregate_nodes",&aggregate_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_rcr_ports",&port_option));
        bool interface_option=false;
        for(const char* option:{"-pc_plan_interface_smoother","-pc_plan_patch_precision","-pc_plan_patch_overlap",
            "-pc_plan_patch_max_size","-pc_plan_patch_refinement_steps","-pc_plan_patch_refinement_tolerance","-pc_plan_patch_damping",
            "-pc_plan_pcd_robin","-pc_plan_pcd_velocity_mass","-pc_plan_pcd_velocity_mass_weight"}) {
            PetscBool found=PETSC_FALSE; EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,option,&found));
            interface_option=interface_option||found;
        }
        int unused=!semantic&&(nodal_option||velocity_option||structure_option||coarse_option||aggregate_option||port_option||interface_option),any_unused=0;
        MPI_Allreduce(&unused,&any_unused,1,MPI_INT,MPI_MAX,comm);
        if(any_unused) throw std::runtime_error("pc_plan Schur, velocity and structure options require -pc_recipe");
        if(semantic) plan=make_pc_plan(comm,l,recipe);
        if(block||schur||semantic) {
            EONSIM_PETSC(KSPSetType(ksp,KSPFGMRES));
            EONSIM_PETSC(KSPSetTolerances(ksp,1e-9,1e-13,PETSC_DEFAULT,500));
            EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
            EONSIM_PETSC(PCFieldSplitSetType(pc,PC_COMPOSITE_MULTIPLICATIVE));
        }
        EONSIM_PETSC(SNESSetFromOptions(snes.get()));
        if(semantic) validate_pc_plan_options(comm,ksp,plan);
        if(schur) validate_schur_solver_options(comm,ksp,l);
        // PETSc 优化构建默认可能不检查 Jacobian domain error；结果有效性检查在两种构建都启用。
        EONSIM_PETSC(SNESSetCheckJacobianDomainError(snes.get(),PETSC_TRUE));
        PCType type; EONSIM_PETSC(PCGetType(pc,&type));
        if(!schur&&!semantic&&std::strcmp(type,PCFIELDSPLIT)==0) {
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
        report=PETSC_FALSE; PetscBool linear_report=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-solver_report",&report,nullptr));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-solver_rank_report",&rank_report,nullptr));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-linear_report",&linear_report,nullptr));
        if(rank_report) report=PETSC_TRUE;
        if(linear_report) {
            report=PETSC_TRUE;
            diagnostics.fields.emplace(comm,l,config,constraint_rows);
            EONSIM_PETSC(VecDuplicate(r,diagnostics.residual.put()));
        }
        diagnostics.enabled=report;
        EONSIM_PETSC(KSPSetPostSolve(ksp,linear_complete,&diagnostics));
        if(report) {
            EONSIM_PETSC(KSPSetPreSolve(ksp,linear_begin,&diagnostics));
        }
        EONSIM_PETSC(SNESSetCountersReset(snes.get(),PETSC_TRUE));
        SNESType nonlinear_type=nullptr;
        PetscInt jacobian_lag=1,preconditioner_lag=1;
        PetscBool reuse_preconditioner=PETSC_FALSE,permutation=PETSC_FALSE,eisenstat_walker=PETSC_FALSE;
        EONSIM_PETSC(SNESGetType(snes.get(),&nonlinear_type));
        EONSIM_PETSC(SNESGetLagJacobian(snes.get(),&jacobian_lag));
        EONSIM_PETSC(SNESGetLagPreconditioner(snes.get(),&preconditioner_lag));
        EONSIM_PETSC(KSPGetReusePreconditioner(ksp,&reuse_preconditioner));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-verify_operator_permutation",&permutation,nullptr));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-snes_ksp_ew",&eisenstat_walker,nullptr));
        options=petsc_options_snapshot();
        if(matrix_free) {
            PetscBool incompatible=PETSC_FALSE;
            for(const char* option:{"-snes_mf","-snes_mf_operator","-snes_fd","-snes_fd_color"}) {
                PetscBool found=PETSC_FALSE;
                EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,option,&found));
                incompatible=static_cast<PetscBool>(incompatible||found);
            }
            int bad=incompatible||jacobian_lag!=1||preconditioner_lag!=1||reuse_preconditioner||eisenstat_walker,any=0;
            MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
            if(any) throw std::runtime_error("Exact matrix-free action requires fresh Newton linearizations and its own P interval, without SNES FD/MF, manual lag, PC reuse or EW overrides");
            KSPType method=nullptr; EONSIM_PETSC(KSPGetType(ksp,&method));
            bad=!method||(std::strcmp(method,KSPFGMRES)!=0&&std::strcmp(method,KSPPIPEFGMRES)!=0);
            MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
            if(any) throw std::runtime_error("Exact matrix-free operator requires fgmres or pipefgmres");
        }
        PetscInt deflation_capacity=0;
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-nonlinear_krylov_deflation",&deflation_capacity,nullptr));
        PetscBool true_residual=recipe=="monolithic_mg"||deflation_capacity>0?PETSC_TRUE:PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_true_residual",&true_residual,nullptr));
        PetscBool converge_at_limit=PETSC_FALSE,convergence_test_set=PETSC_FALSE;
        char convergence_test[32]{};
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-ksp_converged_maxits",&converge_at_limit,nullptr));
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-ksp_convergence_test",convergence_test,
            sizeof(convergence_test),&convergence_test_set));
        KSPType method=nullptr; KSPNormType norm_type;
        EONSIM_PETSC(KSPGetType(ksp,&method)); EONSIM_PETSC(KSPGetNormType(ksp,&norm_type));
        const int residual_policy[]={int(true_residual),int(!true_residual),
            (deflation_capacity>0&&!true_residual)||(true_residual&&(!method||(std::strcmp(method,KSPFGMRES)!=0&&std::strcmp(method,KSPPIPEFGMRES)!=0)||
                            norm_type!=KSP_NORM_UNPRECONDITIONED||converge_at_limit||
                            (convergence_test_set&&std::strcmp(convergence_test,"default")!=0)))};
        int global_residual_policy[3]{};
        MPI_Allreduce(residual_policy,global_residual_policy,3,MPI_INT,MPI_MAX,comm);
        if((global_residual_policy[0]&&global_residual_policy[1])||global_residual_policy[2])
            throw std::runtime_error("True residual verification requires the same option on all ranks, unpreconditioned flexible GMRES, and a residual-based convergence test without converged_maxits");
        verify_true_residual=true_residual;
        // Retain fresh-solver semantics for history-carrying nonlinear algorithms
        // or explicit lagged PCs (including prefixed child PCs). The ordinary
        // Newton path reuses symbolic objects, never stale numerical factors.
        reusable=nonlinear_type&&std::strcmp(nonlinear_type,SNESNEWTONLS)==0&&
            jacobian_lag==1&&preconditioner_lag==1&&!reuse_preconditioner&&!eisenstat_walker&&!permutation&&
            options.find("_reuse_preconditioner")==std::string::npos;
        adaptive_pc.initialize(comm,j,reusable&&!matrix_free,ksp);
        diagnostics.adaptive_pc=&adaptive_pc;
        linear_policy.initialize(comm,ksp,r,reusable);
        diagnostics.policy=&linear_policy;
        if(linear_policy.active()) EONSIM_PETSC(KSPSetPreSolve(ksp,linear_begin,&diagnostics));
        if(reusable) {
            SNESLineSearch line_search;
            EONSIM_PETSC(SNESGetLineSearch(snes.get(),&line_search));
            EONSIM_PETSC(SNESLineSearchGetLambda(line_search,&initial_lambda));
        }
    }
};
NonlinearSystem::~NonlinearSystem()=default;
NonlinearSystem::NonlinearSystem(MPI_Comm comm,const AlgebraLayout& l,PetscOwner<Mat,MatDestroy> pattern)
    :communicator_(comm),layout_(l),matrix_(std::move(pattern)),local_trial_(l.local_to_global.size())
{
    if(matrix_.get()) {
        int comparison;
        MPI_Comm_compare(comm,PetscObjectComm(reinterpret_cast<PetscObject>(matrix_.get())),&comparison);
        PetscInt rows,columns,begin,end,column_begin,column_end;
        PetscBool assembled;
        EONSIM_PETSC(MatGetSize(matrix_.get(),&rows,&columns));
        EONSIM_PETSC(MatGetOwnershipRange(matrix_.get(),&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRangeColumn(matrix_.get(),&column_begin,&column_end));
        EONSIM_PETSC(MatAssembled(matrix_.get(),&assembled));
        int invalid=(comparison!=MPI_IDENT&&comparison!=MPI_CONGRUENT)||!assembled||
            rows!=l.global||columns!=l.global||begin!=l.begin||end!=l.begin+l.owned||
            column_begin!=l.begin||column_end!=l.begin+l.owned,any_invalid=0;
        MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,comm);
        if(any_invalid) throw std::runtime_error("Preassembled Jacobian pattern does not match algebra layout");
        // Preallocation has established locations, not only spare row capacity.
        EONSIM_PETSC(MatSetOption(matrix_.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
    } else {
        EONSIM_PETSC(MatCreateAIJ(comm,l.owned,l.owned,l.global,l.global,
            0,l.diagonal.empty()?nullptr:l.diagonal.data(),
            0,l.off_diagonal.empty()?nullptr:l.off_diagonal.data(),matrix_.put()));
        EONSIM_PETSC(MatSetOption(matrix_.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    }
    const auto ghosts=l.local_to_global.size()-l.owned;
    EONSIM_PETSC(VecCreateGhost(comm,l.owned,l.global,ghosts,l.local_to_global.data()+l.owned,solution_.put()));
    EONSIM_PETSC(VecDuplicate(solution_.get(),residual_.put()));
    EONSIM_PETSC(VecDuplicate(solution_.get(),scratch_.put()));
    EONSIM_PETSC(VecSetOption(residual_.get(),VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
    EONSIM_PETSC(VecSetOption(scratch_.get(),VEC_IGNORE_NEGATIVE_INDICES,PETSC_TRUE));
    EONSIM_PETSC(MatSetOption(matrix_.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
}
void NonlinearSystem::set_jacobian_coo(const std::vector<PetscInt>& rows,const std::vector<PetscInt>& columns)
{
    int invalid=coo_enabled_||solve_started_||rows.size()!=columns.size(),any_invalid=0;
    const auto limit=static_cast<std::uintmax_t>(std::numeric_limits<PetscCount>::max());
    if(rows.size()>limit-static_cast<std::uintmax_t>(layout_.owned) ||
       rows.size()>coo_values_.max_size()-static_cast<std::size_t>(layout_.owned)) invalid=1;
    for(auto row:rows) if(row<0||row>=layout_.global) invalid=1;
    for(auto column:columns) if(column<0||column>=layout_.global) invalid=1;
    MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,communicator_);
    if(any_invalid) throw std::runtime_error("Invalid COO Jacobian pattern or configuration after first solve");
    // PETSc may reorder the index arrays. Never expose those mutated arrays to the callback.
    auto i=rows,j=columns;
    for(PetscInt row=layout_.begin;row<layout_.begin+layout_.owned;++row) {
        i.push_back(row); j.push_back(row);
    }
    coo_values_.assign(i.size(),0.);
    EONSIM_PETSC(MatSetPreallocationCOO(matrix_.get(),static_cast<PetscCount>(i.size()),i.data(),j.data()));
    EONSIM_PETSC(MatSetOption(matrix_.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
    EONSIM_PETSC(MatSetOption(matrix_.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    coo_enabled_=true;
}
void NonlinearSystem::set_residual_coo(const std::vector<PetscInt>& rows)
{
    const auto limit=static_cast<std::uintmax_t>(std::numeric_limits<PetscCount>::max());
    int invalid=residual_coo_enabled_||solve_started_||rows.size()>limit||
        rows.size()>residual_coo_values_.max_size(),any_invalid=0;
    for(auto row:rows) if(row>=layout_.global) invalid=1;
    MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,communicator_);
    if(any_invalid) throw std::runtime_error("Invalid COO residual pattern or configuration after first solve");
    residual_coo_rows_=rows;
    residual_coo_values_.assign(rows.size(),0.);
    // Only the persistent function target is published. Jacobian-only scratch
    // values are unused; SNES-owned line-search targets are prepared on first
    // use because VecDuplicate does not promise to copy COO state.
    prepare_residual_coo(residual_.get(),residual_coo_rows_,residual_coo_vectors_);
    residual_coo_enabled_=true;
}
NonlinearResult NonlinearSystem::solve(const SolverConfig& config,
    const std::vector<double>& initial,const std::vector<PetscInt>& constraints,
    const std::vector<double>& prescribed,const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble,
    const NonlinearAssemblyPhases& phases)
{
    const auto setup_begin=std::chrono::steady_clock::now();
    if(solving_) throw std::runtime_error("NonlinearSystem::solve is not reentrant");
    solving_=true; solve_started_=true;
    struct SolveScope {
        bool& running;
        std::unique_ptr<Workspace>& workspace;
        bool keep_workspace=false;
        ~SolveScope() {
            if(workspace) workspace->callbacks.current=nullptr;
            // A failure may leave PETSc algorithm/PC state or callback locks.
            // Keep the graph and owned work vectors, rebuild the solver next time.
            if(!keep_workspace) workspace.reset();
            running=false;
        }
    } scope{solving_,workspace_};
    const auto comm=communicator_;
    const auto& l=layout_;
    auto& x=solution_; auto& r=residual_; auto& scratch=scratch_; auto& j=matrix_;
    PetscBool reuse=PETSC_TRUE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_reuse",&reuse,nullptr));
    char pressure_approximation[32]{};
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_schur_approx",pressure_approximation,
        sizeof(pressure_approximation),nullptr));
    const bool physical_pcd=std::strcmp(pressure_approximation,"pcd")==0;
    PetscBool matrix_free_interval_set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-nonlinear_matrix_free_pc_interval",&matrix_free_interval_set));
    const auto options=petsc_options_snapshot();
    int local[]={initial.size()!=l.local_to_global.size()||constraints.size()!=prescribed.size()||
        bool(phases.owned)!=bool(phases.halo)||
        bool(phases.jacobian_action_owned)!=bool(phases.jacobian_action_halo)||
        ((phases.jacobian_action_owned||phases.prepare_jacobian_action)&&!phases.jacobian_action),
        !reuse||!workspace_||!workspace_->reusable||workspace_->options!=options||
        !same_solver_config(workspace_->config,config)||workspace_->constraint_rows!=constraints||
        workspace_->matrix_free!=bool(phases.jacobian_action),
        bool(phases.owned),!phases.owned,bool(phases.after_jacobian),!phases.after_jacobian,
        physical_pcd&&!phases.after_jacobian,bool(phases.jacobian_action),!phases.jacobian_action,
        matrix_free_interval_set&&!phases.jacobian_action,
        bool(phases.jacobian_action_owned),!phases.jacobian_action_owned,
        bool(phases.prepare_jacobian_action),!phases.prepare_jacobian_action};
    int global[14]{};
    MPI_Allreduce(local,global,14,MPI_INT,MPI_MAX,comm);
    if(global[0]) throw std::runtime_error("Invalid nonlinear state/constraint layout");
    if(global[2]&&global[3]) throw std::runtime_error("Nonlinear assembly phases must agree on every rank");
    if(global[4]&&global[5]) throw std::runtime_error("Auxiliary Jacobian callback must agree on every rank");
    // Root Mat compositions retain their handles across solves. Without a
    // current producer, a retained PCD recipe could silently reuse old physical
    // coefficients, including when the new initial residual is already zero.
    // Standalone algebra callers may still compose static auxiliary operators
    // explicitly; this requirement belongs to the nonlinear update contract.
    if(global[6]) throw std::runtime_error("Physical PCD requires an after_jacobian auxiliary update callback for every nonlinear solve");
    if(global[7]&&global[8]) throw std::runtime_error("Matrix-free action must be supplied on every rank or none");
    if(global[9]) throw std::runtime_error("-nonlinear_matrix_free_pc_interval requires a matrix-free Jacobian action");
    if(global[10]&&global[11]) throw std::runtime_error("Matrix-free action phases must agree on every rank");
    if(global[12]&&global[13]) throw std::runtime_error("Matrix-free preparation must agree on every rank");
    const bool solver_reused=!global[1];
    if(!solver_reused) {
        workspace_.reset();
        workspace_=std::make_unique<Workspace>(comm,l,config,constraints);
        ++solver_generation_;
        workspace_->initialize(comm,l,r.get(),j.get(),bool(phases.jacobian_action));
        if(residual_coo_enabled_) {
            // A failed MatShell action retires the KSP's locked residual too.
            // VecDuplicate preserves its ghost layout, but not the COO plan.
            // Retain preparation only for this persistent target after the old
            // SNES work vectors have been destroyed.
            prepare_residual_coo(r.get(),residual_coo_rows_,residual_coo_vectors_);
            PetscObjectId residual_id=0;
            EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(r.get()),&residual_id));
            residual_coo_vectors_={residual_id};
        }
    }
    auto& workspace=*workspace_;
    auto& snes=workspace.snes;
    auto& acceptance=workspace.acceptance;
    acceptance.reduction_calls=0;
    auto& diagnostics=workspace.diagnostics;
    diagnostics.reset();
    workspace.adaptive_pc.begin_solve(phases.preconditioner_context);
    const auto schur=workspace.schur,report=workspace.report;
    const bool semantic=workspace.semantic;
    KSP ksp; PC pc;
    EONSIM_PETSC(SNESGetKSP(snes.get(),&ksp)); EONSIM_PETSC(KSPGetPC(ksp,&pc));
    workspace.linear_policy.begin_solve(ksp);
    if(solver_reused) {
        SNESLineSearch line_search;
        EONSIM_PETSC(SNESGetLineSearch(snes.get(),&line_search));
        EONSIM_PETSC(SNESLineSearchSetLambda(line_search,workspace.initial_lambda));
    }
    PetscScalar* a;
    EONSIM_PETSC(VecGetArray(x.get(),&a));
    for(PetscInt i=0;i<l.owned;++i) a[i]=initial[i];
    for(std::size_t i=0;i<constraints.size();++i) a[constraints[i]-l.begin]=prescribed[i];
    EONSIM_PETSC(VecRestoreArray(x.get(),&a));
    Context context{comm,l,constraints,prescribed,assemble,acceptance,scratch.get(),local_trial_,
        coo_enabled_?&coo_values_:nullptr,residual_coo_enabled_?&residual_coo_rows_:nullptr,
        residual_coo_enabled_?&residual_coo_values_:nullptr,residual_coo_vectors_,{}};
    context.phases=&phases;
    context.adaptive_pc=&workspace.adaptive_pc;
    context.matrix_free=workspace.matrix_free;
    context.direction_ghost=workspace.direction_ghost.get();
    context.assembled_pc_interval=workspace.assembled_pc_interval;
    if(workspace.matrix_free) EONSIM_PETSC(SNESSetLagPreconditioner(snes.get(),1));
    struct CallbackScope {
        ActiveContext& callbacks;
        CallbackScope(ActiveContext& target,Context& value):callbacks(target) { callbacks.current=&value; }
        ~CallbackScope() { callbacks.current=nullptr; }
    } callback_scope{workspace.callbacks,context};
    if(workspace.pc_configured&&semantic) context.pc_updates=&workspace.pc_updates;
    const auto solve_begin=std::chrono::steady_clock::now();
    const double setup_seconds=std::chrono::duration<double>(solve_begin-setup_begin).count();
    PetscBool verify_permutation=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-verify_operator_permutation",&verify_permutation,nullptr));
    bool reuse_initial_jacobian=false;
    if(schur||semantic) {
        PetscBool requested=PETSC_TRUE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-nonlinear_initial_jacobian_reuse",&requested,nullptr));
        const int local=requested&&workspace.reusable&&!verify_permutation;
        int all=0;
        if(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Initial Jacobian policy communication failed");
        reuse_initial_jacobian=all!=0;
    }
    const bool initial_jacobian_deferred=(schur||semantic)&&workspace.pc_configured&&reuse_initial_jacobian;
    const bool initial_jacobian_assembled=verify_permutation||((schur||semantic)&&!initial_jacobian_deferred);
    // A retained PC already knows its symbolic blocks. Its numerical update
    // belongs to the first Newton Jacobian callback, after this fresh residual.
    context.evaluate(x.get(),r.get(),initial_jacobian_assembled?j.get():nullptr,true);
    if(verify_permutation) verify_operator_permutation(comm,j.get(),r.get());
    acceptance.measure(r.get(),true);
    EONSIM_PETSC(SNESSetInitialFunction(snes.get(),r.get()));
    const auto schur_begin=std::chrono::steady_clock::now();
    PetscReal initial_norm=0;
    if(schur||semantic) EONSIM_PETSC(VecNorm(r.get(),NORM_2,&initial_norm));
    // An exactly converged initial state must not factor an unused/singular PC.
    if((schur||semantic)&&initial_norm>0) {
        if(!workspace.pc_configured) {
            // Default options may be inserted while preparing child solvers.
            // A callback's unrelated options change must still invalidate reuse.
            const bool options_unchanged=petsc_options_snapshot()==workspace.options;
            if(schur) configure_schur_solver(comm,ksp,l,j.get());
            else {
                configure_pc_plan(comm,ksp,j.get(),workspace.plan,&workspace.pc_updates);
                context.user_schur_updates+=static_cast<PetscInt>(workspace.pc_updates.refreshers.size());
            }
            workspace.options=petsc_options_snapshot();
            workspace.reusable=workspace.reusable&&options_unchanged&&
                workspace.options.find("_reuse_preconditioner")==std::string::npos;
            workspace.pc_configured=true;
        } else if(semantic&&initial_jacobian_assembled&&!workspace.adaptive_pc.enabled) context.refresh_user_schur(j.get());
        if(semantic) context.pc_updates=&workspace.pc_updates;
    }
    // Only startup PC configuration needs a tangent before SNESSolve. The
    // first callback may use it once if no intervening evaluation or owner
    // value change occurred; later Newton steps always assemble their own J.
    if(reuse_initial_jacobian&&initial_jacobian_assembled&&initial_norm>0) {
        // Configuring a child PC may insert options or reveal an incompatible
        // reuse policy. Recheck collectively before arming a collective token.
        const int local=workspace.reusable;
        int all=0;
        if(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Initial Jacobian configuration communication failed");
        if(all) context.remember_initial_jacobian(x.get(),j.get());
    }
    const double schur_setup_seconds=(schur||semantic)?std::chrono::duration<double>(std::chrono::steady_clock::now()-schur_begin).count():0.;
    if(workspace.matrix_free) {
        // Recipe setup inspects assembled P. Restore the distinct exact action
        // only after all child submatrices have been configured.
        EONSIM_PETSC(KSPSetOperators(ksp,workspace.action_matrix.get(),j.get()));
        EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
        bind_exact_multigrid_action(ksp,workspace.action_matrix.get());
    }
    if(workspace.linear_policy.deflation_capacity) {
        configure_deflated_fgmres(ksp,workspace.linear_policy.deflation_capacity);
        EONSIM_PETSC(KSPGetPC(ksp,&pc));
    }
    if(workspace.matrix_free||workspace.verify_true_residual) {
        // Recipe setup can call KSPSetFromOptions, so wrap only its final
        // configured convergence test and retain the wrapper on session reuse.
        decltype(KrylovConvergence::original) current=nullptr;
        EONSIM_PETSC(KSPGetConvergenceTest(ksp,&current,nullptr,nullptr));
        if(current!=guarded_krylov_convergence) {
            // Transfer without destroying the original context; KSP owns the
            // wrapper and calls its original destructor exactly once.
            auto guarded=std::make_unique<KrylovConvergence>();
            guarded->callbacks=&workspace.callbacks;
            guarded->verify_residual=workspace.verify_true_residual;
            EONSIM_PETSC(KSPGetAndClearConvergenceTest(ksp,&guarded->original,
                &guarded->original_context,&guarded->original_destroy));
            EONSIM_PETSC(KSPSetConvergenceTest(ksp,guarded_krylov_convergence,guarded.get(),
                destroy_krylov_convergence));
            guarded.release();
        }
    }
    auto error=SNESSolve(snes.get(),nullptr,x.get());
    PetscInt pc_rebuild_retries=0,prior_nonlinear_iterations=0,prior_linear_iterations=0;
    if(workspace.adaptive_pc.enabled) {
        SNESConvergedReason first_reason; KSPConvergedReason first_linear_reason; PCFailedReason first_pc_failure;
        EONSIM_PETSC(SNESGetConvergedReason(snes.get(),&first_reason));
        EONSIM_PETSC(KSPGetConvergedReason(ksp,&first_linear_reason));
        EONSIM_PETSC(PCGetFailedReason(pc,&first_pc_failure));
        const int local_retry=!error&&context.error.empty()&&workspace.adaptive_pc.failed_reuse&&
            first_reason==SNES_DIVERGED_LINEAR_SOLVE&&first_linear_reason==KSP_DIVERGED_ITS&&
            first_pc_failure==PC_NOERROR&&!diagnostics.collective_pc_failure;
        int retry=0; MPI_Allreduce(&local_retry,&retry,1,MPI_INT,MPI_MIN,comm);
        if(retry) {
            // The unsuccessful linear correction was never committed to the
            // Newton iterate. Keep the original physical acceptance baseline,
            // evaluate that last accepted iterate afresh, and retry once with
            // a rebuilt PC. No tolerance, iteration budget or state is relaxed.
            EONSIM_PETSC(SNESGetIterationNumber(snes.get(),&prior_nonlinear_iterations));
            EONSIM_PETSC(SNESGetLinearSolveIterations(snes.get(),&prior_linear_iterations));
            PetscInt prior_function_evaluations=0;
            EONSIM_PETSC(SNESGetNumberFunctionEvals(snes.get(),&prior_function_evaluations));
            struct RetryBudget {
                SNES solver;
                PetscReal absolute=0,relative=0,step=0;
                PetscInt iterations=0,functions=0;
                bool active=false;
                ~RetryBudget() {
                    // Restore even if a callback throws; a successful session
                    // is retained for the next time step with its original limits.
                    if(active) (void)SNESSetTolerances(solver,absolute,relative,step,iterations,functions);
                }
            } budget{snes.get()};
            // Query the effective values, including -snes_max_it/max_funcs.
            // SNESSolve resets both counters, so only the unspent allowances
            // belong to this retry. The function count is PETSc's, excluding
            // the explicit initial/final physical checks as before. A negative
            // function limit means unlimited.
            EONSIM_PETSC(SNESGetTolerances(snes.get(),&budget.absolute,&budget.relative,
                &budget.step,&budget.iterations,&budget.functions));
            const PetscInt remaining_iterations=std::max(PetscInt{0},budget.iterations-prior_nonlinear_iterations);
            const PetscInt remaining_functions=budget.functions<0?budget.functions:
                std::max(PetscInt{0},budget.functions-prior_function_evaluations);
            budget.active=true;
            EONSIM_PETSC(SNESSetTolerances(snes.get(),budget.absolute,budget.relative,budget.step,
                remaining_iterations,remaining_functions));
            workspace.adaptive_pc.force=true; workspace.adaptive_pc.ready=false;
            workspace.adaptive_pc.failed_reuse=false;
            EONSIM_PETSC(SNESSetLagPreconditioner(snes.get(),1));
            EONSIM_PETSC(KSPSetReusePreconditioner(ksp,PETSC_FALSE));
            context.evaluate(x.get(),r.get(),nullptr,true);
            EONSIM_PETSC(SNESSetInitialFunction(snes.get(),r.get()));
            EONSIM_PETSC(PetscPrintf(comm,"pc_rebuild_retry previous_ksp_reason=%d retained_acceptance=1"
                " newton_used=%" PetscInt_FMT " newton_remaining=%" PetscInt_FMT
                " snes_functions_used=%" PetscInt_FMT " snes_functions_remaining=%" PetscInt_FMT "\n",
                static_cast<int>(first_linear_reason),prior_nonlinear_iterations,remaining_iterations,
                prior_function_evaluations,remaining_functions));
            ++pc_rebuild_retries;
            error=SNESSolve(snes.get(),nullptr,x.get());
            EONSIM_PETSC(SNESSetTolerances(snes.get(),budget.absolute,budget.relative,budget.step,
                budget.iterations,budget.functions));
            budget.active=false;
        }
    }
    const auto finalize_begin=std::chrono::steady_clock::now();
    const double solve_seconds=std::chrono::duration<double>(finalize_begin-solve_begin).count();
    const double assembly_seconds=context.assembly_seconds,ghost_seconds=context.ghost_seconds;
    // Freeze before final physical acceptance/reaction assembly, matching existing assembly timers.
    const double callback_seconds=context.callback_seconds,failure_sync_seconds=context.failure_sync_seconds;
    const double assembly_finalize_seconds=context.assembly_finalize_seconds,constraint_seconds=context.constraint_seconds;
    if(!context.action_error.empty()) { context.error=context.action_error; context.recoverable=false; }
    if(!diagnostics.policy_error.empty()&&context.error.empty()) {
        context.error=diagnostics.policy_error; context.recoverable=false;
    }
    if((error||!context.action_error.empty())&&!context.error.empty()) {
        // SNESComputeJacobian/Function can return from a failing callback before
        // VecLockReadPop (PETSc 3.23.7). A MatShell error additionally returns
        // from KSPSolve_Private before it pops the read lock on its RHS, which
        // is our persistent residual. Retire both affected Vecs rather than
        // editing PETSc's lock stack. Normally the deferred action error above
        // exits through KSP convergence and leaves no locks, but an independent
        // PETSc error may still return early. SNES/KSP retain old references until
        // normal workspace destruction; the next solve overwrites owned data,
        // updates ghosts and prepares the replacement residual's COO plan.
        PetscOwner<Vec,VecDestroy> fresh_trial,fresh_residual;
        EONSIM_PETSC(VecDuplicate(x.get(),fresh_trial.put()));
        const bool retire_rhs=context.matrix_free||!diagnostics.policy_error.empty();
        if(retire_rhs) EONSIM_PETSC(VecDuplicate(r.get(),fresh_residual.put()));
        std::swap(*x.put(),*fresh_trial.put());
        if(retire_rhs) std::swap(*r.put(),*fresh_residual.put());
        if(context.recoverable) throw StepRejected(context.error);
        throw std::runtime_error(context.error);
    }
    SNESConvergedReason reason; EONSIM_PETSC(SNESGetConvergedReason(snes.get(),&reason));
    KSPConvergedReason linear_reason; EONSIM_PETSC(KSPGetConvergedReason(ksp,&linear_reason));
    if(diagnostics.collective_pc_failure||
       ((error||reason<=0)&&(linear_reason<0||reason==SNES_DIVERGED_LINEAR_SOLVE))) {
        PCFailedReason local_failure; EONSIM_PETSC(PCGetFailedReason(pc,&local_failure));
        int rank; MPI_Comm_rank(comm,&rank);
        const auto tree=local_solver_report(ksp,rank);
        // Failure diagnostics are rank-local: never add a collective or force PC setup.
        std::cerr<<tree<<std::flush;
        throw std::runtime_error("Linear solver failure: phase=linear_solve rank="+std::to_string(rank)+
            " petsc_error="+std::to_string(error)+" snes_reason="+std::to_string(reason)+
            " ksp_reason="+std::to_string(linear_reason)+" pc_reason="+std::to_string(local_failure)+
            " collective_pc_failure="+std::to_string(diagnostics.collective_pc_failure)+"\n"+tree);
    }
    EONSIM_PETSC(error);
    if(reason==SNES_DIVERGED_INNER||reason==SNES_CONVERGED_ITERATING)
        throw std::runtime_error("SNES solver failure: reason="+std::to_string(reason));
    if(reason<0) throw StepRejected("SNES did not converge: reason="+std::to_string(reason)+(context.error.empty()?"":": "+context.error));
    NonlinearResult result;
    result.domain_rejections=context.domain_rejections;
    result.solver_reused=solver_reused; result.solver_generation=solver_generation_;
    result.jacobian_assemblies=context.jacobian_assemblies;
    result.jacobian_callbacks=context.jacobian_callbacks;
    result.initial_jacobian_assemblies=initial_jacobian_assembled?1:0;
    result.initial_jacobian_reuses=context.initial_jacobian_reuses;
    result.user_schur_updates=context.user_schur_updates;
    result.pc_refreshes=workspace.adaptive_pc.rebuilds;
    result.pc_reuses=workspace.adaptive_pc.reuses;
    result.pc_rebuild_retries=pc_rebuild_retries;
    result.pc_drift_refreshes=workspace.adaptive_pc.drift_rebuilds;
    result.pc_age_refreshes=workspace.adaptive_pc.age_rebuilds;
    result.pc_iteration_refreshes=workspace.adaptive_pc.iteration_rebuilds;
    result.pc_context_refreshes=workspace.adaptive_pc.context_rebuilds;
    result.pc_monitor_seconds=workspace.adaptive_pc.monitor_seconds;
    result.initial_jacobian_deferred=initial_jacobian_deferred;
    result.matrix_free_actions=context.matrix_free_actions;
    result.assembled_pc_reuses=context.assembled_pc_reuses;
    result.matrix_free_seconds=context.matrix_free_seconds;
    result.matrix_free_preparations=context.matrix_free_preparations;
    result.matrix_free_overlapped_actions=context.matrix_free_overlapped_actions;
    result.matrix_free_overlap_seconds=context.matrix_free_overlap_seconds;
    result.matrix_free_ghost_seconds=context.matrix_free_ghost_seconds;
    result.true_residual_checks=context.true_residual_checks;
    result.true_residual_rejections=context.true_residual_rejections;
    result.true_residual_seconds=context.true_residual_seconds;
    result.inexact_linear_solves=workspace.linear_policy.forcing_solves;
    result.recycle_projections=workspace.linear_policy.projections;
    result.recycle_vectors=static_cast<PetscInt>(workspace.linear_policy.basis.size());
    result.recycle_seconds=workspace.linear_policy.seconds;
    DeflatedFgmresStats deflated;
    if(query_deflated_fgmres_stats(pc,deflated)) {
        result.deflation_vectors=deflated.vectors;
        result.deflation_projections=deflated.projections;
        result.deflation_applications=deflated.projected_applications;
        result.deflation_spectral_updates=deflated.spectral_updates;
        result.deflation_operator_actions=deflated.operator_actions;
    }
    // Always assemble once afresh after SNESSolve. Save the unprojected owned
    // and ghost reactions before replacing constraint rows for acceptance.
    // Both outputs now describe this same evaluation, without a second kernel
    // pass or a repeated ghost update of the unchanged solution vector.
    context.evaluate(x.get(),r.get(),nullptr,false);
    local_values(r.get(),result.raw_residual);
    context.apply_constraints(r.get(),nullptr);
    EONSIM_PETSC(VecNorm(r.get(),NORM_2,&result.residual_norm));
    if(!std::isfinite(result.residual_norm)) throw std::runtime_error("Nonfinite nonlinear residual");
    acceptance.measure(r.get());
    if(report||!config.fields.empty()||!acceptance.passes()) acceptance.report();
    if(!acceptance.passes()) {
        const auto& failed=*std::find_if(acceptance.values.begin(),acceptance.values.end(),[](const auto& f){return !accepted(f);});
        throw StepRejected("Field acceptance failed: "+failed.name+" (SNES reason="+std::to_string(reason)+")");
    }
    result.field_residuals=acceptance.values;
    result.values=context.values;
    EONSIM_PETSC(SNESGetIterationNumber(snes.get(),&result.iterations));
    EONSIM_PETSC(SNESGetLinearSolveIterations(snes.get(),&result.linear_iterations));
    result.iterations+=prior_nonlinear_iterations;
    result.linear_iterations+=prior_linear_iterations;
    const double finalize_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-finalize_begin).count();
    if(report) {
        EONSIM_PETSC(PetscPrintf(comm,
            "nonlinear_communication overlap=%d fused_reductions=%d ghost_exchanges=%" PetscInt_FMT
            " field_reduction_calls=%" PetscInt_FMT " rank0_overlap_seconds=%.17g\n",
            int(bool(phases.owned)),int(acceptance.fused_reductions),context.ghost_exchanges,
            acceptance.reduction_calls,context.ghost_overlap_seconds));
        MatInfo info; EONSIM_PETSC(MatGetInfo(j.get(),MAT_GLOBAL_SUM,&info));
        PetscLogDouble memory=0; EONSIM_PETSC(PetscMemoryGetCurrentUsage(&memory));
        double system_peak=memory;
#if defined(__linux__)
        struct rusage usage{};
        if(getrusage(RUSAGE_SELF,&usage)!=0) throw std::runtime_error("Cannot read peak RSS");
        // Linux's getrusage high-water counter and PETSc's /proc current RSS
        // estimate are sampled differently. A newly observed current value is
        // also a lower bound on peak usage, even before ru_maxrss catches up.
        system_peak=1024.0*usage.ru_maxrss;
#endif
        const double peak=std::max(double(memory),system_peak);
        double local[]={solve_seconds,assembly_seconds,ghost_seconds,memory,peak,setup_seconds,
            schur_setup_seconds,diagnostics.solve_seconds,diagnostics.diagnostic_seconds,finalize_seconds,
            callback_seconds,failure_sync_seconds,assembly_finalize_seconds,constraint_seconds},maxima[14]{};
        MPI_Allreduce(local,maxima,14,MPI_DOUBLE,MPI_MAX,comm);
        const double local_memory[]{memory,peak}; double memory_totals[2]{};
        MPI_Allreduce(local_memory,memory_totals,2,MPI_DOUBLE,MPI_SUM,comm);
        const double memory_sum=memory_totals[0],peak_sum=memory_totals[1];
        int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
        KSPType kt; EONSIM_PETSC(KSPGetType(ksp,&kt));
        PCType type; EONSIM_PETSC(PCGetType(pc,&type));
        if(rank==0) std::cout << "solver_report ranks=" << ranks << " dofs=" << l.global << " nnz=" << info.nz_used
            << " nnz_allocated=" << info.nz_allocated << " nnz_unneeded=" << info.nz_unneeded
            << " matrix_mallocs=" << info.mallocs
            << " solver_reused=" << result.solver_reused << " solver_generation=" << result.solver_generation
            << " jacobian_assemblies=" << result.jacobian_assemblies << " jacobian_callbacks=" << result.jacobian_callbacks
            << " initial_jacobian_assemblies=" << result.initial_jacobian_assemblies
            << " initial_jacobian_reuses=" << result.initial_jacobian_reuses
            << " initial_jacobian_deferred=" << result.initial_jacobian_deferred
            << " user_schur_updates=" << result.user_schur_updates
            << " matrix_free=" << workspace.matrix_free << " matrix_free_actions=" << result.matrix_free_actions
            << " assembled_pc_reuses=" << result.assembled_pc_reuses
            << " matrix_free_seconds_rank0=" << result.matrix_free_seconds
            << " matrix_free_preparations=" << result.matrix_free_preparations
            << " matrix_free_overlapped_actions=" << result.matrix_free_overlapped_actions
            << " matrix_free_overlap_seconds_rank0=" << result.matrix_free_overlap_seconds
            << " matrix_free_ghost_seconds_rank0=" << result.matrix_free_ghost_seconds
            << " true_residual_checks=" << result.true_residual_checks
            << " true_residual_rejections=" << result.true_residual_rejections
            << " true_residual_seconds_rank0=" << result.true_residual_seconds
            << " inexact_linear_solves=" << result.inexact_linear_solves
            << " recycle_projections=" << result.recycle_projections
            << " recycle_vectors=" << result.recycle_vectors
            << " recycle_seconds_rank0=" << result.recycle_seconds
            << " deflation_vectors=" << result.deflation_vectors
            << " deflation_projections=" << result.deflation_projections
            << " deflation_applications=" << result.deflation_applications
            << " deflation_spectral_updates=" << result.deflation_spectral_updates
            << " deflation_operator_actions=" << result.deflation_operator_actions
            << " pc_refreshes=" << result.pc_refreshes << " pc_reuses=" << result.pc_reuses
            << " pc_rebuild_retries=" << result.pc_rebuild_retries
            << " pc_drift_refreshes=" << result.pc_drift_refreshes << " pc_age_refreshes=" << result.pc_age_refreshes
            << " pc_iteration_refreshes=" << result.pc_iteration_refreshes << " pc_context_refreshes=" << result.pc_context_refreshes
            << " pc_monitor_seconds_rank0=" << result.pc_monitor_seconds
            << " ksp=" << kt << " pc=" << type << " linear_iterations=" << result.linear_iterations
            << " snes_reason=" << reason << " ksp_reason=" << linear_reason << " domain_rejections=" << result.domain_rejections
            << " solve_seconds=" << maxima[0] << " assembly_seconds=" << maxima[1] << " ghost_seconds=" << maxima[2]
            << " setup_seconds=" << maxima[5] << " schur_setup_seconds=" << maxima[6]
            << " linear_seconds=" << maxima[7] << " linear_diagnostic_seconds=" << maxima[8]
            << " callback_seconds=" << maxima[10] << " failure_sync_seconds=" << maxima[11]
            << " assembly_finalize_seconds=" << maxima[12] << " constraint_seconds=" << maxima[13]
            << " finalize_seconds=" << maxima[9] << " linear_started=" << diagnostics.started
            << " linear_completed=" << diagnostics.completed
            << " rss_max_bytes=" << maxima[3] << " rss_sum_bytes=" << memory_sum
            << " peak_rss_max_bytes=" << maxima[4] << " peak_rss_sum_bytes=" << peak_sum << '\n';
        char processor[MPI_MAX_PROCESSOR_NAME+1]{}; int processor_length=0;
        MPI_Get_processor_name(processor,&processor_length);
        for(int i=0;i<processor_length;++i)
            if(processor[i]==' '||processor[i]=='\t'||processor[i]=='\n') processor[i]='_';
        if(workspace.rank_report) EONSIM_PETSC(PetscSynchronizedPrintf(comm,
            "solver_rank_report rank=%d owned=%" PetscInt_FMT " ghosts=%zu jacobian_assemblies=%" PetscInt_FMT
            " jacobian_callbacks=%" PetscInt_FMT " initial_jacobian_assemblies=%" PetscInt_FMT
            " initial_jacobian_reuses=%" PetscInt_FMT " initial_jacobian_deferred=%d user_schur_updates=%" PetscInt_FMT
            " callback_seconds=%.17g failure_sync_seconds=%.17g ghost_seconds=%.17g assembly_seconds=%.17g"
            " assembly_finalize_seconds=%.17g constraint_seconds=%.17g linear_seconds=%.17g"
            " host=%s rss_bytes=%.17g peak_rss_bytes=%.17g system_peak_rss_bytes=%.17g\n",
            rank,l.owned,l.local_to_global.size()-static_cast<std::size_t>(l.owned),
            result.jacobian_assemblies,result.jacobian_callbacks,result.initial_jacobian_assemblies,
            result.initial_jacobian_reuses,static_cast<int>(result.initial_jacobian_deferred),result.user_schur_updates,
            callback_seconds,failure_sync_seconds,ghost_seconds,assembly_seconds,
            assembly_finalize_seconds,constraint_seconds,diagnostics.solve_seconds,processor,memory,peak,system_peak));
        const auto tree=local_solver_report(ksp,rank);
        EONSIM_PETSC(PetscSynchronizedPrintf(comm,"%s",tree.c_str()));
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    // Destruction is collective too: local options may disable retention on
    // only one rank, even though the successful numerical solve was identical.
    const int keep=reuse&&workspace.reusable;
    int keep_global=0;
    MPI_Allreduce(&keep,&keep_global,1,MPI_INT,MPI_MIN,comm);
    scope.keep_workspace=keep_global;
    return result;
}
}
