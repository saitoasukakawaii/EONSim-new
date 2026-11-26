#include "eonsim/nonlinear_system.hpp"
#include <cstdint>
#include "eonsim/schur_solver.hpp"
#include "eonsim/pc_plan.hpp"
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
struct FieldAcceptance {
    MPI_Comm comm;
    std::vector<FieldResidual> values;
    std::vector<std::vector<PetscInt>> equations,constraints;
    std::vector<double> squares,sums,peaks,maxima;
    bool has_constraints=false;

    FieldAcceptance(MPI_Comm communicator,const AlgebraLayout& l,const SolverConfig& config,
                    const std::vector<PetscInt>& bc):comm(communicator) {
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
        MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,comm);
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
    }
    void measure(Vec r,bool initial=false) {
        const PetscScalar* a;
        EONSIM_PETSC(VecGetArrayRead(r,&a));
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
struct LinearDiagnostics {
    std::optional<FieldAcceptance> fields;
    PetscOwner<Vec,VecDestroy> residual;
    std::chrono::steady_clock::time_point begin;
    double solve_seconds=0,diagnostic_seconds=0;
    PetscInt started=0,completed=0;
    bool enabled=false;
    int collective_pc_failure=0;
    void reset() {
        solve_seconds=diagnostic_seconds=0.;
        started=completed=0; collective_pc_failure=0;
    }
};
PetscErrorCode linear_begin(KSP,Vec,Vec,void* pointer)
{
    auto& d=*static_cast<LinearDiagnostics*>(pointer);
    ++d.started; d.begin=std::chrono::steady_clock::now();
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
                out<<prefix<<"_residual solve="<<d.completed<<" norm="<<norm<<" rhs_norm="<<rhs<<'\n';
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
    values.assign(a,a+n);
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
    double callback_seconds=0,failure_sync_seconds=0,assembly_finalize_seconds=0,constraint_seconds=0;
    PcSchurUpdates* pc_updates=nullptr;
    PetscInt jacobian_assemblies=0,jacobian_callbacks=0,initial_jacobian_reuses=0,user_schur_updates=0;
    Vec initial_trial=nullptr;
    Mat initial_jacobian=nullptr;
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
        // A residual evaluation, rejected trial or new tangent must not leave
        // a startup Jacobian eligible for a later line-search/Newton state.
        initial_trial=nullptr; initial_jacobian=nullptr;
        const auto begin=std::chrono::steady_clock::now();
        local_values(x,values);
        ghost_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
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
        const auto callback_begin=std::chrono::steady_clock::now();
        try { assemble(values,r,j); }
        catch(const StepRejected& e) { error=e.what(); failed=1; }
        catch(const std::exception& e) { error=e.what(); failed=2; }
        const auto sync_begin=std::chrono::steady_clock::now();
        const double callback_time=std::chrono::duration<double>(sync_begin-callback_begin).count();
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
PetscErrorCode function(SNES snes,Vec x,Vec r,void* pointer)
{
    auto* active=static_cast<ActiveContext*>(pointer);
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    try { c.evaluate(x,r,nullptr,true); return PETSC_SUCCESS; }
    catch(const StepRejected& e) { c.error=e.what(); ++c.domain_rejections; return SNESSetFunctionDomainError(snes); }
    catch(const std::exception& e) { c.error=e.what(); return PETSC_ERR_LIB; }
}
PetscErrorCode jacobian(SNES snes,Vec x,Mat j,Mat,void* pointer)
{
    auto* active=static_cast<ActiveContext*>(pointer);
    if(!active||!active->current) return PETSC_ERR_ARG_WRONGSTATE;
    auto& c=*active->current;
    try {
        ++c.jacobian_callbacks;
        if(c.consume_initial_jacobian(x,j)) return PETSC_SUCCESS;
        // The fused physical callback may compute residual values while forming
        // J, but SNES consumes only J here. Ordinary Vec stashes still drain;
        // COO needs neither a scratch communication plan nor a publication.
        c.evaluate(x,c.scratch,j,true,false);
        // Refresh only after successful assembly, including constraint row replacement.
        c.refresh_user_schur(j);
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
    PcBlock plan;
    PcSchurUpdates pc_updates; // Must outlive the SNES/KSP/PC holding its USER matrices.
    ActiveContext callbacks;
    PetscBool block=PETSC_FALSE,schur=PETSC_FALSE,report=PETSC_FALSE,rank_report=PETSC_FALSE;
    bool semantic=false,pc_configured=false,reusable=false;
    PetscReal initial_lambda=1;
    PetscOwner<SNES,SNESDestroy> snes; // Destroy first, before callback/PC refresh storage.

    Workspace(MPI_Comm comm,const AlgebraLayout& layout,const SolverConfig& settings,
              const std::vector<PetscInt>& constraints)
        :config(settings),constraint_rows(constraints),acceptance(comm,layout,config,constraints) {}
    void initialize(MPI_Comm comm,const AlgebraLayout& l,Vec r,Mat j) {
        EONSIM_PETSC(SNESCreate(comm,snes.put()));
        EONSIM_PETSC(SNESSetFunction(snes.get(),r,function,&callbacks));
        EONSIM_PETSC(SNESSetJacobian(snes.get(),j,j,jacobian,&callbacks));
        EONSIM_PETSC(SNESSetTolerances(snes.get(),config.absolute_tolerance,config.relative_tolerance,0,config.maximum_iterations,10000));
        EONSIM_PETSC(SNESSetConvergenceTest(snes.get(),convergence,&callbacks,nullptr));
        KSP ksp; PC pc;
        EONSIM_PETSC(SNESGetKSP(snes.get(),&ksp)); EONSIM_PETSC(KSPGetPC(ksp,&pc));
        EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCLU));
        EONSIM_PETSC(PCFactorSetMatSolverType(pc,MATSOLVERSUPERLU_DIST));
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
            coarse_option=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_schur_approx",&nodal_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_velocity_solver",&velocity_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_structure_approx",&structure_option));
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-pc_plan_velocity_coarse_space",&coarse_option));
        int unused=!semantic&&(nodal_option||velocity_option||structure_option||coarse_option),any_unused=0;
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
            diagnostics.fields.emplace(acceptance);
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
        // Retain fresh-solver semantics for history-carrying nonlinear algorithms
        // or explicit lagged PCs (including prefixed child PCs). The ordinary
        // Newton path reuses symbolic objects, never stale numerical factors.
        reusable=nonlinear_type&&std::strcmp(nonlinear_type,SNESNEWTONLS)==0&&
            jacobian_lag==1&&preconditioner_lag==1&&!reuse_preconditioner&&!eisenstat_walker&&!permutation&&
            options.find("_reuse_preconditioner")==std::string::npos;
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
    const std::vector<double>& prescribed,const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble)
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
    const auto options=petsc_options_snapshot();
    int local[]={initial.size()!=l.local_to_global.size()||constraints.size()!=prescribed.size(),
        !reuse||!workspace_||!workspace_->reusable||workspace_->options!=options||
        !same_solver_config(workspace_->config,config)||workspace_->constraint_rows!=constraints};
    int global[2]{};
    MPI_Allreduce(local,global,2,MPI_INT,MPI_MAX,comm);
    if(global[0]) throw std::runtime_error("Invalid nonlinear state/constraint layout");
    const bool solver_reused=!global[1];
    if(!solver_reused) {
        workspace_.reset();
        workspace_=std::make_unique<Workspace>(comm,l,config,constraints);
        ++solver_generation_;
        workspace_->initialize(comm,l,r.get(),j.get());
        if(residual_coo_enabled_) {
            PetscObjectId residual_id=0;
            EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(r.get()),&residual_id));
            residual_coo_vectors_={residual_id};
        }
    }
    auto& workspace=*workspace_;
    auto& snes=workspace.snes;
    auto& acceptance=workspace.acceptance;
    auto& diagnostics=workspace.diagnostics;
    diagnostics.reset();
    const auto schur=workspace.schur,report=workspace.report;
    const bool semantic=workspace.semantic;
    KSP ksp; PC pc;
    EONSIM_PETSC(SNESGetKSP(snes.get(),&ksp)); EONSIM_PETSC(KSPGetPC(ksp,&pc));
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
        } else if(semantic&&initial_jacobian_assembled) context.refresh_user_schur(j.get());
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
    const auto error=SNESSolve(snes.get(),nullptr,x.get());
    const auto finalize_begin=std::chrono::steady_clock::now();
    const double solve_seconds=std::chrono::duration<double>(finalize_begin-solve_begin).count();
    const double assembly_seconds=context.assembly_seconds,ghost_seconds=context.ghost_seconds;
    // Freeze before final physical acceptance/reaction assembly, matching existing assembly timers.
    const double callback_seconds=context.callback_seconds,failure_sync_seconds=context.failure_sync_seconds;
    const double assembly_finalize_seconds=context.assembly_finalize_seconds,constraint_seconds=context.constraint_seconds;
    if(error&&!context.error.empty()) {
        // SNESComputeJacobian/Function can return from a failing callback before
        // VecLockReadPop (PETSc 3.23.7). Retire that trial Vec rather than editing
        // PETSc's lock stack. SNES retains its reference until normal destruction;
        // the next solve overwrites the fresh owned data and updates its ghosts.
        PetscOwner<Vec,VecDestroy> fresh;
        EONSIM_PETSC(VecDuplicate(x.get(),fresh.put()));
        std::swap(*x.put(),*fresh.put());
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
    result.initial_jacobian_deferred=initial_jacobian_deferred;
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
    const double finalize_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-finalize_begin).count();
    if(report) {
        MatInfo info; EONSIM_PETSC(MatGetInfo(j.get(),MAT_GLOBAL_SUM,&info));
        PetscLogDouble memory=0; EONSIM_PETSC(PetscMemoryGetCurrentUsage(&memory));
        double peak=memory;
#if defined(__linux__)
        struct rusage usage{};
        if(getrusage(RUSAGE_SELF,&usage)!=0) throw std::runtime_error("Cannot read peak RSS");
        peak=1024.0*usage.ru_maxrss;
#endif
        double local[]={solve_seconds,assembly_seconds,ghost_seconds,memory,peak,setup_seconds,
            schur_setup_seconds,diagnostics.solve_seconds,diagnostics.diagnostic_seconds,finalize_seconds,
            callback_seconds,failure_sync_seconds,assembly_finalize_seconds,constraint_seconds},maxima[14]{};
        MPI_Allreduce(local,maxima,14,MPI_DOUBLE,MPI_MAX,comm);
        double memory_sum=0; MPI_Allreduce(&memory,&memory_sum,1,MPI_DOUBLE,MPI_SUM,comm);
        double peak_sum=0; MPI_Allreduce(&peak,&peak_sum,1,MPI_DOUBLE,MPI_SUM,comm);
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
        if(workspace.rank_report) EONSIM_PETSC(PetscSynchronizedPrintf(comm,
            "solver_rank_report rank=%d owned=%" PetscInt_FMT " ghosts=%zu jacobian_assemblies=%" PetscInt_FMT
            " jacobian_callbacks=%" PetscInt_FMT " initial_jacobian_assemblies=%" PetscInt_FMT
            " initial_jacobian_reuses=%" PetscInt_FMT " initial_jacobian_deferred=%d user_schur_updates=%" PetscInt_FMT
            " callback_seconds=%.17g failure_sync_seconds=%.17g ghost_seconds=%.17g assembly_seconds=%.17g"
            " assembly_finalize_seconds=%.17g constraint_seconds=%.17g linear_seconds=%.17g\n",
            rank,l.owned,l.local_to_global.size()-static_cast<std::size_t>(l.owned),
            result.jacobian_assemblies,result.jacobian_callbacks,result.initial_jacobian_assemblies,
            result.initial_jacobian_reuses,static_cast<int>(result.initial_jacobian_deferred),result.user_schur_updates,
            callback_seconds,failure_sync_seconds,ghost_seconds,assembly_seconds,
            assembly_finalize_seconds,constraint_seconds,diagnostics.solve_seconds));
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
