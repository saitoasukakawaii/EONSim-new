#include "eonsim/fsi_level_smoother.hpp"
#include "fsi_profile.hpp"
#include <petscblaslapack.h>
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <tuple>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("FSI level smoother validation communication failed");
    if(any) throw std::runtime_error("FSI level smoother: "+message);
}
using Entity=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
using SparseRow=std::vector<std::pair<PetscInt,double>>;
bool vanka_kind(const std::string& kind) {
    return kind=="vanka"||kind=="vanka_multiplicative"||kind=="vanka_colored";
}
// Invert a small coupled primal block after two-sided equilibration. The
// scales are undone explicitly; no pressure stabilization or pivot shift is
// introduced to make an inadmissible block appear invertible.
bool invert_primal_block(const std::vector<double>& matrix,std::vector<double>& inverse) {
    const auto n=static_cast<PetscBLASInt>(std::sqrt(static_cast<double>(matrix.size())));
    std::vector<double> rows(n,0.),columns(n,0.),lu(matrix.size()),solved(matrix.size(),0.);
    for(PetscBLASInt i=0;i<n;++i) for(PetscBLASInt j=0;j<n;++j)
        rows[i]=std::max(rows[i],std::abs(matrix[i*n+j]));
    for(auto scale:rows) if(!(scale>0.&&std::isfinite(scale))) return false;
    for(PetscBLASInt i=0;i<n;++i) for(PetscBLASInt j=0;j<n;++j)
        columns[j]=std::max(columns[j],std::abs(matrix[i*n+j]/rows[i]));
    for(auto scale:columns) if(!(scale>0.&&std::isfinite(scale))) return false;
    for(PetscBLASInt i=0;i<n;++i) for(PetscBLASInt j=0;j<n;++j)
        lu[i+j*n]=(matrix[i*n+j]/rows[i])/columns[j];
    for(PetscBLASInt i=0;i<n;++i) solved[i+i*n]=1.;
    std::vector<PetscBLASInt> pivots(n);
    PetscBLASInt info=0;
    LAPACKgetrf_(&n,&n,lu.data(),&n,pivots.data(),&info);
    if(info) return false;
    LAPACKgetrs_("N",&n,&n,lu.data(),&n,pivots.data(),solved.data(),&n,&info);
    if(info) return false;
    inverse.resize(matrix.size());
    for(PetscBLASInt i=0;i<n;++i) for(PetscBLASInt j=0;j<n;++j) {
        inverse[i*n+j]=(solved[i+j*n]/columns[i])/rows[j];
        if(!std::isfinite(inverse[i*n+j])) return false;
    }
    return true;
}
long double inner_product(const SparseRow& a,const SparseRow& b) {
    std::size_t i=0,j=0; long double sum=0.;
    while(i<a.size()&&j<b.size()) {
        if(a[i].first<b[j].first) ++i;
        else if(b[j].first<a[i].first) ++j;
        else {sum+=static_cast<long double>(a[i].second)*b[j].second;++i;++j;}
    }
    return sum;
}
// G=Dg H Dg, H=L L^T. Return C=Dg^-1 L^-T, so C^T G C=I.
// Column equilibration prevents the pressure/velocity unit disparity from
// turning the small Cholesky test into an absolute-unit threshold.
bool whitening_factor(const std::vector<SparseRow>& columns,std::vector<double>& c) {
    const auto n=columns.size();
    std::vector<long double> scale(n),l(n*n,0.);
    for(std::size_t i=0;i<n;++i) {
        scale[i]=std::sqrt(inner_product(columns[i],columns[i]));
        if(!(scale[i]>0&&std::isfinite(scale[i]))) return false;
    }
    const long double tolerance=64.L*std::numeric_limits<double>::epsilon()*n;
    for(std::size_t i=0;i<n;++i) for(std::size_t j=0;j<=i;++j) {
        long double value=inner_product(columns[i],columns[j])/(scale[i]*scale[j]);
        for(std::size_t k=0;k<j;++k) value-=l[i*n+k]*l[j*n+k];
        if(i==j) {
            if(!(value>tolerance&&std::isfinite(value))) return false;
            l[i*n+j]=std::sqrt(value);
        } else l[i*n+j]=value/l[j*n+j];
    }
    c.assign(n*n,0.);
    std::vector<long double> solution(n);
    for(std::size_t column=0;column<n;++column) {
        std::fill(solution.begin(),solution.end(),0.);
        for(std::size_t i=n;i-->0;) {
            long double value=i==column?1.:0.;
            for(std::size_t j=i+1;j<n;++j) value-=l[j*n+i]*solution[j];
            solution[i]=value/l[i*n+i];
            c[i*n+column]=static_cast<double>(solution[i]/scale[i]);
            if(!std::isfinite(c[i*n+column])) return false;
        }
    }
    return true;
}
} // namespace

