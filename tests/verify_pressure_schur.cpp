#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <vector>

using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool condition,const char* message) {
    int bad=!condition,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
// Independent dense elimination: no PETSc Schur matrix, production products,
// inverse weights or USER matrix is used to produce the expected action.
std::vector<long double> dense_solve(std::vector<long double> matrix,std::vector<long double> rhs) {
    const auto n=rhs.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i)
            if(std::abs(matrix[i*n+k])>std::abs(matrix[pivot*n+k])) pivot=i;
        if(std::abs(matrix[pivot*n+k])<1e-20L) throw std::runtime_error("singular pressure oracle");
        for(std::size_t j=k;j<n;++j) std::swap(matrix[k*n+j],matrix[pivot*n+j]);
        std::swap(rhs[k],rhs[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const auto factor=matrix[i*n+k]/matrix[k*n+k];
            for(std::size_t j=k;j<n;++j) matrix[i*n+j]-=factor*matrix[k*n+j];
            rhs[i]-=factor*rhs[k];
        }
    }
    for(std::size_t k=n;k-->0;) {
        for(std::size_t j=k+1;j<n;++j) rhs[k]-=matrix[k*n+j]*rhs[j];
        rhs[k]/=matrix[k*n+k];
    }
    return rhs;
}
std::vector<long double> dense_mult(const std::vector<long double>& matrix,
                                   const std::vector<long double>& input) {
    std::vector<long double> output(input.size(),0.);
    for(std::size_t i=0;i<input.size();++i) for(std::size_t j=0;j<input.size();++j)
        output[i]+=matrix[i*input.size()+j]*input[j];
    return output;
}

struct Example {
    MPI_Comm comm;
    PetscInt begin=0,end=0;
    static constexpr PetscInt n=7;
    const std::array<PetscInt,3> vr{{0,3,5}};
    const std::array<PetscInt,2> pr{{1,4}};
    std::vector<PetscInt> velocity_rows,pressure_rows;
    PetscOwner<Mat,MatDestroy> matrix,mass,laplace,transport;
    std::vector<long double> a,b,c,d,m,k,f;

