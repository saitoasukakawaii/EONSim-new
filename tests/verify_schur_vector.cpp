#include "eonsim/schur_solver.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool good,const char* message) {
    int bad=!good,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
double coefficient(PetscInt i,PetscInt j) {
    return i==j?4.+.1*i:.003*(i+1)*(j+1);
}
AlgebraLayout layout(MPI_Comm comm) {
    int rank,size; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
    check(comm,size==1||size==2||size==4,"Expected 1/2/4 ranks");
    // Four ranks deliberately include two empty row owners. A node's four
    // physical unknowns stay together; compressed velocity rows are triples.
    const int cuts4[]={0,2,2,3,3},cuts2[]={0,2,3};
    int first=size==1?0:(size==2?cuts2[rank]:cuts4[rank]);
    int last=size==1?3:(size==2?cuts2[rank+1]:cuts4[rank+1]);
    AlgebraLayout l;l.global=12;l.begin=4*first;l.owned=4*(last-first);
    l.fields["velocity"];l.fields["pressure"];
    for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
        l.local_to_global.push_back(row);
        DofKey key;key.entity=500+17*(row/4);key.component=row%4==3?0:row%4;
        key.quantity=row%4==3?DofQuantity::pressure:DofQuantity::velocity;
        l.owned_semantics.push_back(key);
        l.fields[row%4==3?"pressure":"velocity"].push_back(row);
    }
    return l;
}
void matrix(MPI_Comm comm,const AlgebraLayout& l,Mat* a) {
    EONSIM_PETSC(MatCreateAIJ(comm,l.owned,l.owned,l.global,l.global,l.owned,nullptr,l.global-l.owned,nullptr,a));
    for(PetscInt i=l.begin;i<l.begin+l.owned;++i)
        for(PetscInt j=0;j<l.global;++j) EONSIM_PETSC(MatSetValue(*a,i,j,coefficient(i,j),INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(*a,MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(*a,MAT_FINAL_ASSEMBLY));
}
void inspect_and_solve(MPI_Comm comm,KSP solver,Mat a,bool enabled) {
    EONSIM_PETSC(KSPSetType(solver,KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-12,1e-14,PETSC_DEFAULT,100));
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    PetscInt count=0;KSP* subs=nullptr;
    EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&count,&subs));
    check(comm,count==2,"Wrong Schur child count");
    bool good=true;
    for(int field=0;field<2;++field) {
        Mat sub;EONSIM_PETSC(KSPGetOperators(subs[field],&sub,nullptr));
        PetscInt bs=0,begin=0,end=0,m=0;
        EONSIM_PETSC(MatGetBlockSize(sub,&bs));
        EONSIM_PETSC(MatGetSize(sub,&m,nullptr));
        good=good&&bs==(field==0&&enabled?3:1)&&m==(field==0?9:3);
        // The velocity block must contain the original entries in the same
        // physical order; metadata is not an operator permutation.
        if(field==0) {
            EONSIM_PETSC(MatGetOwnershipRange(sub,&begin,&end));
            for(PetscInt i=begin;i<end;++i) for(PetscInt j=0;j<m;++j) {
                PetscScalar value=0;EONSIM_PETSC(MatGetValues(sub,1,&i,1,&j,&value));
                good=good&&std::abs(value-coefficient(4*(i/3)+i%3,4*(j/3)+j%3))<1e-14;
            }
        }
    }
    EONSIM_PETSC(PetscFree(subs));
    PetscInt root_bs=0;EONSIM_PETSC(MatGetBlockSize(a,&root_bs));
    check(comm,good&&root_bs==1,"Submatrix metadata, ownership or entry oracle failed");
    PetscOwner<Vec,VecDestroy> exact,rhs,x,error;
    EONSIM_PETSC(MatCreateVecs(a,exact.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(exact.get(),x.put()));EONSIM_PETSC(VecDuplicate(rhs.get(),error.put()));
    PetscInt begin=0,end=0;EONSIM_PETSC(VecGetOwnershipRange(exact.get(),&begin,&end));
    PetscScalar* values=nullptr;EONSIM_PETSC(VecGetArray(exact.get(),&values));
    for(PetscInt i=begin;i<end;++i) values[i-begin]=1.+.1*i;
    EONSIM_PETSC(VecRestoreArray(exact.get(),&values));
    EONSIM_PETSC(MatMult(a,exact.get(),rhs.get()));EONSIM_PETSC(KSPSolve(solver,rhs.get(),x.get()));
    KSPConvergedReason reason;EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(MatMult(a,x.get(),error.get()));EONSIM_PETSC(VecAXPY(error.get(),-1.,rhs.get()));
    PetscReal residual=0,rhs_norm=0,difference=0;
    EONSIM_PETSC(VecNorm(error.get(),NORM_2,&residual));EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&rhs_norm));
    EONSIM_PETSC(VecAXPY(x.get(),-1.,exact.get()));EONSIM_PETSC(VecNorm(x.get(),NORM_INFINITY,&difference));
    check(comm,reason>0&&std::isfinite(difference)&&difference<1e-10&&residual<1e-10*rhs_norm,
          "Manufactured Schur solve or independent true residual failed");
}
void run(MPI_Comm comm) {
    int rank=0,size=0;MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&size);
    auto l=layout(comm);PetscOwner<Mat,MatDestroy> a;matrix(comm,l,a.put());
    for(bool enabled:{false,true}) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-schur_velocity_block3",enabled?"true":"false"));
        PetscOwner<KSP,KSPDestroy> solver;EONSIM_PETSC(KSPCreate(comm,solver.put()));
        configure_schur_solver(comm,solver.get(),l,a.get());inspect_and_solve(comm,solver.get(),a.get(),enabled);
    }
    for(int failure=0;failure<4;++failure) {
        if(failure==3&&size==1) continue;
        auto broken=l;
        if(rank==0) {
            if(failure==0) broken.owned_semantics.clear();
            if(failure==1) broken.owned_semantics[1].component=0;
            if(failure==2) broken.fields["mesh"]={};
        }
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-schur_velocity_block3",failure==3&&rank==0?"false":"true"));
        PetscOwner<KSP,KSPDestroy> solver;EONSIM_PETSC(KSPCreate(comm,solver.put()));
        bool caught=false;
        try {configure_schur_solver(comm,solver.get(),broken,a.get());}
        catch(const std::runtime_error& e) {caught=std::string(e.what()).find("Schur velocity")!=std::string::npos;}
        check(comm,caught,"A rank-local metadata/option defect was not rejected collectively");
        // Failure happens before modifying this KSP: repair and use that same
        // object to ensure rejection leaves no partially registered fields.
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-schur_velocity_block3","true"));
        configure_schur_solver(comm,solver.get(),l,a.get());inspect_and_solve(comm,solver.get(),a.get(),true);
    }
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-schur_velocity_block3"));
    if(rank==0) std::cout<<"schur_vector_metadata ranks="<<size<<" status=passed\n";
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);PetscPushErrorHandler(PetscReturnErrorHandler,nullptr);
    int result=0;
    try {run(PETSC_COMM_WORLD);} catch(const std::exception& error) {std::cerr<<error.what()<<'\n';result=1;}
    PetscPopErrorHandler();PetscFinalize();return result;
}
