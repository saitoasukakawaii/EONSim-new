#include "eonsim/coupled_velocity_pc.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using namespace eonsim;
namespace {
void require(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0;
    MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
bool constrained(PetscInt row,PetscInt nodes,int n) {
    return row<6*nodes&&((row/6)%n==0||row%47==11);
}
std::array<double,3> point(PetscInt node,int n) {
    return {{double(node%n)/(n-1),double((node/n)%n)/(n-1),double(node/(n*n))/(n-1)}};
}
std::array<double,13> candidate(PetscInt row,PetscInt nodes,int n) {
    std::array<double,13> result{};
    if(constrained(row,nodes,n)) return result;
    if(row==6*nodes) { result[12]=1.; return result; }
    const int domain=(row%6)/3,component=(row%3+1)%3;
    result[3*domain+component]=1.;
    const auto x=point(row/6,n);
    for(int axis=0;axis<3;++axis) {
        const int positive=(axis+1)%3,negative=(axis+2)%3;
        result[6+3*domain+axis]=component==axis?0.:component==negative?x[positive]:-x[negative];
    }
    return result;
}
void fill(Mat matrix,int n,int phase,bool identity=false) {
    PetscInt begin=0,end=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    const PetscInt nodes=n*n*n,body=6*nodes;
    EONSIM_PETSC(MatZeroEntries(matrix));
    const double diffusion=(1.+.35*phase)*(n-1)*(n-1);
    for(PetscInt row=begin;row<end;++row) {
        if(identity||constrained(row,nodes,n)) {
            EONSIM_PETSC(MatSetValue(matrix,row,row,1.,INSERT_VALUES));
            continue;
        }
        if(row==body) {
            EONSIM_PETSC(MatSetValue(matrix,row,row,2.+phase,INSERT_VALUES));
            EONSIM_PETSC(MatSetValue(matrix,row,body-2,-.2,INSERT_VALUES));
            continue;
        }
        const auto node=row/6,slot=row%6;
        const int i=node%n,j=(node/n)%n,k=node/(n*n);
        double diagonal=.5+phase*.1;
        for(int axis=0;axis<3;++axis) for(int direction:{-1,1}) {
            const int coordinate=axis==0?i:axis==1?j:k;
            if(coordinate+direction<0||coordinate+direction>=n) continue;
            const PetscInt neighbor=node+direction*(axis==0?1:axis==1?n:n*n);
            const double coefficient=diffusion*(1.+.03*direction*(slot<3?1.:-1.));
            EONSIM_PETSC(MatSetValue(matrix,row,6*neighbor+slot,-coefficient,INSERT_VALUES));
            diagonal+=coefficient;
        }
        // Nonsymmetric two-way fluid/solid interaction, with all component
        // and domain meanings independent of the storage slot ordering.
        const double coupling=4.+.2*phase;
        EONSIM_PETSC(MatSetValue(matrix,row,6*node+(slot+3)%6,-coupling,INSERT_VALUES));
        diagonal+=coupling;
        for(int other=0;other<3;++other) if(other!=slot%3) {
            EONSIM_PETSC(MatSetValue(matrix,row,6*node+(slot/3)*3+other,.025,INSERT_VALUES));
            diagonal+=.025;
        }
        if(row==body-2) {
            EONSIM_PETSC(MatSetValue(matrix,row,body,-.3,INSERT_VALUES));
            diagonal+=.3;
        }
        EONSIM_PETSC(MatSetValue(matrix,row,row,diagonal,INSERT_VALUES));
    }
    EONSIM_PETSC(MatAssemblyBegin(matrix,MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(matrix,MAT_FINAL_ASSEMBLY));
}
void audit_span(MPI_Comm comm,PC pc,Mat matrix,int n) {
    PetscInt levels=0,begin=0,end=0;
    EONSIM_PETSC(PCMGGetLevels(pc,&levels));
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    for(int mode=0;mode<13;++mode) {
        PetscOwner<Vec,VecDestroy> fine;
        EONSIM_PETSC(MatCreateVecs(matrix,fine.put(),nullptr));
        PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(fine.get(),&values));
        for(PetscInt row=begin;row<end;++row) values[row-begin]=candidate(row,n*n*n,n)[mode];
        EONSIM_PETSC(VecRestoreArray(fine.get(),&values));
        for(PetscInt level=levels-1;level>0;--level) {
            Mat interpolation=nullptr; EONSIM_PETSC(PCMGGetInterpolation(pc,level,&interpolation));
            PetscOwner<Vec,VecDestroy> coarse,reconstructed;
            EONSIM_PETSC(MatCreateVecs(interpolation,coarse.put(),reconstructed.put()));
            EONSIM_PETSC(MatMultTranspose(interpolation,fine.get(),coarse.get()));
            EONSIM_PETSC(MatMult(interpolation,coarse.get(),reconstructed.get()));
            PetscReal norm=0,error=0;
            EONSIM_PETSC(VecNorm(fine.get(),NORM_2,&norm));
            EONSIM_PETSC(VecAXPY(reconstructed.get(),-1.,fine.get()));
            EONSIM_PETSC(VecNorm(reconstructed.get(),NORM_2,&error));
            require(comm,error<2e-10*(1.+norm),"A field AMG level lost a translation, rotation or body mode");
            fine=std::move(coarse);
        }
    }
}
void audit_galerkin(MPI_Comm comm,PC pc,Mat matrix) {
    PetscInt levels=0; EONSIM_PETSC(PCMGGetLevels(pc,&levels));
    Mat fine=matrix;
    for(PetscInt level=levels-1;level>0;--level) {
        Mat interpolation=nullptr,actual=nullptr; KSP next=nullptr;
        EONSIM_PETSC(PCMGGetInterpolation(pc,level,&interpolation));
        EONSIM_PETSC(PCMGGetSmoother(pc,level-1,&next));
        EONSIM_PETSC(KSPGetOperators(next,&actual,nullptr));
        PetscOwner<Mat,MatDestroy> expected;
        EONSIM_PETSC(MatPtAP(fine,interpolation,MAT_INITIAL_MATRIX,PETSC_DEFAULT,expected.put()));
        PetscReal norm=0,error=0;
        EONSIM_PETSC(MatNorm(expected.get(),NORM_FROBENIUS,&norm));
        EONSIM_PETSC(MatAXPY(expected.get(),-1.,actual,SAME_NONZERO_PATTERN));
        EONSIM_PETSC(MatNorm(expected.get(),NORM_FROBENIUS,&error));
        require(comm,error<2e-11*(1.+norm),"A field AMG Galerkin level failed to refresh its full coupled matrix");
        fine=actual;
    }
}
PetscInt solve(MPI_Comm comm,KSP solver,Mat matrix) {
    PetscOwner<Vec,VecDestroy> exact,rhs,solution,defect;
    EONSIM_PETSC(MatCreateVecs(matrix,exact.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(exact.get(),solution.put()));
    EONSIM_PETSC(VecDuplicate(rhs.get(),defect.put()));
    PetscInt begin=0,end=0; EONSIM_PETSC(VecGetOwnershipRange(exact.get(),&begin,&end));
    PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(exact.get(),&values));
    for(PetscInt row=begin;row<end;++row) values[row-begin]=std::sin(.17*row)+.02*std::cos(.31*row);
    EONSIM_PETSC(VecRestoreArray(exact.get(),&values));
    EONSIM_PETSC(MatMult(matrix,exact.get(),rhs.get()));
    EONSIM_PETSC(VecSet(solution.get(),0.));
    EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason; PetscInt iterations=0;
    EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(KSPGetIterationNumber(solver,&iterations));
    EONSIM_PETSC(MatMult(matrix,solution.get(),defect.get()));
    EONSIM_PETSC(VecAXPY(defect.get(),-1.,rhs.get()));
    PetscReal rhs_norm=0,residual=0,error=0;
    EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&rhs_norm));
    EONSIM_PETSC(VecNorm(defect.get(),NORM_2,&residual));
    EONSIM_PETSC(VecAXPY(solution.get(),-1.,exact.get()));
    EONSIM_PETSC(VecNorm(solution.get(),NORM_INFINITY,&error));
    require(comm,reason>0&&residual<=1e-10*(1.+rhs_norm)&&error<2e-9,
            "Field AMG failed the manufactured solution or independent true residual");
    return iterations;
}
void verify(MPI_Comm comm,int n) {
    int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
    const PetscInt nodes=n*n*n,global=6*nodes+1;
    const int owners=size==4?3:size;
    const PetscInt begin=rank<owners?global*rank/owners:global;
    const PetscInt end=rank<owners?global*(rank+1)/owners:global;
    std::vector<DofKey> keys;
    std::vector<std::array<double,3>> coordinates;
    for(PetscInt row=begin;row<end;++row) {
        DofKey key; key.entity=row/6; key.component=(row%3+1)%3;
        key.domain=row%6<3?DofDomain::fluid:DofDomain::solid;
        if(row==6*nodes) {key.kind=DofEntity::body;key.domain=DofDomain::solid;key.component=0;key.space=0;}
        keys.push_back(key);
        coordinates.push_back(row==6*nodes?std::array<double,3>{{0,0,0}}:point(row/6,n));
    }
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,global,global,
        std::min<PetscInt>(12,end-begin),nullptr,std::min<PetscInt>(12,global-end+begin),nullptr,matrix.put()));
    fill(matrix.get(),n,0);
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    const auto prefix="verify_field_"+std::to_string(n)+"_";
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,("-"+prefix+"field_amg_coarse_limit").c_str(),"40"));
    EONSIM_PETSC(KSPSetOperators(solver.get(),matrix.get(),matrix.get()));
    configure_coupled_velocity_field_amg(comm,solver.get(),keys,coordinates,true,8);
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetNormType(solver.get(),KSP_NORM_UNPRECONDITIONED));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,500));
    PC pc; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    for(int phase=0;phase<2;++phase) {
        if(phase) { fill(matrix.get(),n,phase); EONSIM_PETSC(KSPSetOperators(solver.get(),matrix.get(),matrix.get())); }
        const auto iterations=solve(comm,solver.get(),matrix.get());
        audit_galerkin(comm,pc,matrix.get());
        if(!phase) audit_span(comm,pc,matrix.get(),n);
        PetscInt levels=0; EONSIM_PETSC(PCMGGetLevels(pc,&levels));
        require(comm,levels>=3,"Field AMG did not construct a recursively preserved hierarchy");
        EONSIM_PETSC(PetscPrintf(comm,"field_amg_verified n=%d dofs=%" PetscInt_FMT " ranks=%d phase=%d levels=%" PetscInt_FMT " iterations=%" PetscInt_FMT "\n",
            n,global,size,phase,levels,iterations));
    }
    // Changing the constraint set requires a new session. The all-identity
    // branch exercises its explicit one-level exact action, including empty ranks.
    fill(matrix.get(),n,0,true);
    PetscOwner<KSP,KSPDestroy> identity;
    EONSIM_PETSC(KSPCreate(comm,identity.put()));
    EONSIM_PETSC(KSPSetOperators(identity.get(),matrix.get(),matrix.get()));
    configure_coupled_velocity_field_amg(comm,identity.get(),keys,coordinates,true,8);
    const auto identity_iterations=solve(comm,identity.get(),matrix.get());
    PC identity_pc; PetscInt identity_levels=0;
    EONSIM_PETSC(KSPGetPC(identity.get(),&identity_pc));
    EONSIM_PETSC(PCMGGetLevels(identity_pc,&identity_levels));
    require(comm,identity_levels==1&&identity_iterations==1,"All-identity field AMG did not use one exact action");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,("-"+prefix+"field_amg_coarse_limit").c_str()));
}
}
int main(int argc,char** argv) {
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    int result=0;
    try { verify(PETSC_COMM_WORLD,4); verify(PETSC_COMM_WORLD,6); }
    catch(const std::exception& error) {
        int rank=0; MPI_Comm_rank(PETSC_COMM_WORLD,&rank);
        std::cerr<<"rank="<<rank<<" field AMG verification failed: "<<error.what()<<'\n';
        result=1;
    }
    const auto finalize=PetscFinalize();
    return result||finalize?1:0;
}