struct FsiLevelSmoother {
    MPI_Comm comm;
    Mat source=nullptr;
    PetscOwner<Mat,MatDestroy> source_reference;
    PetscObjectState graph=0;
    PetscInt begin=0,end=0,global=0;
    bool ready=false,braess_identity_lift=false;
    FsiLevelSmootherOptions options;
    FsiLevelSmootherStats stats;
    std::vector<DofKey> semantics;
    std::vector<unsigned char> identity;
    std::vector<PetscInt> identity_rows;
    std::vector<std::vector<PetscInt>> blocks;
    PcSchurUpdates updates; // Destroy KSP before its refresh state.
    PetscOwner<KSP,KSPDestroy> solver;
    PetscOwner<Mat,MatDestroy> right_transform,transformed,normal;
    PetscOwner<Vec,VecDestroy> row_scale,residual,scaled_rhs,normal_rhs,normal_solution,work;
    PetscOwner<IS,ISDestroy> primal_is,pressure_is;
    PetscOwner<Mat,MatDestroy> primal,gradient,divergence,pressure_block,primal_inverse,inverse_gradient,schur_product,schur;
    PetscOwner<Vec,VecDestroy> primal_solution,primal_rhs,primal_work,pressure_rhs,pressure_solution;
    std::vector<std::vector<PetscInt>> primal_blocks;
    std::vector<PetscInt> primal_offsets,pressure_offsets;

    std::vector<unsigned char> inspect_constraints(Mat matrix) const {
        std::vector<unsigned char> result(end-begin,0);
        bool valid=true;
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
            bool diagonal=false,is_identity=true;
            for(PetscInt j=0;j<count;++j) {
                valid=valid&&std::isfinite(values[j]);
                if(columns[j]==row) {diagonal=true;is_identity=is_identity&&values[j]==1.;}
                else is_identity=is_identity&&values[j]==0.;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
            result[row-begin]=diagonal&&is_identity;
        }
        common_check(comm,valid,"nonfinite level matrix");
        return result;
    }

