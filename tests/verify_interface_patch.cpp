#include "eonsim/interface_patch_pc.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>

using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool good,const char* message) {
    int bad=!good,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
// Independent long-double elimination on explicitly known patch rows. This
// oracle does not use production patches, multiplicities, scaling or factors.
std::vector<double> inverse_action(std::vector<long double> a,std::vector<long double> b) {
    const auto n=b.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i) if(std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if(std::abs(a[pivot*n+k])<1e-20L) throw std::runtime_error("Singular independent oracle");
        for(std::size_t j=k;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
        std::swap(b[k],b[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const auto ratio=a[i*n+k]/a[k*n+k];
            for(std::size_t j=k;j<n;++j) a[i*n+j]-=ratio*a[k*n+j];
            b[i]-=ratio*b[k];
        }
    }
    for(std::size_t i=n;i-->0;) {
        for(std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
        b[i]/=a[i*n+i];
    }
    return std::vector<double>(b.begin(),b.end());
}
struct Example {
    static constexpr PetscInt n=8;
    MPI_Comm comm;
    PetscInt begin=0,end=0;
    bool dense_graph;
    std::vector<double> a;
    std::vector<DofKey> semantics;
    std::vector<unsigned char> trace;
    PetscOwner<Mat,MatDestroy> matrix;
    Example(MPI_Comm communicator,bool dense,bool empty):comm(communicator),dense_graph(dense) {
        int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
        if(empty&&size==4) { const PetscInt cuts[]={0,4,8,8,8}; begin=cuts[rank];end=cuts[rank+1]; }
        else { begin=n*rank/size;end=n*(rank+1)/size; }
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,end-begin,nullptr,n-end+begin,nullptr,matrix.put()));
        EONSIM_PETSC(MatSetOption(matrix.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
        for(PetscInt i=begin;i<end;++i) {
            const auto domain=i==2?DofDomain::fluid:i==4?DofDomain::solid:i==6?DofDomain::mesh:DofDomain::fluid;
            const auto quantity=i==2||i==7?DofQuantity::pressure:i==6?DofQuantity::displacement:DofQuantity::velocity;
            semantics.push_back({i,domain,quantity,i==7?DofEntity::boundary:DofEntity::vertex,0,0,1});
            // The dense four-rank case has patch counts 2/1/0/0. Overlap
            // setup must support both unequal positive counts and empty ranks.
            trace.push_back(i==2||i==4||(dense_graph&&i==1));
        }
        fill(0);
    }
    void fill(int phase) {
        a.assign(n*n,0.);
        a[0]=1.; a[7*n+7]=3.5;
        for(PetscInt i=1;i<7;++i) {
            a[i*n+i]=4.+.3*i+.15*phase;
            for(PetscInt j=0;j<n;++j) if(i!=j&&(dense_graph||std::abs(i-j)==1))
                a[i*n+j]=.05*(i-j)+.017*(i+1)*(j+1);
        }
        if(phase==2) {
            // FP32 rounds this nonsingular 2-by-2 block to exact singularity.
            // The scaled FP64 factor remains usable, and fallback is explicit.
            for(PetscInt i=1;i<7;++i) for(PetscInt j=1;j<7;++j) a[i*n+j]=i==j?3.+i:0.;
            a[1*n+1]=2.; a[1*n+2]=2.;a[2*n+1]=2.;a[2*n+2]=2.+2e-8;
        }
        if(phase==3) for(PetscInt j=0;j<n;++j) a[2*n+j]=0.;
        publish();
    }
    void publish() {
        for(PetscInt i=begin;i<end;++i) {
            if(dense_graph) {
                PetscInt columns[n];std::iota(columns,columns+n,0);
                EONSIM_PETSC(MatSetValues(matrix.get(),1,&i,n,columns,a.data()+i*n,INSERT_VALUES));
            } else {
                // Include only the tridiagonal graph, even on row constraints.
                for(PetscInt j=std::max<PetscInt>(0,i-1);j<=std::min<PetscInt>(n-1,i+1);++j)
                    EONSIM_PETSC(MatSetValue(matrix.get(),i,j,a[i*n+j],INSERT_VALUES));
            }
        }
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    }
    std::vector<double> oracle(const std::vector<double>& rhs,double damping) const {
        std::vector<double> x(n),residual(n),weight(n,0.);
        for(PetscInt i=0;i<n;++i) x[i]=rhs[i]/a[i*n+i];
        for(PetscInt i=0;i<n;++i) {
            long double value=rhs[i];
            for(PetscInt j=0;j<n;++j) value-=static_cast<long double>(a[i*n+j])*x[j];
            residual[i]=static_cast<double>(value);
        }
        const std::vector<std::vector<PetscInt>> patches=dense_graph?
            std::vector<std::vector<PetscInt>>{{1,2,3,4,5,6},{1,2,3,4,5,6},{1,2,3,4,5,6}}:
            std::vector<std::vector<PetscInt>>{{1,2,3},{3,4,5}};
        for(const auto& patch:patches) for(auto i:patch) ++weight[i];
        for(const auto& patch:patches) {
            std::vector<long double> local_matrix,local_rhs;
            for(auto i:patch) {
                local_rhs.push_back(residual[i]);
                for(auto j:patch) local_matrix.push_back(a[i*n+j]);
            }
            const auto correction=inverse_action(local_matrix,local_rhs);
            for(std::size_t i=0;i<patch.size();++i) x[patch[i]]+=damping*correction[i]/weight[patch[i]];
        }
        return x;
    }
};
void configure_jacobi(KSP solver,Mat matrix,PcSchurUpdates*) {
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix)); EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(PCSetType(pc,PCJACOBI));
}
void action(MPI_Comm comm,KSP solver,const Example& example,double damping,int sample,bool near_singular=false) {
    PetscOwner<Vec,VecDestroy> rhs,solution,residual;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),solution.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(rhs.get(),residual.put()));
    std::vector<double> values(Example::n);
    for(PetscInt i=0;i<Example::n;++i) values[i]=sample?std::sin(.43*(i+1)):.5+.12*i;
    PetscScalar* data=nullptr; EONSIM_PETSC(VecGetArray(rhs.get(),&data));
    for(PetscInt i=example.begin;i<example.end;++i) data[i-example.begin]=values[i];
    EONSIM_PETSC(VecRestoreArray(rhs.get(),&data));
    const auto expected=example.oracle(values,damping);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc)); EONSIM_PETSC(KSPSetUp(solver));
    EONSIM_PETSC(PCApply(pc,rhs.get(),solution.get()));
    PCFailedReason failure; EONSIM_PETSC(PCGetFailedReason(pc,&failure));
    bool exact=failure==PC_NOERROR;
    const PetscScalar* actual=nullptr; EONSIM_PETSC(VecGetArrayRead(solution.get(),&actual));
    for(PetscInt i=example.begin;i<example.end;++i)
        exact=exact&&std::isfinite(actual[i-example.begin])&&std::abs(actual[i-example.begin]-expected[i])<
            (near_singular?2e-8:2e-10)*(1.+std::abs(expected[i]));
    EONSIM_PETSC(VecRestoreArrayRead(solution.get(),&actual));
    check(comm,exact,"Patch PCApply disagrees with independent mixed local inverses and multiplicity weighting");
    if(near_singular) return; // Deliberate fallback case is a local precision test.
    EONSIM_PETSC(VecSet(solution.get(),0.)); EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(MatMult(example.matrix.get(),solution.get(),residual.get()));
    EONSIM_PETSC(VecAXPY(residual.get(),-1.,rhs.get()));
    PetscReal norm=0,bnorm=0; EONSIM_PETSC(VecNorm(residual.get(),NORM_2,&norm));
    EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&bnorm));
    check(comm,reason>0&&norm<=1e-10*bnorm,"FGMRES with interface patches failed original true-residual gate");
}
void verify(MPI_Comm comm,bool dense,bool empty,bool single) {
    Example example(comm,dense,empty);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver; EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,30));
    EONSIM_PETSC(KSPSetOperators(solver.get(),example.matrix.get(),example.matrix.get()));
    InterfacePatchOptions options; options.single_precision=single; options.damping=dense?1.:.8;
    configure_interface_patch_pc(comm,solver.get(),example.matrix.get(),example.semantics,example.trace,
                                 options,configure_jacobi,&updates);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    for(int phase=0;phase<2;++phase) {
        if(phase) {example.fill(phase);updates.refresh(example.matrix.get());}
        for(int sample=0;sample<2;++sample) action(comm,solver.get(),example,options.damping,sample);
        InterfacePatchPcStats stats;
        check(comm,query_interface_patch_pc_stats(pc,stats)&&stats.rebuilds==phase+1&&
              stats.applications>0&&stats.fp32_patches==(single?stats.patches:0)&&
              stats.factor_bytes==static_cast<std::size_t>(stats.patches)*(dense?36:9)*(single?sizeof(float):sizeof(double)),
              "Patch refresh count or FP32 factor storage accounting is wrong");
    }
    InterfacePatchPcStats before_cache;query_interface_patch_pc_stats(pc,before_cache);
    // Reassemble the same numeric values, changing PETSc object state. A cache
    // keyed only by object identity/state would miss this reusable generation.
    example.fill(1);updates.refresh(example.matrix.get());
    action(comm,solver.get(),example,options.damping,0);
    InterfacePatchPcStats after_cache;query_interface_patch_pc_stats(pc,after_cache);
    check(comm,after_cache.numeric_factorizations==before_cache.numeric_factorizations&&
        after_cache.factor_batches==before_cache.factor_batches&&
        after_cache.cached_factorizations==before_cache.cached_factorizations+after_cache.patches&&
        after_cache.rebuilds==before_cache.rebuilds+1,
        "Exactly unchanged patch matrices were needlessly refactored");
    check(comm,after_cache.numeric_factorizations==2*(dense?(after_cache.patches?1:0):after_cache.patches)&&
        after_cache.factor_batches<=after_cache.numeric_factorizations,
        "Equal-size batching or identical-patch factorization reuse was not exercised");
    if(dense&&single) {
        example.fill(2);updates.refresh(example.matrix.get());
        action(comm,solver.get(),example,options.damping,0,true);
        InterfacePatchPcStats stats; query_interface_patch_pc_stats(pc,stats);
        check(comm,stats.setup_fallbacks==(stats.patches?1:0)&&stats.fp64_patches==stats.patches,
              "FP32 singular rounding did not trigger explicit FP64 fallback");
        example.fill(0);updates.refresh(example.matrix.get());
    }
    // Failed refresh invalidates every generation. PCApply must finish PETSc's
    // input-lock cleanup; a successful refresh then restores the same shell.
    example.fill(3);
    bool rejected=false;
    try {updates.refresh(example.matrix.get());} catch(const LinearSolveFailure&) {rejected=true;}
    check(comm,rejected,"Singular mixed patch was not rejected collectively");
    PetscOwner<Vec,VecDestroy> rhs,solution;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),solution.put(),rhs.put()));
    EONSIM_PETSC(VecSet(rhs.get(),1.)); EONSIM_PETSC(PCApply(pc,rhs.get(),solution.get()));
    PCFailedReason failure; EONSIM_PETSC(PCGetFailedReason(pc,&failure));
    check(comm,failure==PC_SUBPC_ERROR,"Failed patch refresh left a usable stale generation");
    EONSIM_PETSC(VecSet(rhs.get(),2.)); // Fails if the shell leaked a read lock.
    example.fill(0);updates.refresh(example.matrix.get());
    action(comm,solver.get(),example,options.damping,1);
    // Explicit cap rejection is preferable to silently dropping coupling rows.
    InterfacePatchOptions too_small=options; too_small.maximum_size=1;
    PcSchurUpdates rejected_updates;
    PetscOwner<KSP,KSPDestroy> capped;EONSIM_PETSC(KSPCreate(comm,capped.put()));
    EONSIM_PETSC(KSPSetOperators(capped.get(),example.matrix.get(),example.matrix.get()));
    rejected=false;
    try {configure_interface_patch_pc(comm,capped.get(),example.matrix.get(),example.semantics,example.trace,
                                    too_small,configure_jacobi,&rejected_updates);}
    catch(const std::runtime_error&) {rejected=true;}
    check(comm,rejected,"Oversize interface patch was silently truncated");
}
void verify_sweep(MPI_Comm comm,const std::string& sweep) {
    Example example(comm,false,true);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;EONSIM_PETSC(KSPCreate(comm,solver.put()));
    InterfacePatchOptions options;options.sweep=sweep;options.damping=.8;
    configure_vanka_level_pc(comm,solver.get(),example.matrix.get(),example.semantics,example.trace,options,&updates);
    std::vector<std::vector<PetscInt>> rows;
    std::vector<PetscInt> colors;
    check(comm,query_vanka_patch_schedule(solver.get(),rows,colors),"Vanka did not expose its local color schedule");
    // Only this eight-row test gathers the tiny patch schedule. Production
    // builds and colors its conflict graph through distributed sparse products.
    std::vector<PetscInt> encoded;
    for(std::size_t p=0;p<rows.size();++p) {
        encoded.push_back(colors[p]);encoded.push_back(static_cast<PetscInt>(rows[p].size()));
        encoded.insert(encoded.end(),rows[p].begin(),rows[p].end());
    }
    int ranks=0;MPI_Comm_size(comm,&ranks);
    const int local=static_cast<int>(encoded.size());
    std::vector<int> counts(ranks),offsets(ranks,0);
    MPI_Allgather(&local,1,MPI_INT,counts.data(),1,MPI_INT,comm);
    for(int i=1;i<ranks;++i) offsets[i]=offsets[i-1]+counts[i-1];
    std::vector<PetscInt> all(offsets.back()+counts.back());
    MPI_Allgatherv(encoded.data(),local,MPIU_INT,all.data(),counts.data(),offsets.data(),MPIU_INT,comm);
    rows.clear();colors.clear();
    for(std::size_t position=0;position<all.size();) {
        colors.push_back(all[position++]);const auto n=static_cast<std::size_t>(all[position++]);
        rows.emplace_back(all.begin()+position,all.begin()+position+n);position+=n;
    }
    bool conflict_free=true;
    for(std::size_t p=0;p<rows.size();++p) for(std::size_t q=0;q<p;++q) if(colors[p]==colors[q])
        for(auto row:rows[p]) conflict_free=conflict_free&&!std::binary_search(rows[q].begin(),rows[q].end(),row);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    InterfacePatchPcStats before;query_interface_patch_pc_stats(pc,before);
    check(comm,conflict_free&&before.colors>1&&
        (sweep=="multiplicative"?before.colors==static_cast<PetscInt>(rows.size()):before.colors<static_cast<PetscInt>(rows.size())),
        "Patch colors conflict across owners or fail to group independent patches");
    PetscOwner<Vec,VecDestroy> rhs,solution;
    EONSIM_PETSC(MatCreateVecs(example.matrix.get(),solution.put(),rhs.put()));
    for(int phase=0;phase<2;++phase) {
        if(phase) {example.fill(phase);updates.refresh(example.matrix.get());}
        std::vector<double> b(Example::n),expected(Example::n,0.);
        for(PetscInt i=0;i<Example::n;++i) b[i]=std::sin(.4*(i+1))+.1*phase;
        expected[0]=b[0];
        for(PetscInt color=0;color<before.colors;++color) {
            std::vector<long double> residual(Example::n);
            for(PetscInt i=0;i<Example::n;++i) {
                residual[i]=b[i];
                for(PetscInt j=0;j<Example::n;++j) residual[i]-=example.a[i*Example::n+j]*expected[j];
            }
            for(std::size_t p=0;p<rows.size();++p) if(colors[p]==color) {
                std::vector<long double> a,r;
                for(auto i:rows[p]) {
                    r.push_back(residual[i]);
                    for(auto j:rows[p]) a.push_back(example.a[i*Example::n+j]);
                }
                const auto dx=inverse_action(a,r);
                for(std::size_t j=0;j<rows[p].size();++j) expected[rows[p][j]]+=options.damping*dx[j];
            }
        }
        PetscScalar* data=nullptr;EONSIM_PETSC(VecGetArray(rhs.get(),&data));
        for(PetscInt i=example.begin;i<example.end;++i) data[i-example.begin]=b[i];
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&data));
        EONSIM_PETSC(PCApply(pc,rhs.get(),solution.get()));
        const PetscScalar* actual=nullptr;EONSIM_PETSC(VecGetArrayRead(solution.get(),&actual));
        bool accurate=true;
        for(PetscInt i=example.begin;i<example.end;++i)
            accurate=accurate&&std::abs(actual[i-example.begin]-expected[i])<2e-11*(1.+std::abs(expected[i]));
        EONSIM_PETSC(VecRestoreArrayRead(solution.get(),&actual));
        InterfacePatchPcStats stats;query_interface_patch_pc_stats(pc,stats);
        check(comm,accurate&&stats.color_stages==stats.colors*(phase+1)&&stats.residual_products==stats.color_stages,
            "Vanka sweep does not match independent color-by-color residuals or kept additive overlap weights");
    }
}
void run(MPI_Comm comm) {
    int ranks=0; MPI_Comm_size(comm,&ranks);
    check(comm,ranks==1||ranks==2||ranks==4,"Expected 1, 2 or 4 ranks");
    for(bool single:{false,true}) {
        verify(comm,true,true,single);
        verify(comm,false,false,single);
    }
    verify_sweep(comm,"multiplicative");verify_sweep(comm,"colored");
    EONSIM_PETSC(PetscPrintf(comm,"Interface mixed patches: exact weighted action, distributed conflict coloring, multiplicative per-color residual oracle, ghost rows, empty ranks, batched LU, exact factor cache, FP32 refinement/fallback and failed-generation recovery passed\n"));
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try {run(PETSC_COMM_WORLD);}
    catch(const std::exception& error) {std::cerr<<"Interface patch verification failed: "<<error.what()<<'\n';result=1;}
    PetscFinalize();return result;
}
