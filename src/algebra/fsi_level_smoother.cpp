#include "eonsim/fsi_level_smoother.hpp"
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
        throw std::runtime_error("FSI level smoother validation communication failed");
    if(any) throw std::runtime_error("FSI level smoother: "+message);
}
using Entity=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
using SparseRow=std::vector<std::pair<PetscInt,double>>;
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
    bool ready=false;
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
        int selection=options.kind=="vanka"?1:options.kind=="chebyshev"?2:options.kind=="block_chebyshev"?3:0;
        int lo=0,hi=0;
        EONSIM_PETSC(MPI_Allreduce(&selection,&lo,1,MPI_INT,MPI_MIN,comm));
        EONSIM_PETSC(MPI_Allreduce(&selection,&hi,1,MPI_INT,MPI_MAX,comm));
        common_check(comm,selection&&lo==hi,"kind must be vanka, chebyshev or block_chebyshev on every rank");
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

    void refresh(Mat matrix) {
        ready=false;
        PetscObjectState current_graph=0;EONSIM_PETSC(MatGetNonzeroState(matrix,&current_graph));
        common_check(comm,matrix==source&&graph==current_graph,"matrix identity/graph changed; rebuild the level");
        common_check(comm,identity==inspect_constraints(matrix),"identity rows changed; rebuild the level");
        if(options.kind=="vanka") {
            updates.refresh(matrix);ready=true;++stats.refreshes;return;
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
        if(options.kind=="vanka") {
            PC pc=nullptr;PetscCall(KSPGetPC(solver.get(),&pc));
            PetscCall(PCSetFailedReason(pc,PC_NOERROR));
            const auto error=PCApply(pc,input,output);
            PCFailedReason failure=PC_NOERROR;PetscCall(PCGetFailedReason(pc,&failure));
            valid=error==PETSC_SUCCESS&&failure==PC_NOERROR;
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
    common_check(smoother->comm,smoother->options.kind=="vanka"&&smoother->options.patches.native_storage,
                 "native setup release requires native Vanka");
    release_native_vanka_setup(smoother->solver.get());
    smoother->source=nullptr;
    smoother->source_reference=PetscOwner<Mat,MatDestroy>{};
}
PetscErrorCode apply_fsi_level_smoother(const FsiLevelSmootherHandle& smoother,Vec rhs,Vec correction) {
    return smoother->apply(rhs,correction);
}
FsiLevelSmootherStats query_fsi_level_smoother_stats(const FsiLevelSmootherHandle& smoother) {
    auto stats=smoother->stats;
    if(smoother->options.kind=="vanka") {
        PC pc=nullptr;EONSIM_PETSC(KSPGetPC(smoother->solver.get(),&pc));
        (void)query_interface_patch_pc_stats(pc,stats.patches);
    }
    return stats;
}
} // namespace eonsim
