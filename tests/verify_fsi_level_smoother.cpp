#include "eonsim/fsi_level_smoother.hpp"
#include "eonsim/native_float_sparse.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <numeric>

using namespace eonsim;
namespace {
void require(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0;MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
std::vector<double> dense_solve(std::vector<long double> a,std::vector<long double> b) {
    const auto n=b.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i) if(std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if(std::abs(a[pivot*n+k])<1e-24L) throw std::runtime_error("Singular independent smoother oracle");
        for(std::size_t j=0;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
        std::swap(b[k],b[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const auto factor=a[i*n+k]/a[k*n+k];
            for(std::size_t j=k;j<n;++j) a[i*n+j]-=factor*a[k*n+j];
            b[i]-=factor*b[k];
        }
    }
    for(std::size_t i=n;i-->0;) {
        for(std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
        b[i]/=a[i*n+i];
    }
    return std::vector<double>(b.begin(),b.end());
}
struct Example {
    static constexpr PetscInt n=9;
    MPI_Comm comm;
    PetscInt begin=0,end=0;
    std::array<double,n*n> values{};
    std::vector<DofKey> keys;
    std::vector<unsigned char> trace;
    PetscOwner<Mat,MatDestroy> matrix;
    PetscInt first_active;
    Example(MPI_Comm communicator,bool coarse,bool constrained=true):comm(communicator),first_active(constrained?1:0) {
        int rank=0,ranks=0;MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&ranks);
        // Two ranks have no owned rows in the four-rank negative/empty case.
        if(ranks==4) {const PetscInt cuts[]={0,5,n,n,n};begin=cuts[rank];end=cuts[rank+1];}
        else {begin=n*rank/ranks;end=n*(rank+1)/ranks;}
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,end-begin,nullptr,n-end+begin,nullptr,matrix.put()));
        for(PetscInt i=begin;i<end;++i) {
            DofKey key;
            key.entity=i/3;key.component=static_cast<std::uint16_t>(i%3);
            key.domain=coarse?DofDomain::scalar:(i%3==0?DofDomain::fluid:i%3==1?DofDomain::solid:DofDomain::mesh);
            key.quantity=coarse?DofQuantity::scalar_value:(i%3==0?DofQuantity::pressure:i%3==1?DofQuantity::velocity:DofQuantity::displacement);
            // Boundary scalars must also be covered by the full-level action.
            if(i==n-1) key.kind=DofEntity::boundary;
            keys.push_back(key);trace.push_back(i==3||i==4);
        }
        fill(0);
    }
    void fill(int phase) {
        values.fill(0.);
        if(first_active) values[0]=1.;
        for(PetscInt i=first_active;i<n;++i) {
            // Nonsymmetric and genuinely indefinite (pressure rows negative).
            const double row_scale=i%3==0?1e-3:i%3==1?1e2:1.;
            for(PetscInt j=0;j<n;++j)
                values[i*n+j]=row_scale*(i==j?(i%3==0?-2.5:4.8)+.1*phase:
                    .055*(i-j)+.021*(1+i)*(1+j));
        }
        PetscInt columns[n];std::iota(columns,columns+n,0);
        for(PetscInt i=begin;i<end;++i)
            EONSIM_PETSC(MatSetValues(matrix.get(),1,&i,n,columns,values.data()+i*n,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    }
    double exact(PetscInt i) const {return std::sin(.4*(i+1))+.2*std::cos(.17*i);}
    double rhs(PetscInt i) const {
        long double sum=0.;for(PetscInt j=0;j<n;++j) sum+=static_cast<long double>(values[i*n+j])*exact(j);
        return static_cast<double>(sum);
    }
    // Independent weighted norm used by the normal-equation polynomial.
    double weighted_norm(Vec residual) const {
        const PetscScalar* r=nullptr;EONSIM_PETSC(VecGetArrayRead(residual,&r));
        long double local=0.;
        for(PetscInt i=begin;i<end;++i) {
            double scale=0.;
            for(PetscInt j=i==0?0:1;j<n;++j) scale=std::max(scale,std::abs(values[i*n+j]));
            const long double value=r[i-begin]/scale;local+=value*value;
        }
        EONSIM_PETSC(VecRestoreArrayRead(residual,&r));
        long double sum=0.;MPI_Allreduce(&local,&sum,1,MPI_LONG_DOUBLE,MPI_SUM,comm);
        return std::sqrt(static_cast<double>(sum));
    }
};
void verify(MPI_Comm comm,const std::string& kind,bool coarse,bool single) {
    Example example(comm,coarse);
    FsiLevelSmootherOptions options;options.kind=kind;options.patches.maximum_size=32;
    options.patches.single_precision=single;options.polynomial_degree=5;
    auto smoother=make_fsi_level_smoother(comm,example.matrix.get(),example.keys,example.trace,options);
    const bool vanka=kind.find("vanka")==0;
    PetscOwner<Vec,VecDestroy> rhs,x,r,reference;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),x.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(x.get(),r.put()));EONSIM_PETSC(VecDuplicate(x.get(),reference.put()));
    for(int phase=0;phase<2;++phase) {
        if(phase) {example.fill(1);refresh_fsi_level_smoother(smoother,example.matrix.get());}
        PetscScalar* b=nullptr;PetscScalar* initial=nullptr;
        EONSIM_PETSC(VecGetArray(rhs.get(),&b));EONSIM_PETSC(VecGetArray(reference.get(),&initial));
        for(PetscInt i=example.begin;i<example.end;++i) {b[i-example.begin]=example.rhs(i);initial[i-example.begin]=i==0?example.rhs(0):0.;}
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&b));EONSIM_PETSC(VecRestoreArray(reference.get(),&initial));
        EONSIM_PETSC(MatMult(example.matrix.get(),reference.get(),r.get()));
        EONSIM_PETSC(VecAYPX(r.get(),-1.,rhs.get()));const double before=example.weighted_norm(r.get());
        EONSIM_PETSC(apply_fsi_level_smoother(smoother,rhs.get(),x.get()));
        EONSIM_PETSC(MatMult(example.matrix.get(),x.get(),r.get()));EONSIM_PETSC(VecAYPX(r.get(),-1.,rhs.get()));
        const double after=example.weighted_norm(r.get());
        const PetscScalar* solution=nullptr;EONSIM_PETSC(VecGetArrayRead(x.get(),&solution));
        bool correct=true;
        for(PetscInt i=example.begin;i<example.end;++i) {
            if(i==0) correct=correct&&solution[i-example.begin]==example.rhs(0);
            if(vanka) correct=correct&&std::abs(solution[i-example.begin]-example.exact(i))<2e-9;
        }
        EONSIM_PETSC(VecRestoreArrayRead(x.get(),&solution));
        require(comm,correct,"Level smoother altered identity constraints or full-patch exact solution");
        require(comm,std::isfinite(after)&&after<(vanka?1e-9:.9)*before,
                "Level smoother failed its independently measured residual reduction");
        const auto stats=query_fsi_level_smoother_stats(smoother);
        require(comm,stats.refreshes==phase+1&&stats.applications==phase+1,"Level smoother generation/application accounting mismatch");
        if(vanka) {
            PetscInt interfaces=stats.patches.interface_patches,total=0;
            MPI_Allreduce(&interfaces,&total,1,MPIU_INT,MPI_SUM,comm);
            require(comm,total>0&&stats.patches.numeric_factorizations<=stats.patches.patches*(phase+1),
                    "All-level Vanka omitted the trace or duplicate-factor reuse");
        } else require(comm,stats.polynomial_degree==options.polynomial_degree&&stats.eigenvalue_upper>0.,
                       "Polynomial smoother did not publish its fixed degree/spectral bound");
    }
}
void verify_native_storage(MPI_Comm comm,bool sparse,bool identity,const std::string& kind="vanka") {
    Example example(comm,false);
    if(sparse) {
        example.values.fill(0.);
        for(PetscInt i=1;i<Example::n;++i) {
            const double scale=i%3==0?1e-3:i%3==1?1e2:1.;
            example.values[i*Example::n+i]=4.*scale;
            if(i>1) example.values[i*Example::n+i-1]=-.25*scale;
            if(i+1<Example::n) example.values[i*Example::n+i+1]=.125*scale;
            // With an identity row, all active owners depend on its value,
            // including rank 1 whose constraint column is remote. Ranks 2/3
            // remain empty in the existing four-rank layout.
            example.values[i*Example::n]=.0625*(i+1)*scale;
        }
    }
    example.values[0]=identity?1.:4.;
    if(!identity) example.values[1]=.125;
    PetscInt columns[Example::n];std::iota(columns,columns+Example::n,0);
    for(PetscInt i=example.begin;i<example.end;++i)
        EONSIM_PETSC(MatSetValues(example.matrix.get(),1,&i,Example::n,columns,
            example.values.data()+i*Example::n,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(example.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(example.matrix.get(),MAT_FINAL_ASSEMBLY));

    // The source has a fully allocated graph. Its unique halo column map must
    // occupy halo-sized storage, not retain the nnz-sized sort/erase capacity.
    NativeFloatSparse compact;
    compact.update(example.matrix.get());
    require(comm,compact.columns.capacity()<=compact.columns.size()+1&&
        compact.values.capacity()<=compact.values.size()+1&&
        compact.offsets.capacity()<=compact.offsets.size()+1,
        "Native sparse arrays retain unused graph/growth capacity");

    FsiLevelSmootherOptions options;options.kind=kind;
    options.patches.maximum_size=32;
    options.patches.single_precision=true;options.patches.native_storage=true;
    auto smoother=make_fsi_level_smoother(comm,example.matrix.get(),example.keys,example.trace,options);
    const auto before=query_fsi_level_smoother_stats(smoother);
    PetscOwner<Vec,VecDestroy> rhs,x;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),x.put(),rhs.put()));
    release_native_fsi_smoother_setup(smoother);
    const auto released=query_fsi_level_smoother_stats(smoother);
    const auto& patch=released.patches;
    require(comm,patch.retained_fp64_matrix_bytes==0&&patch.factor_bytes==before.patches.factor_bytes&&
        patch.fp32_patches==patch.patches&&patch.fp64_patches==0&&
        patch.native_sparse_patches==(sparse?patch.patches:0)&&
        patch.native_dense_patches==(sparse?0:patch.patches),
        "Native patches did not retain the smaller dense/CSR coefficient representation");
    const unsigned long long retained=patch.fp32_matrix_bytes+patch.native_index_bytes;
    const unsigned long long dense=patch.factor_bytes;
    unsigned long long retained_total=0,dense_total=0;
    EONSIM_PETSC(MPI_Allreduce(&retained,&retained_total,1,MPI_UNSIGNED_LONG_LONG,MPI_SUM,comm));
    EONSIM_PETSC(MPI_Allreduce(&dense,&dense_total,1,MPI_UNSIGNED_LONG_LONG,MPI_SUM,comm));
    if(sparse&&kind=="vanka") require(comm,retained_total<dense_total,
        "Native CSR coefficients plus indices did not use less memory than dense coefficients");

    // Neither the native action nor its identity lifting may dereference this
    // source after release. The independent RHS/oracle uses the explicit small
    // matrix stored in Example, not production compact coefficients or factors.
    example.matrix=PetscOwner<Mat,MatDestroy>{};
    for(double amplitude:{1.,-.37}) {
        PetscScalar* b=nullptr;EONSIM_PETSC(VecGetArray(rhs.get(),&b));
        for(PetscInt i=example.begin;i<example.end;++i) b[i-example.begin]=amplitude*example.rhs(i);
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&b));
        EONSIM_PETSC(apply_fsi_level_smoother(smoother,rhs.get(),x.get()));
        const PetscScalar* solution=nullptr;EONSIM_PETSC(VecGetArrayRead(x.get(),&solution));
        bool accurate=true;
        for(PetscInt i=example.begin;i<example.end;++i) {
            const double expected=amplitude*example.exact(i);
            accurate=accurate&&std::isfinite(solution[i-example.begin])&&
                std::abs(solution[i-example.begin]-expected)<=2e-6*(1.+std::abs(expected));
            if(identity&&i==0) accurate=accurate&&solution[i-example.begin]==amplitude*example.rhs(0);
        }
        EONSIM_PETSC(VecRestoreArrayRead(x.get(),&solution));
        require(comm,accurate,"Released native coefficients changed the mixed action or remote identity lifting");
    }
}
void verify_braess(MPI_Comm comm,bool coarse,double alpha,bool use_default=false,bool constrained=true) {
    Example example(comm,coarse,constrained);
    // Retain a pure algebraic pressure tag on coarse entities, independently
    // of the fine physical domains. RCR-like boundary scalars remain primal.
    if(coarse) for(PetscInt i=example.begin;i<example.end;++i)
        if(i%3==0) example.keys[i-example.begin].quantity=DofQuantity::pressure;
    FsiLevelSmootherOptions options;
    options.kind="braess_sarazin";options.schur_iterations=3;
    if(!use_default) options.braess_alpha=alpha;
    auto smoother=make_fsi_level_smoother(comm,example.matrix.get(),example.keys,example.trace,options);
    PetscOwner<Vec,VecDestroy> rhs,x;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),x.put(),rhs.put()));
    int ranks=0;MPI_Comm_size(comm,&ranks);
    const auto owner=[&](PetscInt row) {
        if(ranks==4) return row<5?0:1;
        for(int rank=0;rank<ranks;++rank) if(row<Example::n*(rank+1)/ranks) return rank;
        return ranks-1;
    };
    for(int phase=0;phase<2;++phase) {
        if(phase) {example.fill(phase);refresh_fsi_level_smoother(smoother,example.matrix.get());}
        // Independently solve [alpha blockdiag(F),G;D,C], with the original
        // constraint-column lifting. The oracle neither forms nor reads the
        // production inverse, Schur matrix or PETSc field submatrices.
        std::vector<long double> approximate(example.values.begin(),example.values.end()),b(Example::n);
        for(PetscInt i=0;i<Example::n;++i) {
            b[i]=.4+std::sin(.7*i)+.2*phase;
            for(PetscInt j=example.first_active;j<Example::n;++j) if(i>=example.first_active&&i%3!=0&&j%3!=0) {
                const bool same_entity=i/3==j/3&&(i==8)==(j==8)&&owner(i)==owner(j);
                approximate[i*Example::n+j]=same_entity?alpha*example.values[i*Example::n+j]:0.;
            }
        }
        const auto expected=dense_solve(approximate,b);
        PetscScalar* data=nullptr;EONSIM_PETSC(VecGetArray(rhs.get(),&data));
        for(PetscInt i=example.begin;i<example.end;++i) data[i-example.begin]=static_cast<double>(b[i]);
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&data));
        EONSIM_PETSC(apply_fsi_level_smoother(smoother,rhs.get(),x.get()));
        const PetscScalar* actual=nullptr;EONSIM_PETSC(VecGetArrayRead(x.get(),&actual));
        bool correct=true;
        for(PetscInt i=example.begin;i<example.end;++i)
            correct=correct&&std::isfinite(actual[i-example.begin])&&
                std::abs(actual[i-example.begin]-expected[i])<2e-9*(1.+std::abs(expected[i]));
        EONSIM_PETSC(VecRestoreArrayRead(x.get(),&actual));
        const auto stats=query_fsi_level_smoother_stats(smoother);
        require(comm,correct,"Braess-Sarazin disagrees with independent full block inverse or loses structure/ALE compliance");
        require(comm,stats.refreshes==phase+1&&stats.schur_applications==phase+1&&stats.schur_budget==options.schur_iterations&&
            stats.schur_iterations<=options.schur_iterations*stats.schur_applications,
            "Braess-Sarazin exceeded its fixed pressure budget or failed numeric refresh");
        require(comm,stats.zero_lift_skips==(constrained?0:phase+1),
                "Braess-Sarazin used the wrong identity lifting path");
    }
    if(constrained&&!coarse&&alpha==1.) {
        // Zero one primal-block row while retaining pressure coupling and the
        // allocated graph. A failed refresh must invalidate its old factors.
        example.values[1*Example::n+1]=0.;example.values[1*Example::n+2]=0.;
        PetscInt columns[Example::n];std::iota(columns,columns+Example::n,0);
        if(example.begin<=1&&example.end>1) {
            const PetscInt row=1;
            EONSIM_PETSC(MatSetValues(example.matrix.get(),1,&row,Example::n,columns,
                example.values.data()+Example::n,INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(example.matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(example.matrix.get(),MAT_FINAL_ASSEMBLY));
        bool rejected=false;
        try {refresh_fsi_level_smoother(smoother,example.matrix.get());}
        catch(const std::runtime_error&) {rejected=true;}
        require(comm,rejected,"Singular Braess-Sarazin primal block retained a usable previous generation");
        require(comm,apply_fsi_level_smoother(smoother,rhs.get(),x.get())==PETSC_ERR_NOT_CONVERGED,
                "Failed Braess-Sarazin refresh did not invalidate the action");
        EONSIM_PETSC(VecSet(rhs.get(),2.));
        example.fill(0);refresh_fsi_level_smoother(smoother,example.matrix.get());
        EONSIM_PETSC(apply_fsi_level_smoother(smoother,rhs.get(),x.get()));
        EONSIM_PETSC(VecSet(rhs.get(),3.)); // Every inner-solve subvector was restored.
        require(comm,query_fsi_level_smoother_stats(smoother).refreshes==3,
                "Braess-Sarazin did not recover after a failed numeric refresh");
    }
}
void run(MPI_Comm comm) {
    int ranks=0;MPI_Comm_size(comm,&ranks);require(comm,ranks==1||ranks==2||ranks==4,"Expected 1, 2 or 4 ranks");
    for(bool coarse:{false,true}) {
        verify(comm,"vanka",coarse,false);verify(comm,"vanka",coarse,true);
        verify(comm,"chebyshev",coarse,false);verify(comm,"block_chebyshev",coarse,false);
    }
    for(bool sparse:{false,true}) for(bool identity:{false,true}) verify_native_storage(comm,sparse,identity);
    for(const std::string kind:{"vanka_multiplicative","vanka_colored"}) {
        verify(comm,kind,false,false);
        verify_native_storage(comm,true,true,kind);
    }
    for(bool coarse:{false,true}) {
        for(double alpha:{1.,1.7}) verify_braess(comm,coarse,alpha);
        // Exercise the production default without overriding it. The dense
        // oracle independently expects H=2*blockdiag(F) on both typed levels.
        verify_braess(comm,coarse,2.,true);
        verify_braess(comm,coarse,2.,true,false);
    }
    Example example(comm,false);
    FsiLevelSmootherOptions invalid;invalid.kind="chebyshev";invalid.eigenvalue_ratio=1.;
    bool rejected=false;try {make_fsi_level_smoother(comm,example.matrix.get(),example.keys,example.trace,invalid);}
    catch(const std::runtime_error&) {rejected=true;}
    require(comm,rejected,"Invalid Chebyshev spectral interval was accepted");
    EONSIM_PETSC(PetscPrintf(comm,"Coupled level smoothers: mixed/aggregate additive/multiplicative/colored Vanka, native residuals after source release, coupled Braess-Sarazin block oracle, identity/port/empty ranks, numeric refresh and normal/block Chebyshev passed\n"));
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);int result=0;
    try {run(PETSC_COMM_WORLD);}catch(const std::exception& error) {std::cerr<<"Level smoother verification failed: "<<error.what()<<'\n';result=1;}
    PetscFinalize();return result;
}
