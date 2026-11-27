#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <numeric>
#include <stdexcept>

using namespace eonsim;
namespace {
std::vector<long double> solve(std::vector<long double> a,std::vector<long double> b) {
    const auto n=b.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i) if(std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if(std::abs(a[pivot*n+k])<1e-24L) throw std::runtime_error("Singular independent added-mass oracle");
        for(std::size_t j=k;j<n;++j) std::swap(a[k*n+j],a[pivot*n+j]);
        std::swap(b[k],b[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const auto multiplier=a[i*n+k]/a[k*n+k];
            for(std::size_t j=k+1;j<n;++j) a[i*n+j]-=multiplier*a[k*n+j];
            b[i]-=multiplier*b[k];
        }
    }
    for(std::size_t i=n;i-->0;) {
        for(std::size_t j=i+1;j<n;++j) b[i]-=a[i*n+j]*b[j];
        b[i]/=a[i*n+i];
    }
    return b;
}
void common(MPI_Comm comm,bool valid,const char* message) {
    int local=valid,all=0;MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm);
    if(!all) throw std::runtime_error(message);
}
void run(MPI_Comm comm,bool empty_owners) {
    int rank=0,ranks=1;MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&ranks);
    const int blocks=empty_owners?1:ranks,n=6*blocks;
    const PetscInt owned=empty_owners&&rank?0:6;
    const PetscInt begin=empty_owners?(rank?6:0):6*rank;
    PetscOwner<Mat,MatDestroy> root;
    EONSIM_PETSC(MatCreateAIJ(comm,owned,owned,n,n,owned,nullptr,n-owned,nullptr,root.put()));
    EONSIM_PETSC(MatSetOption(root.get(),MAT_IGNORE_ZERO_ENTRIES,PETSC_FALSE));
    std::vector<PetscInt> all_columns(n),velocity_rows,pressure_rows;
    std::iota(all_columns.begin(),all_columns.end(),0);
    PressureComplianceLayout groups;
    if(owned) {
        velocity_rows={begin,begin+1,begin+3,begin+4};pressure_rows={begin+2,begin+5};
        groups.fluid_groups={{begin,begin+3}};groups.structure_groups={{begin+1,begin+4}};
    }
    std::vector<int> velocities,pressures;
    for(int block=0;block<blocks;++block) {
        velocities.insert(velocities.end(),{6*block,6*block+1,6*block+3,6*block+4});
        pressures.insert(pressures.end(),{6*block+2,6*block+5});
    }
    PressureSchurHandle state;
    PetscOwner<KSP,KSPDestroy> ksp;
    PetscOwner<Vec,VecDestroy> rhs,answer;
    Mat original=nullptr;
    double worst=0.;
    for(int generation=0;generation<4;++generation) {
        std::vector<long double> matrix(n*n,0.);
        for(int block=0;block<blocks;++block) {
            const int f[2]{6*block,6*block+3},s[2]{6*block+1,6*block+4},p[2]{6*block+2,6*block+5};
            const long double stiffness=generation==1?.15L:(generation==2?80.L:2.L);
            const long double off=generation==2?0.L:1.L;
            const long double F[4]{5.L,.4L,-.3L,4.L};
            const long double K[4]{stiffness+1.L,.12L*off,-.07L*off,stiffness+1.4L};
            const long double E[4]{.4L*off,.1L*off,-.15L*off,.3L*off};
            const long double G[4]{-.35L*off,.08L*off,.12L*off,-.24L*off};
            for(int i=0;i<2;++i) for(int j=0;j<2;++j) {
                matrix[f[i]*n+f[j]]=F[2*i+j];matrix[s[i]*n+s[j]]=K[2*i+j];
                matrix[f[i]*n+s[j]]=E[2*i+j];matrix[s[i]*n+f[j]]=G[2*i+j];
                matrix[p[i]*n+p[j]]=i==j?.4L:.015L;
                matrix[f[i]*n+p[j]]=i==j?-1.L:-.2L;
                matrix[s[i]*n+p[j]]=i==j?-.35L:-.09L;
                matrix[p[i]*n+f[j]]=i==j?1.1L:.16L;
                matrix[p[i]*n+s[j]]=i==j?.29L:.04L;
                if(blocks>1) {
                    const int neighbor=6*((block+1)%blocks)+(j?5:2);
                    matrix[f[i]*n+neighbor]=-.025L*(i+j+1);
                    matrix[neighbor*n+s[i]]=.017L*(i+j+1);
                }
            }
        }
        std::vector<double> values(n);
        for(PetscInt row=begin;row<begin+owned;++row) {
            for(int column=0;column<n;++column) values[column]=static_cast<double>(matrix[row*n+column]);
            EONSIM_PETSC(MatSetValues(root.get(),1,&row,n,all_columns.data(),values.data(),INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(root.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(root.get(),MAT_FINAL_ASSEMBLY));
        if(!state) {
            state=make_pressure_schur_state(comm,root.get(),velocity_rows,pressure_rows,PressureSchurKind::added_mass,groups);
            original=pressure_schur_matrix(state);
            EONSIM_PETSC(KSPCreate(comm,ksp.put()));
            EONSIM_PETSC(KSPSetOptionsPrefix(ksp.get(),"compliance_"));
            EONSIM_PETSC(KSPSetOperators(ksp.get(),original,original));
            configure_pressure_schur_pc(comm,ksp.get(),state);
            EONSIM_PETSC(MatCreateVecs(original,answer.put(),rhs.put()));
        } else refresh_pressure_schur(state,root.get());
        common(comm,pressure_schur_matrix(state)==original,"Added-mass USER matrix identity changed on refresh");
        const auto nv=velocities.size(),np=pressures.size();
        std::vector<long double> a(nv*nv),schur(np*np),input(np);
        for(std::size_t i=0;i<nv;++i) for(std::size_t j=0;j<nv;++j) a[i*nv+j]=matrix[velocities[i]*n+velocities[j]];
        for(std::size_t j=0;j<np;++j) {
            std::vector<long double> pressure_load(nv);
            for(std::size_t v=0;v<nv;++v) pressure_load[v]=matrix[velocities[v]*n+pressures[j]];
            const auto response=solve(a,pressure_load);
            for(std::size_t i=0;i<np;++i) {
                schur[i*np+j]=matrix[pressures[i]*n+pressures[j]];
                for(std::size_t v=0;v<nv;++v) schur[i*np+j]-=matrix[pressures[i]*n+velocities[v]]*response[v];
            }
        }
        for(std::size_t i=0;i<np;++i) input[i]=.4L+.2L*i;
        const auto expected=solve(schur,input);
        PetscInt rb=0,re=0;PetscScalar* destination=nullptr;
        EONSIM_PETSC(VecGetOwnershipRange(rhs.get(),&rb,&re));
        EONSIM_PETSC(VecGetArray(rhs.get(),&destination));
        for(PetscInt row=rb;row<re;++row) destination[row-rb]=static_cast<double>(input[row]);
        EONSIM_PETSC(VecRestoreArray(rhs.get(),&destination));
        EONSIM_PETSC(KSPSolve(ksp.get(),rhs.get(),answer.get()));
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;EONSIM_PETSC(KSPGetConvergedReason(ksp.get(),&reason));
        const PetscScalar* actual=nullptr;EONSIM_PETSC(VecGetArrayRead(answer.get(),&actual));
        bool finite=reason>0;
        for(PetscInt row=rb;row<re;++row) {
            finite=finite&&std::isfinite(actual[row-rb]);
            worst=std::max(worst,static_cast<double>(std::abs(actual[row-rb]-expected[row])/(1.L+std::abs(expected[row]))));
        }
        EONSIM_PETSC(VecRestoreArrayRead(answer.get(),&actual));
        common(comm,finite&&worst<2e-11,"Added-mass action failed independent full momentum elimination oracle");
    }
    // Wrong semantic partition must be rejected before creating PETSc products.
    auto invalid=groups;if(owned) invalid.structure_groups[0][0]=begin;
    bool rejected=false;
    try { auto wrong=make_pressure_schur_state(comm,root.get(),velocity_rows,pressure_rows,PressureSchurKind::added_mass,invalid); }
    catch(const std::runtime_error&) {rejected=true;}
    common(comm,rejected,"Added-mass semantic overlap was not collectively rejected");
    double global_worst=0.;MPI_Allreduce(&worst,&global_worst,1,MPI_DOUBLE,MPI_MAX,comm);
    PetscPrintf(comm,"added_mass_pressure empty_owners=%d generations=4 max_error=%.17g\n",int(empty_owners),global_worst);
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);int status=0;
    try {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-compliance_pressure_aux_ksp_type","gmres"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-compliance_pressure_aux_pc_type","jacobi"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-compliance_pressure_aux_ksp_rtol","1e-13"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-compliance_pressure_aux_ksp_atol","1e-14"));
        run(PETSC_COMM_WORLD,false);run(PETSC_COMM_WORLD,true);
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';status=1;}
    int any=0;MPI_Allreduce(&status,&any,1,MPI_INT,MPI_MAX,PETSC_COMM_WORLD);
    PetscFinalize();return any;
}