    FsiLevelSmoother(MPI_Comm communicator,Mat matrix,const std::vector<DofKey>& keys,
                    const std::vector<unsigned char>& trace,const FsiLevelSmootherOptions& selected):
        comm(communicator),source(matrix),options(selected),semantics(keys) {
        EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(matrix)));
        *source_reference.put()=matrix;
        PetscInt columns=0,cbegin=0,cend=0;
        EONSIM_PETSC(MatGetSize(matrix,&global,&columns));
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRangeColumn(matrix,&cbegin,&cend));
        common_check(comm,global>0&&global==columns&&begin==cbegin&&end==cend&&
            static_cast<PetscInt>(keys.size())==end-begin&&trace.size()==keys.size(),"owned metadata/level layout mismatch");
        int selection=vanka_kind(options.kind)?1:options.kind=="chebyshev"?2:options.kind=="block_chebyshev"?3:
            options.kind=="braess_sarazin"?4:0;
        int lo=0,hi=0;
        EONSIM_PETSC(MPI_Allreduce(&selection,&lo,1,MPI_INT,MPI_MIN,comm));
        EONSIM_PETSC(MPI_Allreduce(&selection,&hi,1,MPI_INT,MPI_MAX,comm));
        common_check(comm,selection&&lo==hi,"kind must select Vanka, Chebyshev or Braess-Sarazin on every rank");
        if(options.kind=="vanka_multiplicative") options.patches.sweep="multiplicative";
        if(options.kind=="vanka_colored") options.patches.sweep="colored";
        PetscInt degree_min=0,degree_max=0;
        EONSIM_PETSC(MPI_Allreduce(&options.polynomial_degree,&degree_min,1,MPIU_INT,MPI_MIN,comm));
        EONSIM_PETSC(MPI_Allreduce(&options.polynomial_degree,&degree_max,1,MPIU_INT,MPI_MAX,comm));
        double ratio_min=0.,ratio_max=0.;
        EONSIM_PETSC(MPI_Allreduce(&options.eigenvalue_ratio,&ratio_min,1,MPI_DOUBLE,MPI_MIN,comm));
        EONSIM_PETSC(MPI_Allreduce(&options.eigenvalue_ratio,&ratio_max,1,MPI_DOUBLE,MPI_MAX,comm));
        common_check(comm,degree_min==degree_max&&degree_min>=1&&degree_max<=32&&
            std::isfinite(options.eigenvalue_ratio)&&ratio_min==ratio_max&&ratio_min>0&&ratio_max<1,
            "polynomial degree must be identical in 1..32 and interval ratio in (0,1)");
        common_check(comm,std::all_of(trace.begin(),trace.end(),[](unsigned char x){return x<=1;}),"invalid interface marker");
        EONSIM_PETSC(MatGetNonzeroState(matrix,&graph));
        identity=inspect_constraints(matrix);
        for(PetscInt i=0;i<end-begin;++i) if(identity[i]) identity_rows.push_back(begin+i);
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetErrorIfNotConverged(solver.get(),PETSC_FALSE));
        if(selection==1) {
            configure_vanka_level_pc(comm,solver.get(),matrix,keys,trace,options.patches,&updates);
            ready=true; stats.refreshes=1;
            return;
        }
        if(selection==4) {
            validate_interface_patch_options(comm,"",options.patches,false);
            PetscInt minimum=0,maximum=0;
            double alpha_min=0.,alpha_max=0.;
            EONSIM_PETSC(MPI_Allreduce(&options.schur_iterations,&minimum,1,MPIU_INT,MPI_MIN,comm));
            EONSIM_PETSC(MPI_Allreduce(&options.schur_iterations,&maximum,1,MPIU_INT,MPI_MAX,comm));
            EONSIM_PETSC(MPI_Allreduce(&options.braess_alpha,&alpha_min,1,MPI_DOUBLE,MPI_MIN,comm));
            EONSIM_PETSC(MPI_Allreduce(&options.braess_alpha,&alpha_max,1,MPI_DOUBLE,MPI_MAX,comm));
            common_check(comm,minimum==maximum&&minimum>=1&&maximum<=32&&std::isfinite(options.braess_alpha)&&
                alpha_min==alpha_max&&alpha_min>0.&&!options.patches.native_storage,
                "Braess-Sarazin requires equal positive alpha, 1..32 Schur iterations and FP64 setup storage");
            prepare_braess_partition();
            stats.schur_budget=options.schur_iterations;
            if(braess_identity_lift) EONSIM_PETSC(MatCreateVecs(source,residual.put(),nullptr));
            EONSIM_PETSC(KSPSetType(solver.get(),KSPGMRES));
            EONSIM_PETSC(KSPSetPCSide(solver.get(),PC_RIGHT));
            EONSIM_PETSC(KSPSetNormType(solver.get(),KSP_NORM_UNPRECONDITIONED));
            EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-50,PETSC_DEFAULT,options.schur_iterations));
            EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),options.schur_iterations));
            EONSIM_PETSC(KSPSetInitialGuessNonzero(solver.get(),PETSC_FALSE));
            PC pressure_pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pressure_pc));
            EONSIM_PETSC(PCSetType(pressure_pc,PCJACOBI));
            refresh(matrix);
            return;
        }
        // Polynomial modes also validate damping and precision/refinement
        // options, although their block whitening factors remain FP64.
        validate_interface_patch_options(comm,"",options.patches,false);
        if(selection==2) {
            for(PetscInt i=begin;i<end;++i) blocks.push_back({i});
        } else {
            std::map<Entity,std::vector<PetscInt>> by_entity;
            for(PetscInt i=0;i<end-begin;++i) {
                if(identity[i]) {blocks.push_back({begin+i});continue;}
                const auto& key=semantics[i];
                by_entity[{key.entity,key.kind,key.mode,key.space}].push_back(begin+i);
            }
            for(auto& entry:by_entity) blocks.push_back(std::move(entry.second));
        }
        EONSIM_PETSC(MatCreateVecs(source,row_scale.put(),nullptr));
        EONSIM_PETSC(VecDuplicate(row_scale.get(),residual.put()));
        EONSIM_PETSC(VecDuplicate(row_scale.get(),scaled_rhs.put()));
        EONSIM_PETSC(VecDuplicate(row_scale.get(),normal_rhs.put()));
        EONSIM_PETSC(VecDuplicate(row_scale.get(),normal_solution.put()));
        EONSIM_PETSC(VecDuplicate(row_scale.get(),work.put()));
        EONSIM_PETSC(KSPSetType(solver.get(),KSPCHEBYSHEV));
        EONSIM_PETSC(KSPSetNormType(solver.get(),KSP_NORM_NONE));
        EONSIM_PETSC(KSPSetConvergenceTest(solver.get(),KSPConvergedSkip,nullptr,nullptr));
        EONSIM_PETSC(KSPSetInitialGuessNonzero(solver.get(),PETSC_FALSE));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),PETSC_DEFAULT,PETSC_DEFAULT,PETSC_DEFAULT,options.polynomial_degree));
        PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));EONSIM_PETSC(PCSetType(pc,PCNONE));
        refresh(matrix);
    }

    void prepare_braess_partition() {
        std::vector<PetscInt> u,p;
        for(PetscInt i=0;i<end-begin;++i) if(!identity[i]) {
            const auto& key=semantics[i];
            (key.quantity==DofQuantity::pressure&&key.kind!=DofEntity::boundary?p:u).push_back(begin+i);
        }
        const PetscInt local[]={static_cast<PetscInt>(u.size()),static_cast<PetscInt>(p.size())};
        PetscInt totals[2]{};
        EONSIM_PETSC(MPI_Allreduce(local,totals,2,MPIU_INT,MPI_SUM,comm));
        common_check(comm,totals[0]>0&&totals[1]>0,
                     "Braess-Sarazin needs active pressure and primal rows with preserved quantity tags");
        stats.primal_rows=local[0];stats.pressure_rows=local[1];
        braess_identity_lift=totals[0]+totals[1]!=global;
        EONSIM_PETSC(ISCreateGeneral(comm,local[0],u.data(),PETSC_COPY_VALUES,primal_is.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,local[1],p.data(),PETSC_COPY_VALUES,pressure_is.put()));
        PetscInt offset=0;int rank=0;
        EONSIM_PETSC(MPI_Comm_rank(comm,&rank));
        EONSIM_PETSC(MPI_Exscan(&local[0],&offset,1,MPIU_INT,MPI_SUM,comm));
        if(rank==0) offset=0;
        std::map<Entity,std::vector<PetscInt>> grouped;
        for(std::size_t i=0;i<u.size();++i) {
            const auto& key=semantics[u[i]-begin];
            grouped[{key.entity,key.kind,key.mode,key.space}].push_back(offset+static_cast<PetscInt>(i));
        }
        bool bounded=true;
        for(auto& group:grouped) {
            bounded=bounded&&group.second.size()<=static_cast<std::size_t>(options.patches.maximum_size);
            primal_blocks.push_back(std::move(group.second));
        }
        common_check(comm,bounded,"a Braess-Sarazin primal entity exceeds the patch size limit");
        if(options.braess_local_fields) {
            for(auto index:u) primal_offsets.push_back(index-begin);
            for(auto index:p) pressure_offsets.push_back(index-begin);
        }
    }

    void refresh_braess(Mat matrix) {
        const bool first=!primal.get();
        const auto reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(matrix,primal_is.get(),primal_is.get(),reuse,primal.put()));
        EONSIM_PETSC(MatCreateSubMatrix(matrix,primal_is.get(),pressure_is.get(),reuse,gradient.put()));
        EONSIM_PETSC(MatCreateSubMatrix(matrix,pressure_is.get(),primal_is.get(),reuse,divergence.put()));
        EONSIM_PETSC(MatCreateSubMatrix(matrix,pressure_is.get(),pressure_is.get(),reuse,pressure_block.put()));
        PetscInt ubegin=0,uend=0,usize=0;
        EONSIM_PETSC(MatGetOwnershipRange(primal.get(),&ubegin,&uend));
        EONSIM_PETSC(MatGetSize(primal.get(),&usize,nullptr));
        if(first) {
            std::vector<PetscInt> nonzeros(uend-ubegin,0);
            for(const auto& block:primal_blocks) for(auto row:block)
                nonzeros[row-ubegin]=static_cast<PetscInt>(block.size());
            EONSIM_PETSC(MatCreateAIJ(comm,uend-ubegin,uend-ubegin,usize,usize,0,nonzeros.data(),0,nullptr,primal_inverse.put()));
        } else EONSIM_PETSC(MatZeroEntries(primal_inverse.get()));
        bool valid=true;
        for(const auto& block:primal_blocks) {
            const auto n=static_cast<PetscInt>(block.size());
            std::vector<double> values(static_cast<std::size_t>(n)*n),inverse;
            EONSIM_PETSC(MatGetValues(primal.get(),n,block.data(),n,block.data(),values.data()));
            const bool nonsingular=invert_primal_block(values,inverse);
            valid=valid&&nonsingular;
            if(nonsingular) {
                for(auto& value:inverse) {value/=options.braess_alpha;valid=valid&&std::isfinite(value);}
                EONSIM_PETSC(MatSetValues(primal_inverse.get(),n,block.data(),n,block.data(),inverse.data(),INSERT_VALUES));
            }
        }
        EONSIM_PETSC(MatAssemblyBegin(primal_inverse.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(primal_inverse.get(),MAT_FINAL_ASSEMBLY));
        common_check(comm,valid,"a coupled Braess-Sarazin primal block is singular or nonfinite; no shift was applied");
        EONSIM_PETSC(MatMatMult(primal_inverse.get(),gradient.get(),reuse,PETSC_DEFAULT,inverse_gradient.put()));
        EONSIM_PETSC(MatMatMult(divergence.get(),inverse_gradient.get(),reuse,PETSC_DEFAULT,schur_product.put()));
        if(first) {
            EONSIM_PETSC(MatDuplicate(pressure_block.get(),MAT_COPY_VALUES,schur.put()));
            EONSIM_PETSC(MatAXPY(schur.get(),-1.,schur_product.get(),DIFFERENT_NONZERO_PATTERN));
            EONSIM_PETSC(MatSetOption(schur.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
            EONSIM_PETSC(MatCreateVecs(primal.get(),primal_solution.put(),primal_work.put()));
            EONSIM_PETSC(VecDuplicate(primal_solution.get(),primal_rhs.put()));
            EONSIM_PETSC(MatCreateVecs(schur.get(),pressure_solution.put(),pressure_rhs.put()));
        } else {
            EONSIM_PETSC(MatZeroEntries(schur.get()));
            EONSIM_PETSC(MatAXPY(schur.get(),1.,pressure_block.get(),SUBSET_NONZERO_PATTERN));
            EONSIM_PETSC(MatAXPY(schur.get(),-1.,schur_product.get(),SUBSET_NONZERO_PATTERN));
        }
        EONSIM_PETSC(MatGetDiagonal(schur.get(),pressure_rhs.get()));
        const PetscScalar* diagonal=nullptr;
        EONSIM_PETSC(VecGetArrayRead(pressure_rhs.get(),&diagonal));
        for(PetscInt i=0;i<stats.pressure_rows;++i)
            valid=valid&&std::isfinite(diagonal[i])&&diagonal[i]!=0.;
        EONSIM_PETSC(VecRestoreArrayRead(pressure_rhs.get(),&diagonal));
        common_check(comm,valid,"Braess-Sarazin Schur Jacobi diagonal is zero or nonfinite; no pressure pin was added");
        EONSIM_PETSC(KSPSetOperators(solver.get(),schur.get(),schur.get()));
        EONSIM_PETSC(KSPSetReusePreconditioner(solver.get(),PETSC_FALSE));
        EONSIM_PETSC(KSPSetUp(solver.get()));
    }

    PetscErrorCode gather_field(const PetscScalar* mixed,const std::vector<PetscInt>& offsets,Vec field) {
        PetscFunctionBeginUser;
        PetscScalar* values=nullptr;
        PetscCall(VecGetArrayWrite(field,&values));
        for(std::size_t i=0;i<offsets.size();++i) values[i]=mixed[offsets[i]];
        PetscCall(VecRestoreArrayWrite(field,&values));
        PetscFunctionReturn(PETSC_SUCCESS);
    }

    PetscErrorCode add_field(Vec field,const std::vector<PetscInt>& offsets,PetscScalar* mixed) {
        PetscFunctionBeginUser;
        const PetscScalar* values=nullptr;
        PetscCall(VecGetArrayRead(field,&values));
        for(std::size_t i=0;i<offsets.size();++i) mixed[offsets[i]]+=options.patches.damping*values[i];
        PetscCall(VecRestoreArrayRead(field,&values));
        PetscFunctionReturn(PETSC_SUCCESS);
    }

    PetscErrorCode apply_braess(Vec input,Vec output,bool& valid) {
        PetscFunctionBeginUser;
        Vec active_rhs=input;
        if(braess_identity_lift) {
            const PetscScalar* rhs=nullptr;PetscScalar* x=nullptr;
            PetscCall(VecGetArrayRead(input,&rhs));PetscCall(VecGetArray(output,&x));
            for(PetscInt i=0;i<end-begin;++i) x[i]=identity[i]?rhs[i]:0.;
            PetscCall(VecRestoreArray(output,&x));PetscCall(VecRestoreArrayRead(input,&rhs));
            PetscCall(MatMult(source,output,residual.get()));
            PetscCall(VecAYPX(residual.get(),-1.,input));
            active_rhs=residual.get();
        } else {
            // The global lift is exactly zero, so applying A would perform a
            // halo exchange with no effect on the active right-hand side.
            PetscCall(VecSet(output,0.));
            ++stats.zero_lift_skips;
        }
        Vec ru=nullptr,rp=nullptr;
        if(options.braess_local_fields) {
            const PetscScalar* mixed=nullptr;
            PetscCall(VecGetArrayRead(active_rhs,&mixed));
            ru=primal_rhs.get();
            // The pressure KSP has a zero initial guess. Reuse its output for rp until KSPSolve.
            rp=pressure_solution.get();
            PetscCall(gather_field(mixed,primal_offsets,ru));
            PetscCall(gather_field(mixed,pressure_offsets,rp));
            PetscCall(VecRestoreArrayRead(active_rhs,&mixed));
        } else {
            PetscCall(VecGetSubVector(active_rhs,primal_is.get(),&ru));
            PetscCall(VecGetSubVector(active_rhs,pressure_is.get(),&rp));
        }
        PetscCall(MatMult(primal_inverse.get(),ru,primal_solution.get()));
        PetscCall(MatMult(divergence.get(),primal_solution.get(),pressure_rhs.get()));
        PetscCall(VecAYPX(pressure_rhs.get(),-1.,rp));
        if(!options.braess_local_fields) {
            PetscCall(VecCopy(ru,primal_rhs.get()));
            PetscCall(VecRestoreSubVector(active_rhs,pressure_is.get(),&rp));
            PetscCall(VecRestoreSubVector(active_rhs,primal_is.get(),&ru));
        }
        const auto error=profile_fsi_operation(options.schur_event,[&]{
            return KSPSolve(solver.get(),pressure_rhs.get(),pressure_solution.get());
        });
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
        PC pressure_pc=nullptr;PCFailedReason failure=PC_NOERROR;PetscInt iterations=0;
        PetscCall(KSPGetConvergedReason(solver.get(),&reason));
        PetscCall(KSPGetPC(solver.get(),&pressure_pc));PetscCall(PCGetFailedReason(pressure_pc,&failure));
        PetscCall(KSPGetIterationNumber(solver.get(),&iterations));
        // Exhausting the explicitly fixed inner budget is a valid smoother
        // action, not a claim that the Schur system was solved to tolerance.
        valid=error==PETSC_SUCCESS&&(reason>0||reason==KSP_DIVERGED_ITS)&&failure==PC_NOERROR;
        stats.schur_iterations+=iterations;++stats.schur_applications;
        int bad=!valid,any_bad=0;
        PetscCallMPI(MPI_Allreduce(&bad,&any_bad,1,MPI_INT,MPI_MAX,comm));
        if(any_bad) {
            valid=false;PetscCall(VecSet(output,0.));
            PetscFunctionReturn(PETSC_ERR_NOT_CONVERGED);
        }
        PetscCall(MatMult(gradient.get(),pressure_solution.get(),primal_work.get()));
        PetscCall(VecAYPX(primal_work.get(),-1.,primal_rhs.get()));
        PetscCall(MatMult(primal_inverse.get(),primal_work.get(),primal_solution.get()));
        if(options.braess_local_fields) {
            PetscScalar* mixed=nullptr;
            PetscCall(VecGetArray(output,&mixed));
            PetscCall(add_field(primal_solution.get(),primal_offsets,mixed));
            PetscCall(add_field(pressure_solution.get(),pressure_offsets,mixed));
            PetscCall(VecRestoreArray(output,&mixed));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        Vec du=nullptr,dp=nullptr;
        PetscCall(VecGetSubVector(output,primal_is.get(),&du));
        PetscCall(VecGetSubVector(output,pressure_is.get(),&dp));
        PetscCall(VecAXPY(du,options.patches.damping,primal_solution.get()));
        PetscCall(VecAXPY(dp,options.patches.damping,pressure_solution.get()));
        PetscCall(VecRestoreSubVector(output,pressure_is.get(),&dp));
        PetscCall(VecRestoreSubVector(output,primal_is.get(),&du));
        PetscFunctionReturn(PETSC_SUCCESS);
    }

    void refresh(Mat matrix) {
        ready=false;
        PetscObjectState current_graph=0;EONSIM_PETSC(MatGetNonzeroState(matrix,&current_graph));
        common_check(comm,matrix==source&&graph==current_graph,"matrix identity/graph changed; rebuild the level");
        common_check(comm,identity==inspect_constraints(matrix),"identity rows changed; rebuild the level");
        if(vanka_kind(options.kind)) {
            updates.refresh(matrix);ready=true;++stats.refreshes;return;
        }
        if(options.kind=="braess_sarazin") {
            refresh_braess(matrix);ready=true;++stats.refreshes;return;
        }
        PetscOwner<Mat,MatDestroy> scaled,transpose,c,b,n;
        EONSIM_PETSC(MatDuplicate(matrix,MAT_COPY_VALUES,scaled.put()));
        // The exact identity correction has already lifted its columns from
        // the residual. Remove them here as well so the polynomial cannot
        // perturb constraints through the normal-equation coupling.
        EONSIM_PETSC(MatZeroRowsColumns(scaled.get(),static_cast<PetscInt>(identity_rows.size()),
                                      identity_rows.data(),1.,nullptr,nullptr));
        bool valid=true;PetscScalar* scale=nullptr;
        EONSIM_PETSC(VecGetArray(row_scale.get(),&scale));
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(scaled.get(),row,&count,&columns,&values));
            double maximum=0.;for(PetscInt j=0;j<count;++j) maximum=std::max(maximum,std::abs(values[j]));
            EONSIM_PETSC(MatRestoreRow(scaled.get(),row,&count,&columns,&values));
            scale[row-begin]=maximum>0?1./maximum:0.;
            valid=valid&&scale[row-begin]>0&&std::isfinite(scale[row-begin]);
        }
        EONSIM_PETSC(VecRestoreArray(row_scale.get(),&scale));
        common_check(comm,valid,"normal polynomial cannot equilibrate a zero or nonfinite row");
        EONSIM_PETSC(MatDiagonalScale(scaled.get(),row_scale.get(),nullptr));
        EONSIM_PETSC(MatTranspose(scaled.get(),MAT_INITIAL_MATRIX,transpose.put()));
        std::vector<PetscInt> diagonal_nonzeros(end-begin,0);
        for(const auto& block:blocks) for(auto row:block) diagonal_nonzeros[row-begin]=static_cast<PetscInt>(block.size());
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,global,global,0,diagonal_nonzeros.data(),0,nullptr,c.put()));
        for(const auto& block:blocks) {
            std::vector<SparseRow> columns(block.size());
            for(std::size_t i=0;i<block.size();++i) {
                PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(transpose.get(),block[i],&count,&indices,&values));
                for(PetscInt j=0;j<count;++j) columns[i].emplace_back(indices[j],values[j]);
                EONSIM_PETSC(MatRestoreRow(transpose.get(),block[i],&count,&indices,&values));
                std::sort(columns[i].begin(),columns[i].end());
            }
            std::vector<double> whitening;
            const bool block_valid=whitening_factor(columns,whitening);
            valid=valid&&block_valid;
            if(block_valid) EONSIM_PETSC(MatSetValues(c.get(),static_cast<PetscInt>(block.size()),block.data(),
                static_cast<PetscInt>(block.size()),block.data(),whitening.data(),INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(c.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(c.get(),MAT_FINAL_ASSEMBLY));
        common_check(comm,valid,"column block Gram matrix is singular/nonfinite; no diagonal shift was applied");
        EONSIM_PETSC(MatMatMult(scaled.get(),c.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,b.put()));
        PetscReal one=0.,infinity=0.;
        EONSIM_PETSC(MatNorm(b.get(),NORM_1,&one));EONSIM_PETSC(MatNorm(b.get(),NORM_INFINITY,&infinity));
        const long double upper=1.05L*one*infinity;
        common_check(comm,upper>0&&std::isfinite(upper)&&upper<std::numeric_limits<double>::max(),
                     "normal polynomial spectral upper bound is not representable");
        EONSIM_PETSC(MatCreateNormal(b.get(),n.put()));
        EONSIM_PETSC(KSPSetOperators(solver.get(),n.get(),n.get()));
        EONSIM_PETSC(KSPChebyshevSetEigenvalues(solver.get(),static_cast<double>(upper),
                                             options.eigenvalue_ratio*static_cast<double>(upper)));
        EONSIM_PETSC(KSPSetUp(solver.get()));
        right_transform=std::move(c);transformed=std::move(b);normal=std::move(n);
        stats.eigenvalue_upper=static_cast<double>(upper);stats.polynomial_degree=options.polynomial_degree;
        ready=true;++stats.refreshes;
    }

    PetscErrorCode apply(Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!ready) {PetscCall(VecSet(output,0.));PetscFunctionReturn(PETSC_ERR_NOT_CONVERGED);}
        bool valid=true;
        if(vanka_kind(options.kind)) {
            PC pc=nullptr;PetscCall(KSPGetPC(solver.get(),&pc));
            PetscCall(PCSetFailedReason(pc,PC_NOERROR));
            const auto error=PCApply(pc,input,output);
            PCFailedReason failure=PC_NOERROR;PetscCall(PCGetFailedReason(pc,&failure));
            valid=error==PETSC_SUCCESS&&failure==PC_NOERROR;
        } else if(options.kind=="braess_sarazin") {
            PetscCall(apply_braess(input,output,valid));
        } else {
            const PetscScalar* rhs=nullptr;PetscScalar* x=nullptr;
            PetscCall(VecGetArrayRead(input,&rhs));PetscCall(VecGetArray(output,&x));
            for(PetscInt i=0;i<end-begin;++i) x[i]=identity[i]?rhs[i]:0.;
            PetscCall(VecRestoreArray(output,&x));PetscCall(VecRestoreArrayRead(input,&rhs));
            PetscCall(MatMult(source,output,residual.get()));
            PetscCall(VecAYPX(residual.get(),-1.,input));
            PetscCall(VecPointwiseMult(scaled_rhs.get(),row_scale.get(),residual.get()));
            PetscCall(MatMultTranspose(transformed.get(),scaled_rhs.get(),normal_rhs.get()));
            const auto error=KSPSolve(solver.get(),normal_rhs.get(),normal_solution.get());
            KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
            PetscCall(KSPGetConvergedReason(solver.get(),&reason));
            valid=error==PETSC_SUCCESS&&reason>0;
            PetscCall(MatMult(right_transform.get(),normal_solution.get(),work.get()));
            PetscCall(VecAXPY(output,options.patches.damping,work.get()));
        }
        const PetscScalar* values=nullptr;PetscCall(VecGetArrayRead(output,&values));
        for(PetscInt i=0;i<end-begin;++i) valid=valid&&std::isfinite(values[i]);
        PetscCall(VecRestoreArrayRead(output,&values));
        ++stats.applications;
        if(!valid) {PetscCall(VecSet(output,0.));PetscFunctionReturn(PETSC_ERR_NOT_CONVERGED);}
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};