    explicit Example(MPI_Comm communicator):comm(communicator) {
        int rank=0,ranks=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
        if(ranks==4) {
            const PetscInt cuts[]={0,3,5,7,7}; begin=cuts[rank]; end=cuts[rank+1];
        } else { begin=n*rank/ranks; end=n*(rank+1)/ranks; }
        for(auto row:vr) if(row>=begin&&row<end) velocity_rows.push_back(row);
        for(auto row:pr) if(row>=begin&&row<end) pressure_rows.push_back(row);
        for(auto* owner:{&matrix,&mass,&laplace,&transport}) {
            EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,end-begin,nullptr,
                n-end+begin,nullptr,owner->put()));
            EONSIM_PETSC(MatSetOption(owner->get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
        }
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(matrix.get()),pressure_pcd_mass_key,
            reinterpret_cast<PetscObject>(mass.get())));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(matrix.get()),pressure_pcd_laplace_key,
            reinterpret_cast<PetscObject>(laplace.get())));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(matrix.get()),pressure_pcd_transport_key,
            reinterpret_cast<PetscObject>(transport.get())));
        fill(0);
    }
    void publish(Mat target,const std::vector<long double>& values) {
        std::array<PetscInt,n> columns{};std::iota(columns.begin(),columns.end(),0);
        std::array<double,n> row_values{};
        for(PetscInt row=begin;row<end;++row) {
            for(PetscInt col=0;col<n;++col) row_values[col]=static_cast<double>(values[row*n+col]);
            EONSIM_PETSC(MatSetValues(target,1,&row,n,columns.data(),row_values.data(),INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(target,MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(target,MAT_FINAL_ASSEMBLY));
    }
    void fill(int phase,bool zero_stabilization=false,bool scalar_momentum=false) {
        const long double shift=.15L*phase;
        a={4.+shift,.3L,-.1L,-.2L,2.+2*shift,.4L,.1L,-.3L,3.+shift};
        b={-1.L,-.2L,-.3L,-1.L,-.4L,-.6L};
        c={1.1L,.25L,.45L,.15L,1.05L,.55L}; // Deliberately not -B^T.
        d={.4L+shift,-.05L,.08L,.6L+shift};
        m={1.2L+shift,.8L+shift};
        k={2.2L+shift,-.3L,-.4L,1.7L+shift};
        f={4.2L+shift,.5L,-.25L,3.4L+2*shift};
        if(phase==2) { b[0]=0.; a[1]=0.; a[3]=0.; d[1]=0.; f[1]=0.; }
        if(zero_stabilization) std::fill(d.begin(),d.end(),0.);
        if(scalar_momentum) { std::fill(a.begin(),a.end(),0.); a[0]=a[4]=a[8]=3.25L; }
        std::vector<long double> full(n*n,0.),pm(n*n,0.),pk(n*n,0.),pf(n*n,0.);
        full[2*n+2]=1.; full[6*n+6]=1.;
        for(std::size_t i=0;i<vr.size();++i) {
            for(std::size_t j=0;j<vr.size();++j) full[vr[i]*n+vr[j]]=a[i*3+j];
            for(std::size_t j=0;j<pr.size();++j) full[vr[i]*n+pr[j]]=b[i*2+j];
        }
        for(std::size_t i=0;i<pr.size();++i) {
            for(std::size_t j=0;j<vr.size();++j) full[pr[i]*n+vr[j]]=c[i*3+j];
            for(std::size_t j=0;j<pr.size();++j) {
                full[pr[i]*n+pr[j]]=d[i*2+j];
                pm[pr[i]*n+pr[j]]=i==j?m[i]:0.;
                pk[pr[i]*n+pr[j]]=k[i*2+j];
                pf[pr[i]*n+pr[j]]=f[i*2+j];
            }
        }
        publish(matrix.get(),full);publish(mass.get(),pm);publish(laplace.get(),pk);publish(transport.get(),pf);
    }
    std::vector<long double> expected(PressureSchurKind kind,const std::vector<long double>& rhs) const {
        if(kind==PressureSchurKind::pcd) {
            // Independently form S_pcd = D+M F^-1 K and eliminate S_pcd.
            // This exercises the production factorization identity, not its
            // sparse construction T=K+F M^-1 D.
            auto s=d;
            for(int col=0;col<2;++col) {
                const auto response=dense_solve(f,{k[col],k[2+col]});
                for(int row=0;row<2;++row) s[row*2+col]+=m[row]*response[row];
            }
            return dense_solve(s,rhs);
        }
        std::vector<long double> w(3,1.),l(4,0.),h(4,0.);
        if(kind==PressureSchurKind::bfbt) for(int i=0;i<3;++i) w[i]=1.L/std::abs(a[i*3+i]);
        long double scale=0.;
        for(int i=0;i<3;++i) {
            long double rowsum=0.;
            for(int j=0;j<3;++j) rowsum+=std::abs(w[i]*a[i*3+j]);
            scale=std::max(scale,rowsum);
        }
        for(int i=0;i<2;++i) for(int j=0;j<2;++j) {
            l[i*2+j]=scale*d[i*2+j]; h[i*2+j]=scale*scale*d[i*2+j];
            for(int v=0;v<3;++v) {
                l[i*2+j]-=c[i*3+v]*w[v]*b[v*2+j];
                for(int u=0;u<3;++u) h[i*2+j]-=c[i*3+v]*w[v]*a[v*3+u]*w[u]*b[u*2+j];
            }
        }
        return dense_solve(l,dense_mult(h,dense_solve(l,rhs)));
    }
    std::vector<long double> exact_schur(const std::vector<long double>& rhs) const {
        auto s=d;
        for(int col=0;col<2;++col) {
            const auto response=dense_solve(a,{b[col],b[2+col],b[4+col]});
            for(int row=0;row<2;++row) for(int v=0;v<3;++v) s[row*2+col]-=c[row*3+v]*response[v];
        }
        return dense_solve(s,rhs);
    }
};

void compare_action(MPI_Comm comm,KSP solver,const std::vector<long double>& expected) {
    Mat matrix=nullptr; EONSIM_PETSC(KSPGetOperators(solver,nullptr,&matrix));
    PetscOwner<Vec,VecDestroy> rhs,solution;
    EONSIM_PETSC(MatCreateVecs(matrix,solution.put(),rhs.put()));
    PetscInt begin=0,end=0;EONSIM_PETSC(VecGetOwnershipRange(rhs.get(),&begin,&end));
    PetscScalar* array=nullptr;EONSIM_PETSC(VecGetArray(rhs.get(),&array));
    const double data[]={.7,-1.2};
    for(PetscInt row=begin;row<end;++row) array[row-begin]=data[row];
    EONSIM_PETSC(VecRestoreArray(rhs.get(),&array));
    EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason;EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    const PetscScalar* values=nullptr;EONSIM_PETSC(VecGetArrayRead(solution.get(),&values));
    bool correct=reason>0;
    for(PetscInt row=begin;row<end;++row)
        correct=correct&&std::isfinite(values[row-begin])&&
            std::abs(values[row-begin]-expected[row])<2e-11L*(1.+std::abs(expected[row]));
    EONSIM_PETSC(VecRestoreArrayRead(solution.get(),&values));
    check(comm,correct,"pressure action failed independent dense oracle");
}
void run_oracles(MPI_Comm comm) {
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-oracle_pressure_aux_ksp_type","gmres"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-oracle_pressure_aux_ksp_rtol","1e-13"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-oracle_pressure_aux_ksp_atol","1e-14"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-oracle_pressure_aux_pc_type","jacobi"));
    for(auto kind:{PressureSchurKind::lsc,PressureSchurKind::bfbt,PressureSchurKind::pcd}) {
        Example example(comm);
        auto state=make_pressure_schur_state(comm,example.matrix.get(),example.velocity_rows,example.pressure_rows,kind);
        Mat original=pressure_schur_matrix(state);
        PetscOwner<KSP,KSPDestroy> solver,second;
        for(auto* owner:{&solver,&second}) {
            EONSIM_PETSC(KSPCreate(comm,owner->put()));
            EONSIM_PETSC(KSPSetOptionsPrefix(owner->get(),"oracle_"));
            EONSIM_PETSC(KSPSetOperators(owner->get(),original,original));
            configure_pressure_schur_pc(comm,owner->get(),state);
        }
        for(int phase=0;phase<4;++phase) {
            if(phase) { example.fill(phase); refresh_pressure_schur(state,example.matrix.get()); }
            check(comm,pressure_schur_matrix(state)==original,"pressure refresh replaced USER matrix identity");
            const auto expected=example.expected(kind,{.7L,-1.2L});
            compare_action(comm,solver.get(),expected); compare_action(comm,second.get(),expected);
        }
        example.fill(0,true);refresh_pressure_schur(state,example.matrix.get());
        compare_action(comm,solver.get(),example.expected(kind,{.7L,-1.2L}));
        if(kind!=PressureSchurKind::pcd) {
            example.fill(0,false,true);refresh_pressure_schur(state,example.matrix.get());
            compare_action(comm,solver.get(),example.exact_schur({.7L,-1.2L}));
        }
    }
}
void rejects(MPI_Comm comm,const std::function<void()>& operation,const char* message) {
    bool rejected=false;
    try { operation(); } catch(const std::runtime_error&) { rejected=true; }
    check(comm,rejected,message);
}
void negative_cases(MPI_Comm comm) {
    Example example(comm);
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(example.matrix.get()),pressure_pcd_mass_key,nullptr));
    rejects(comm,[&]{make_pressure_schur_state(comm,example.matrix.get(),example.velocity_rows,
        example.pressure_rows,PressureSchurKind::pcd);},"PCD silently accepted a missing physical mass operator");
    EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(example.matrix.get()),pressure_pcd_mass_key,
        reinterpret_cast<PetscObject>(example.mass.get())));
    const PetscInt row=1;
    if(row>=example.begin&&row<example.end) EONSIM_PETSC(MatSetValue(example.mass.get(),row,row,0.,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(example.mass.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(example.mass.get(),MAT_FINAL_ASSEMBLY));
    rejects(comm,[&]{make_pressure_schur_state(comm,example.matrix.get(),example.velocity_rows,
        example.pressure_rows,PressureSchurKind::pcd);},"PCD silently accepted zero pressure mass");
    example.fill(0);
    const PetscInt velocity=0;
    if(velocity>=example.begin&&velocity<example.end) EONSIM_PETSC(MatSetValue(example.matrix.get(),velocity,velocity,0.,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(example.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(example.matrix.get(),MAT_FINAL_ASSEMBLY));
    rejects(comm,[&]{make_pressure_schur_state(comm,example.matrix.get(),example.velocity_rows,
        example.pressure_rows,PressureSchurKind::bfbt);},"BFBt silently accepted zero momentum diagonal");
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-invalid_pc_type","jacobi"));
    rejects(comm,[&]{validate_pressure_schur_options(comm,"invalid_");},"pressure shell PC conflict was not rejected before assembly");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-invalid_pc_type"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-invalid_ksp_type","cg"));
    rejects(comm,[&]{validate_pressure_schur_options(comm,"invalid_");},"pressure unsupported KSP was not rejected before assembly");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-invalid_ksp_type"));
}
void compact_auxiliary(MPI_Comm comm) {
    Example example(comm);
    std::vector<PetscInt> rows;
    for(PetscInt row=example.begin;row<example.end;++row) if(row!=2&&row!=6) rows.push_back(row);
    PetscOwner<IS,ISDestroy> indices;
    EONSIM_PETSC(ISCreateGeneral(comm,rows.size(),rows.data(),PETSC_COPY_VALUES,indices.put()));
    PetscOwner<Mat,MatDestroy> compact;
    Mat initial_mass=nullptr;
    for(int phase=0;phase<3;++phase) {
        if(phase) example.fill(phase);
        EONSIM_PETSC(MatCreateSubMatrix(example.matrix.get(),indices.get(),indices.get(),
            phase?MAT_REUSE_MATRIX:MAT_INITIAL_MATRIX,compact.put()));
        propagate_pressure_auxiliaries(example.matrix.get(),compact.get(),indices.get());
        Mat mass=nullptr;
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(compact.get()),pressure_pcd_mass_key,
            reinterpret_cast<PetscObject*>(&mass)));
        if(!phase) initial_mass=mass;
        check(comm,mass&&mass==initial_mass,"compact pressure auxiliary identity was not retained");
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(mass,&begin,&end));
        bool correct=true;
        for(PetscInt row=begin;row<end;++row) {
            double value=0.;EONSIM_PETSC(MatGetValues(mass,1,&row,1,&row,&value));
            const double expected=row==1?static_cast<double>(example.m[0]):row==3?static_cast<double>(example.m[1]):0.;
            correct=correct&&std::abs(value-expected)<1e-14;
        }
        check(comm,correct,"compact pressure auxiliary numerical refresh failed");
    }
}
void failed_refresh_recovery(MPI_Comm comm) {
    for(auto kind:{PressureSchurKind::bfbt,PressureSchurKind::pcd}) {
        Example example(comm);
        auto state=make_pressure_schur_state(comm,example.matrix.get(),example.velocity_rows,example.pressure_rows,kind);
        PetscOwner<KSP,KSPDestroy> solver;
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),"oracle_"));
        EONSIM_PETSC(KSPSetOperators(solver.get(),pressure_schur_matrix(state),pressure_schur_matrix(state)));
        configure_pressure_schur_pc(comm,solver.get(),state);
        compare_action(comm,solver.get(),example.expected(kind,{.7L,-1.2L}));
        PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
        check(comm,pressure_schur_auxiliary_solver(pc)!=nullptr,"pressure diagnostics did not expose auxiliary KSP");
        for(int broken=0;broken<2;++broken) {
            const PetscInt row=kind==PressureSchurKind::pcd?1:0;
            const Mat target=kind==PressureSchurKind::pcd?example.mass.get():example.matrix.get();
            if(row>=example.begin&&row<example.end)
                EONSIM_PETSC(MatSetValue(target,row,row,broken?std::numeric_limits<double>::infinity():0.,INSERT_VALUES));
            EONSIM_PETSC(MatAssemblyBegin(target,MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(target,MAT_FINAL_ASSEMBLY));
            rejects(comm,[&]{refresh_pressure_schur(state,example.matrix.get());},
                "invalid numerical pressure refresh was silently accepted");
            PetscOwner<Vec,VecDestroy> input,output;
            EONSIM_PETSC(MatCreateVecs(pressure_schur_matrix(state),input.put(),output.put()));
            EONSIM_PETSC(VecSet(input.get(),1.));
            EONSIM_PETSC(PCApply(pc,input.get(),output.get()));
            PCFailedReason reason=PC_NOERROR; EONSIM_PETSC(PCGetFailedReason(pc,&reason));
            check(comm,reason==PC_SUBPC_ERROR,"invalidated pressure state was reused after failed refresh");
            example.fill(broken+1);refresh_pressure_schur(state,example.matrix.get());
            compare_action(comm,solver.get(),example.expected(kind,{.7L,-1.2L}));
        }
    }
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    {
        try {
            run_oracles(PETSC_COMM_WORLD);negative_cases(PETSC_COMM_WORLD);compact_auxiliary(PETSC_COMM_WORLD);
            failed_refresh_recovery(PETSC_COMM_WORLD);
            PetscPrintf(PETSC_COMM_WORLD,"pressure_schur_oracles passed: LSC/BFBt/PCD, stabilization, shared refresh, empty owners, compact auxiliaries\n");
        } catch(const std::exception& error) {
            PetscPrintf(PETSC_COMM_WORLD,"pressure_schur_oracles failed: %s\n",error.what());result=1;
        }
    }
    PetscFinalize();return result;
}
