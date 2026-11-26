#include "eonsim/fsi_level_smoother.hpp"
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
struct Example {
    static constexpr PetscInt n=9;
    MPI_Comm comm;
    PetscInt begin=0,end=0;
    std::array<double,n*n> values{};
    std::vector<DofKey> keys;
    std::vector<unsigned char> trace;
    PetscOwner<Mat,MatDestroy> matrix;
    Example(MPI_Comm communicator,bool coarse):comm(communicator) {
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
        values.fill(0.);values[0]=1.;
        for(PetscInt i=1;i<n;++i) {
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
            if(kind=="vanka") correct=correct&&std::abs(solution[i-example.begin]-example.exact(i))<2e-9;
        }
        EONSIM_PETSC(VecRestoreArrayRead(x.get(),&solution));
        require(comm,correct,"Level smoother altered identity constraints or full-patch exact solution");
        require(comm,std::isfinite(after)&&after<(kind=="vanka"?1e-9:.9)*before,
                "Level smoother failed its independently measured residual reduction");
        const auto stats=query_fsi_level_smoother_stats(smoother);
        require(comm,stats.refreshes==phase+1&&stats.applications==phase+1,"Level smoother generation/application accounting mismatch");
        if(kind=="vanka") {
            PetscInt interfaces=stats.patches.interface_patches,total=0;
            MPI_Allreduce(&interfaces,&total,1,MPIU_INT,MPI_SUM,comm);
            require(comm,total>0&&stats.patches.numeric_factorizations<=stats.patches.patches*(phase+1),
                    "All-level Vanka omitted the trace or duplicate-factor reuse");
        } else require(comm,stats.polynomial_degree==options.polynomial_degree&&stats.eigenvalue_upper>0.,
                       "Polynomial smoother did not publish its fixed degree/spectral bound");
    }
}
void run(MPI_Comm comm) {
    int ranks=0;MPI_Comm_size(comm,&ranks);require(comm,ranks==1||ranks==2||ranks==4,"Expected 1, 2 or 4 ranks");
    for(bool coarse:{false,true}) {
        verify(comm,"vanka",coarse,false);verify(comm,"vanka",coarse,true);
        verify(comm,"chebyshev",coarse,false);verify(comm,"block_chebyshev",coarse,false);
    }
    Example example(comm,false);
    FsiLevelSmootherOptions invalid;invalid.kind="chebyshev";invalid.eigenvalue_ratio=1.;
    bool rejected=false;try {make_fsi_level_smoother(comm,example.matrix.get(),example.keys,example.trace,invalid);}
    catch(const std::runtime_error&) {rejected=true;}
    require(comm,rejected,"Invalid Chebyshev spectral interval was accepted");
    EONSIM_PETSC(PetscPrintf(comm,"Coupled level smoothers: mixed/aggregate Vanka, FP32, identity/port/empty ranks, numeric refresh and normal/block Chebyshev passed\n"));
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);int result=0;
    try {run(PETSC_COMM_WORLD);}catch(const std::exception& error) {std::cerr<<"Level smoother verification failed: "<<error.what()<<'\n';result=1;}
    PetscFinalize();return result;
}