FsiLevelSmootherHandle make_fsi_level_smoother(MPI_Comm comm,Mat matrix,
    const std::vector<DofKey>& semantics,const std::vector<unsigned char>& trace,
    const FsiLevelSmootherOptions& options) {
    return std::make_shared<FsiLevelSmoother>(comm,matrix,semantics,trace,options);
}
void refresh_fsi_level_smoother(const FsiLevelSmootherHandle& smoother,Mat matrix) {smoother->refresh(matrix);}
void release_native_fsi_smoother_setup(const FsiLevelSmootherHandle& smoother) {
    common_check(smoother->comm,vanka_kind(smoother->options.kind)&&smoother->options.patches.native_storage,
                 "native setup release requires native Vanka");
    release_native_vanka_setup(smoother->solver.get());
    smoother->source=nullptr;
    smoother->source_reference=PetscOwner<Mat,MatDestroy>{};
    // The pure native Vanka action owns its active-row mask. These copies are
    // used only by assembled setup/refresh, which is forbidden after release.
    std::vector<DofKey>().swap(smoother->semantics);
    std::vector<unsigned char>().swap(smoother->identity);
    std::vector<PetscInt>().swap(smoother->identity_rows);
}
PetscErrorCode apply_fsi_level_smoother(const FsiLevelSmootherHandle& smoother,Vec rhs,Vec correction) {
    return smoother->apply(rhs,correction);
}
FsiLevelSmootherStats query_fsi_level_smoother_stats(const FsiLevelSmootherHandle& smoother) {
    auto stats=smoother->stats;
    if(vanka_kind(smoother->options.kind)) {
        PC pc=nullptr;EONSIM_PETSC(KSPGetPC(smoother->solver.get(),&pc));
        (void)query_interface_patch_pc_stats(pc,stats.patches);
    }
    return stats;
}
} // namespace eonsim
